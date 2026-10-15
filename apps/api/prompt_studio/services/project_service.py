"""ProjectService and RequirementService."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import schemas
from ..engine.spec import ProjectSpec, PromptConfig, SpecRequirement
from ..engine.templates.task_templates import TEMPLATES_BY_ID
from ..errors import bad_request, conflict, not_found
from ..models import (
    Finding,
    Project,
    ProjectEvent,
    Prompt,
    PromptVersion,
    Recommendation,
    Requirement,
    Tag,
    project_tags,
    utcnow,
)


def get_or_create_tags(db: Session, names: list[str]) -> list[Tag]:
    clean = sorted({n.strip().lower() for n in names if n.strip()})
    if not clean:
        return []
    existing = {t.name: t for t in db.scalars(select(Tag).where(Tag.name.in_(clean)))}
    out = []
    for n in clean:
        tag = existing.get(n)
        if tag is None:
            tag = Tag(name=n)
            db.add(tag)
        out.append(tag)
    return out


def add_event(db: Session, project_id: str, kind: str, summary: str) -> None:
    db.add(ProjectEvent(project_id=project_id, kind=kind, summary=summary[:500]))


def touch(project: Project) -> None:
    project.updated_at = utcnow()


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ queries
    def get(self, project_id: str) -> Project:
        p = self.db.get(Project, project_id)
        if p is None:
            raise not_found("Project")
        return p

    def list(
        self, q: str = "", tag: str = "", archived: str = "false", limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(Project)
        if archived == "false":
            stmt = stmt.where(Project.archived.is_(False))
        elif archived == "true":
            stmt = stmt.where(Project.archived.is_(True))
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Project.name).like(like),
                    func.lower(Project.description).like(like),
                    func.lower(Project.original_idea).like(like),
                )
            )
        if tag:
            stmt = stmt.join(project_tags).join(Tag).where(Tag.name == tag.lower())
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        projects = list(self.db.scalars(stmt.order_by(Project.updated_at.desc()).limit(limit).offset(offset)))
        ids = [p.id for p in projects]
        open_f = (
            dict(
                self.db.execute(
                    select(Finding.project_id, func.count())
                    .where(Finding.project_id.in_(ids), Finding.status == "open")
                    .group_by(Finding.project_id)
                ).all()
            )
            if ids
            else {}
        )
        prop_r = (
            dict(
                self.db.execute(
                    select(Recommendation.project_id, func.count())
                    .where(Recommendation.project_id.in_(ids), Recommendation.status == "proposed")
                    .group_by(Recommendation.project_id)
                ).all()
            )
            if ids
            else {}
        )
        items = []
        for p in projects:
            d = schemas.ProjectSummary.model_validate(p).model_dump()
            d["task_category"] = (p.config or {}).get("task_category", "general")
            d["open_findings"] = open_f.get(p.id, 0)
            d["proposed_recommendations"] = prop_r.get(p.id, 0)
            items.append(d)
        return items, total

    def events(self, project_id: str, limit: int = 100) -> list[ProjectEvent]:
        self.get(project_id)
        return list(
            self.db.scalars(
                select(ProjectEvent)
                .where(ProjectEvent.project_id == project_id)
                .order_by(ProjectEvent.created_at.desc())
                .limit(limit)
            )
        )

    # ------------------------------------------------------------------ mutations
    def create(self, data: schemas.ProjectCreate) -> Project:
        p = Project(
            name=data.name,
            description=data.description,
            original_idea=data.original_idea,
            tech_stack=data.tech_stack,
            config=data.config.model_dump(),
        )
        p.tags = get_or_create_tags(self.db, data.tags)
        self.db.add(p)
        self.db.flush()
        add_event(self.db, p.id, "created", f"Project '{p.name}' created")
        self.db.commit()
        return p

    def create_from_template(self, data: schemas.ProjectFromTemplate) -> Project:
        tpl = TEMPLATES_BY_ID.get(data.template_id)
        if tpl is None:
            raise not_found("Template")
        cfg = PromptConfig(**tpl.config)
        p = Project(name=data.name, description=tpl.description, original_idea=tpl.idea, config=cfg.model_dump())
        self.db.add(p)
        self.db.flush()
        for i, r in enumerate(tpl.requirements):
            self.db.add(
                Requirement(project_id=p.id, kind=r.kind, text=r.text, status="proposed", source="template", position=i)
            )
        add_event(
            self.db,
            p.id,
            "created",
            f"Project created from template '{tpl.name}'; "
            f"{len(tpl.requirements)} template requirement(s) awaiting review",
        )
        self.db.commit()
        self.db.refresh(p)
        return p

    def update(self, project_id: str, data: schemas.ProjectUpdate) -> Project:
        p = self.get(project_id)
        if data.revision != p.revision:
            raise conflict(
                "This project was changed elsewhere. Reload to see the latest version.", current_revision=p.revision
            )
        changed = []
        for field in ("name", "description", "original_idea", "tech_stack"):
            val = getattr(data, field)
            if val is not None and val != getattr(p, field):
                setattr(p, field, val)
                changed.append(field.replace("_", " "))
        if data.config is not None and data.config.model_dump() != p.config:
            p.config = data.config.model_dump()
            changed.append("configuration")
        if data.tags is not None:
            new = get_or_create_tags(self.db, data.tags)
            if [t.name for t in new] != [t.name for t in p.tags]:
                p.tags = new
                changed.append("tags")
        if changed:
            p.revision += 1
            touch(p)
            add_event(self.db, p.id, "updated", "Updated " + ", ".join(changed))
        self.db.commit()
        return p

    def duplicate(self, project_id: str) -> Project:
        src = self.get(project_id)
        p = Project(
            name=f"{src.name} (copy)"[:200],
            description=src.description,
            original_idea=src.original_idea,
            tech_stack=src.tech_stack,
            config=dict(src.config),
        )
        p.tags = list(src.tags)
        self.db.add(p)
        self.db.flush()
        for r in src.requirements:
            self.db.add(
                Requirement(
                    project_id=p.id, kind=r.kind, text=r.text, status=r.status, source=r.source, position=r.position
                )
            )
        add_event(self.db, p.id, "created", f"Duplicated from '{src.name}'")
        add_event(self.db, src.id, "duplicated", f"Duplicated as '{p.name}'")
        self.db.commit()
        self.db.refresh(p)
        return p

    def set_archived(self, project_id: str, archived: bool) -> Project:
        p = self.get(project_id)
        if p.archived != archived:
            p.archived = archived
            p.revision += 1
            touch(p)
            add_event(
                self.db,
                p.id,
                "archived" if archived else "restored",
                "Project archived" if archived else "Project restored from archive",
            )
            self.db.commit()
        return p

    def delete(self, project_id: str) -> None:
        p = self.get(project_id)
        self.db.delete(p)
        self.db.commit()

    # ------------------------------------------------------------------ requirements
    def add_requirement(
        self,
        project_id: str,
        data: schemas.RequirementCreate,
        source: str = "user",
        recommendation_id: str | None = None,
        commit: bool = True,
    ) -> Requirement:
        p = self.get(project_id)
        pos = (self.db.scalar(select(func.max(Requirement.position)).where(Requirement.project_id == p.id)) or 0) + 1
        r = Requirement(
            project_id=p.id,
            kind=data.kind,
            text=data.text,
            status=data.status,
            source=source,
            recommendation_id=recommendation_id,
            position=pos,
        )
        self.db.add(r)
        touch(p)
        add_event(
            self.db, p.id, "requirement_added", f"Added {data.kind} requirement ({data.status}): {data.text[:80]}"
        )
        if commit:
            self.db.commit()
        return r

    def get_requirement(self, req_id: str) -> Requirement:
        r = self.db.get(Requirement, req_id)
        if r is None:
            raise not_found("Requirement")
        return r

    def update_requirement(self, req_id: str, data: schemas.RequirementUpdate) -> Requirement:
        r = self.get_requirement(req_id)
        changes = []
        for field in ("kind", "text", "status"):
            val = getattr(data, field)
            if val is not None and val != getattr(r, field):
                changes.append(f"{field} → {val[:60]}" if field != "text" else "text edited")
                setattr(r, field, val)
        if changes:
            r.updated_at = utcnow()
            touch(r.project)
            add_event(self.db, r.project_id, "requirement_updated", f"Requirement updated: {', '.join(changes)}")
        self.db.commit()
        return r

    def delete_requirement(self, req_id: str) -> None:
        r = self.get_requirement(req_id)
        add_event(self.db, r.project_id, "requirement_deleted", f"Deleted {r.kind} requirement: {r.text[:80]}")
        touch(r.project)
        self.db.delete(r)
        self.db.commit()

    # ------------------------------------------------------------------ spec / bundles
    def to_spec(self, project: Project) -> ProjectSpec:
        return ProjectSpec(
            name=project.name,
            description=project.description,
            idea=project.original_idea,
            tech_stack=project.tech_stack,
            config=PromptConfig(**(project.config or {})),
            requirements=[
                SpecRequirement(id=r.id, kind=r.kind, text=r.text, status=r.status) for r in project.requirements
            ],
        )

    def snapshot(self, project: Project) -> dict[str, Any]:
        """Everything needed to reproduce a prompt generation."""
        return {
            "project_id": project.id,
            "project_revision": project.revision,
            "name": project.name,
            "idea": project.original_idea,
            "description": project.description,
            "tech_stack": project.tech_stack,
            "config": project.config,
            "requirements": [
                {"id": r.id, "kind": r.kind, "text": r.text, "status": r.status}
                for r in project.requirements
                if r.status != "rejected"
            ],
            "rejected_requirement_ids": [r.id for r in project.requirements if r.status == "rejected"],
        }

    def export_bundle(self, project_id: str) -> dict[str, Any]:
        p = self.get(project_id)
        recs = self.db.scalars(select(Recommendation).where(Recommendation.project_id == p.id))
        prompts = self.db.scalars(select(Prompt).where(Prompt.project_id == p.id))
        bundle_prompts = []
        for pr in prompts:
            versions = self.db.scalars(
                select(PromptVersion).where(PromptVersion.prompt_id == pr.id).order_by(PromptVersion.number)
            )
            bundle_prompts.append(
                {
                    "title": pr.title,
                    "category": pr.category,
                    "target_agent": pr.target_agent,
                    "favorite": pr.favorite,
                    "tags": [t.name for t in pr.tags],
                    "versions": [
                        {
                            "number": v.number,
                            "content": v.content,
                            "variant": v.variant,
                            "profile_id": v.profile_id,
                            "profile_version": v.profile_version,
                            "generator": v.generator,
                            "model": v.model,
                            "change_summary": v.change_summary,
                            "source_snapshot": v.source_snapshot,
                        }
                        for v in versions
                    ],
                }
            )
        return {
            "format": "prompt-studio-project",
            "format_version": 1,
            "exported_at": datetime.now(UTC).isoformat(),
            "project": {
                "name": p.name,
                "description": p.description,
                "original_idea": p.original_idea,
                "tech_stack": p.tech_stack,
                "config": p.config,
                "tags": [t.name for t in p.tags],
                "requirements": [
                    {"kind": r.kind, "text": r.text, "status": r.status, "source": r.source} for r in p.requirements
                ],
                "recommendations": [
                    {
                        k: getattr(r, k)
                        for k in (
                            "fingerprint",
                            "engine",
                            "model",
                            "title",
                            "problem",
                            "rationale",
                            "proposal",
                            "benefits",
                            "tradeoffs",
                            "complexity",
                            "dependencies",
                            "disadvantages",
                            "verification",
                            "requirement_kind",
                            "requirement_text",
                            "alternatives",
                            "status",
                        )
                    }
                    for r in recs
                ],
                "prompts": bundle_prompts,
            },
        }

    def import_bundle(self, bundle: schemas.ProjectBundle) -> Project:
        """Import with fresh IDs inside one transaction. Nothing is written on failure."""
        b = bundle.project
        try:
            p = Project(
                name=b.name,
                description=b.description,
                original_idea=b.original_idea,
                tech_stack=b.tech_stack,
                config=b.config.model_dump(),
            )
            p.tags = get_or_create_tags(self.db, b.tags)
            self.db.add(p)
            self.db.flush()
            for i, r in enumerate(b.requirements):
                self.db.add(
                    Requirement(
                        project_id=p.id,
                        kind=r.kind,
                        text=r.text,
                        status=r.status,
                        source=r.source or "import",
                        position=i,
                    )
                )
            seen_fp: set[str] = set()
            for rec in b.recommendations:
                if rec.fingerprint in seen_fp:
                    continue
                seen_fp.add(rec.fingerprint)
                data = rec.model_dump()
                data["alternatives"] = [a.model_dump() for a in rec.alternatives]
                self.db.add(Recommendation(project_id=p.id, **data))
            for bp in b.prompts:
                pr = Prompt(
                    project_id=p.id,
                    title=bp.title,
                    category=bp.category,
                    target_agent=bp.target_agent,
                    favorite=bp.favorite,
                )
                pr.tags = get_or_create_tags(self.db, bp.tags)
                self.db.add(pr)
                self.db.flush()
                last = None
                numbers = set()
                for v in sorted(bp.versions, key=lambda x: x.number):
                    if v.number in numbers:
                        raise bad_request("Duplicate version numbers in import.", "invalid_import")
                    numbers.add(v.number)
                    last = PromptVersion(prompt_id=pr.id, parent_version_id=last.id if last else None, **v.model_dump())
                    self.db.add(last)
                    self.db.flush()
                pr.current_version_id = last.id if last else None
            add_event(
                self.db,
                p.id,
                "imported",
                f"Imported from bundle with {len(b.requirements)} requirement(s) and {len(b.prompts)} prompt(s)",
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(p)
        return p
