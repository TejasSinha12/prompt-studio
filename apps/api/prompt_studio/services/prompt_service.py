"""PromptVersionService (library, versions, restore) and PromptEvaluationService."""

from __future__ import annotations

import difflib
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import schemas
from ..engine.evaluator.quality import SCORE_FORMULA, evaluate
from ..engine.spec import CODING_CATEGORIES
from ..engine.templates.profiles import get_profile
from ..errors import not_found
from ..models import Evaluation, Project, Prompt, PromptVersion, Tag, prompt_tags, utcnow
from .project_service import ProjectService, add_event, get_or_create_tags


def change_summary(old: str, new: str) -> str:
    if old == new:
        return "No content changes."
    added = removed = 0
    for line in difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return f"+{added} / -{removed} lines"


class PromptService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, prompt_id: str) -> Prompt:
        p = self.db.get(Prompt, prompt_id)
        if p is None:
            raise not_found("Prompt")
        return p

    def get_version(self, version_id: str) -> PromptVersion:
        v = self.db.get(PromptVersion, version_id)
        if v is None:
            raise not_found("Prompt version")
        return v

    def list(
        self,
        q: str = "",
        tag: str = "",
        category: str = "",
        favorite: bool | None = None,
        archived: str = "false",
        project_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(Prompt)
        if archived == "false":
            stmt = stmt.where(Prompt.archived.is_(False))
        elif archived == "true":
            stmt = stmt.where(Prompt.archived.is_(True))
        if project_id:
            stmt = stmt.where(Prompt.project_id == project_id)
        if category:
            stmt = stmt.where(Prompt.category == category)
        if favorite is not None:
            stmt = stmt.where(Prompt.favorite.is_(favorite))
        if tag:
            stmt = stmt.join(prompt_tags).join(Tag).where(Tag.name == tag.lower())
        if q:
            like = f"%{q.lower()}%"
            matching_versions = select(PromptVersion.prompt_id).where(func.lower(PromptVersion.content).like(like))
            stmt = stmt.where(or_(func.lower(Prompt.title).like(like), Prompt.id.in_(matching_versions)))
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        prompts = list(self.db.scalars(stmt.order_by(Prompt.updated_at.desc()).limit(limit).offset(offset)))
        ids = [p.id for p in prompts]
        counts = (
            dict(
                self.db.execute(
                    select(PromptVersion.prompt_id, func.count())
                    .where(PromptVersion.prompt_id.in_(ids))
                    .group_by(PromptVersion.prompt_id)
                ).all()
            )
            if ids
            else {}
        )
        pids = {p.project_id for p in prompts if p.project_id}
        names = (
            dict(self.db.execute(select(Project.id, Project.name).where(Project.id.in_(pids))).all()) if pids else {}
        )
        items = []
        for p in prompts:
            d = schemas.PromptSummary.model_validate(p).model_dump()
            d["version_count"] = counts.get(p.id, 0)
            d["project_name"] = names.get(p.project_id) if p.project_id else None
            items.append(d)
        return items, total

    def detail(self, prompt_id: str, version_limit: int = 200) -> schemas.PromptOut:
        p = self.get(prompt_id)
        versions = list(
            self.db.scalars(
                select(PromptVersion)
                .where(PromptVersion.prompt_id == p.id)
                .order_by(PromptVersion.number.desc())
                .limit(version_limit)
            )
        )
        current = self.db.get(PromptVersion, p.current_version_id) if p.current_version_id else None
        out = schemas.PromptOut.model_validate(p)
        out.versions = [schemas.VersionMeta.model_validate(v) for v in versions]
        out.version_count = len(versions)
        out.current_version = schemas.VersionOut.model_validate(current) if current else None
        if p.project_id:
            proj = self.db.get(Project, p.project_id)
            out.project_name = proj.name if proj else None
        return out

    def _snapshot(self, project_id: str | None) -> dict[str, Any]:
        if not project_id:
            return {}
        ps = ProjectService(self.db)
        return ps.snapshot(ps.get(project_id))

    def create(self, data: schemas.PromptCreate) -> Prompt:
        project = None
        if data.project_id:
            project = ProjectService(self.db).get(data.project_id)
        p = Prompt(project_id=data.project_id, title=data.title, category=data.category, target_agent=data.target_agent)
        p.tags = get_or_create_tags(self.db, data.tags)
        self.db.add(p)
        self.db.flush()
        self._add_version(
            p,
            schemas.VersionCreate(
                content=data.content,
                variant=data.variant,
                profile_id=data.target_agent,
                generator=data.generator,
                model=data.model,
                change_summary=data.change_summary or "Initial version",
            ),
            parent=None,
        )
        if project:
            add_event(self.db, project.id, "prompt", f"Saved prompt '{p.title}' (v1, {data.variant})")
        self.db.commit()
        return p

    def _add_version(
        self, p: Prompt, data: schemas.VersionCreate, parent: PromptVersion | None, summary_override: str | None = None
    ) -> PromptVersion:
        number = (
            self.db.scalar(select(func.max(PromptVersion.number)).where(PromptVersion.prompt_id == p.id)) or 0
        ) + 1
        profile = get_profile(data.profile_id or p.target_agent)
        previous = self.db.get(PromptVersion, p.current_version_id) if p.current_version_id else None
        summary = summary_override or data.change_summary
        if previous is not None:
            diff = change_summary(previous.content, data.content)
            summary = f"{summary} ({diff})" if summary else diff
        v = PromptVersion(
            prompt_id=p.id,
            number=number,
            content=data.content,
            variant=data.variant,
            profile_id=profile.id,
            profile_version=profile.version,
            generator=data.generator,
            model=data.model,
            source_snapshot=self._snapshot(p.project_id),
            change_summary=summary[:1000],
            parent_version_id=(parent or previous).id if (parent or previous) else None,
        )
        self.db.add(v)
        self.db.flush()
        p.current_version_id = v.id
        p.updated_at = utcnow()
        return v

    def add_version(self, prompt_id: str, data: schemas.VersionCreate) -> PromptVersion:
        p = self.get(prompt_id)
        v = self._add_version(p, data, parent=None)
        if p.project_id:
            add_event(self.db, p.project_id, "prompt", f"Saved '{p.title}' v{v.number} ({v.variant}, {v.generator})")
        self.db.commit()
        return v

    def restore(self, prompt_id: str, version_id: str) -> PromptVersion:
        p = self.get(prompt_id)
        src = self.get_version(version_id)
        if src.prompt_id != p.id:
            raise not_found("Prompt version")
        v = self._add_version(
            p,
            schemas.VersionCreate(
                content=src.content,
                variant=src.variant,
                profile_id=src.profile_id,
                generator=src.generator,
                model=src.model,
            ),
            parent=src,
            summary_override=f"Restored from v{src.number}",
        )
        if p.project_id:
            add_event(self.db, p.project_id, "prompt", f"Restored '{p.title}' v{src.number} as v{v.number}")
        self.db.commit()
        return v

    def update(self, prompt_id: str, data: schemas.PromptUpdate) -> Prompt:
        p = self.get(prompt_id)
        for field in ("title", "category", "target_agent", "favorite", "archived"):
            val = getattr(data, field)
            if val is not None:
                setattr(p, field, val)
        if data.tags is not None:
            p.tags = get_or_create_tags(self.db, data.tags)
        p.updated_at = utcnow()
        self.db.commit()
        return p

    def duplicate(self, prompt_id: str) -> Prompt:
        src = self.get(prompt_id)
        cur = self.db.get(PromptVersion, src.current_version_id) if src.current_version_id else None
        p = Prompt(
            project_id=src.project_id,
            title=f"{src.title} (copy)"[:200],
            category=src.category,
            target_agent=src.target_agent,
        )
        p.tags = list(src.tags)
        self.db.add(p)
        self.db.flush()
        if cur:
            self._add_version(
                p,
                schemas.VersionCreate(
                    content=cur.content,
                    variant=cur.variant,
                    profile_id=cur.profile_id,
                    generator=cur.generator,
                    model=cur.model,
                ),
                parent=None,
                summary_override=f"Duplicated from '{src.title}' v{cur.number}",
            )
        self.db.commit()
        return p

    def delete(self, prompt_id: str) -> None:
        p = self.get(prompt_id)
        if p.project_id:
            add_event(self.db, p.project_id, "prompt", f"Deleted prompt '{p.title}'")
        self.db.delete(p)
        self.db.commit()


class EvaluationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate_version(self, version_id: str) -> Evaluation:
        v = PromptService(self.db).get_version(version_id)
        prompt = self.db.get(Prompt, v.prompt_id)
        assert prompt is not None
        coding = get_profile(v.profile_id).coding and prompt.category in CODING_CATEGORIES | {"general"}
        res = evaluate(v.content, coding=coding)
        e = Evaluation(
            prompt_version_id=v.id,
            engine="rule_based",
            score=res.score,
            dimensions=[d.model_dump() for d in res.dimensions],
            metrics=dict(res.metrics),
        )
        self.db.add(e)
        self.db.commit()
        return e

    def list_for_version(self, version_id: str) -> list[Evaluation]:
        return list(
            self.db.scalars(
                select(Evaluation)
                .where(Evaluation.prompt_version_id == version_id)
                .order_by(Evaluation.created_at.desc())
            )
        )

    def recent(self, limit: int = 50) -> list[schemas.EvaluationOut]:
        rows = self.db.execute(
            select(Evaluation, PromptVersion.number, Prompt.id, Prompt.title)
            .join(PromptVersion, Evaluation.prompt_version_id == PromptVersion.id)
            .join(Prompt, PromptVersion.prompt_id == Prompt.id)
            .order_by(Evaluation.created_at.desc())
            .limit(limit)
        ).all()
        out = []
        for e, num, pid, title in rows:
            o = to_out(e)
            o.version_number, o.prompt_id, o.prompt_title = num, pid, title
            out.append(o)
        return out


def to_out(e: Evaluation) -> schemas.EvaluationOut:
    o = schemas.EvaluationOut.model_validate(e)
    o.formula = (
        SCORE_FORMULA
        if e.engine == "rule_based"
        else "Local-AI judgment of implementation feasibility; not combined with rule-based scores."
    )
    return o
