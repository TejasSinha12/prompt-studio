"""AnalysisService and RecommendationService."""

from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..engine.analyzer.rules import analyze
from ..engine.recommendations.generator import RecommendationDraft, needs_edit, recommend
from ..engine.spec import FindingDraft
from ..errors import AppError, conflict, not_found
from ..models import AnalysisRun, Finding, Project, Recommendation, RecommendationEvent, utcnow
from .project_service import ProjectService, add_event, touch

_CONTENT_FIELDS = (
    "rule_id",
    "category",
    "kind",
    "title",
    "explanation",
    "severity",
    "confidence",
    "impact",
    "solution",
    "alternative",
    "verification",
)

CLARIFY_QUESTIONS: dict[str, tuple[str, str, str]] = {
    # rule_id: (question, why, suggested requirement kind)
    "REQ-001": ("What exactly should the result do, and for whom?", "The idea is too short to act on.", "goal"),
    "REQ-002": (
        "What are the key behaviours the result must have?",
        "No functional requirements are confirmed.",
        "functional",
    ),
    "ACC-001": ("How will you know the task is complete?", "No acceptance criteria exist.", "acceptance"),
    "TST-001": (
        "Which tests are expected (unit, integration, end-to-end)?",
        "No testing expectations.",
        "non_functional",
    ),
    "SEC-001": ("What security or privacy requirements apply?", "No security requirements.", "security"),
    "ERR-001": ("How should invalid input and failures be handled?", "Error handling is unspecified.", "functional"),
    "BND-001": ("What is explicitly out of scope?", "Project boundaries are not stated.", "out_of_scope"),
    "ASM-002": ("Which language, framework or stack should be used?", "The stack is unspecified.", "constraint"),
    "PRF-001": (
        "What measurable performance target applies?",
        "Performance-sensitive work lacks targets.",
        "non_functional",
    ),
    "SCL-001": (
        "What load or data volume must be supported?",
        "Scale is mentioned without a target.",
        "non_functional",
    ),
}


class AnalysisService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.projects = ProjectService(db)

    def run_rule_based(self, project_id: str) -> schemas.AnalysisOut:
        project = self.projects.get(project_id)
        start = time.perf_counter()
        drafts = analyze(self.projects.to_spec(project))
        run = AnalysisRun(project_id=project.id, engine="rule_based", status="completed", finding_count=len(drafts))
        self.db.add(run)
        self.db.flush()
        new, resolved = self.store_findings(project, drafts, "rule_based", None, run, resolve_missing=True)
        new_recs = RecommendationService(self.db).sync(project, drafts, "rule_based", None)
        run.duration_ms = int((time.perf_counter() - start) * 1000)
        add_event(
            self.db,
            project.id,
            "analysis",
            f"Rule-based analysis: {len(drafts)} finding(s), {new} new, "
            f"{resolved} resolved, {new_recs} new recommendation(s)",
        )
        self.db.commit()
        return schemas.AnalysisOut(
            run=schemas.AnalysisRunOut.model_validate(run),
            findings=[schemas.FindingOut.model_validate(f) for f in self.list_findings(project.id)],
            new_findings=new,
            resolved_findings=resolved,
            new_recommendations=new_recs,
        )

    def store_findings(
        self,
        project: Project,
        drafts: list[FindingDraft],
        engine: str,
        model: str | None,
        run: AnalysisRun,
        resolve_missing: bool,
    ) -> tuple[int, int]:
        """Upsert findings by fingerprint, preserving user-set status."""
        existing = {
            f.fingerprint: f
            for f in self.db.scalars(select(Finding).where(Finding.project_id == project.id, Finding.engine == engine))
        }
        new = resolved = 0
        seen = set()
        for d in drafts:
            seen.add(d.fingerprint)
            f = existing.get(d.fingerprint)
            evidence = [e.model_dump() for e in d.evidence]
            if f is None:
                f = Finding(
                    project_id=project.id,
                    fingerprint=d.fingerprint,
                    engine=engine,
                    model=model,
                    run_id=run.id,
                    evidence=evidence,
                    **{k: getattr(d, k) for k in _CONTENT_FIELDS},
                )
                self.db.add(f)
                new += 1
            else:
                for k in _CONTENT_FIELDS:
                    setattr(f, k, getattr(d, k))
                f.evidence = evidence
                f.run_id = run.id
                f.model = model
                if f.status == "resolved":
                    f.status = "open"  # the issue came back
                f.updated_at = utcnow()
        if resolve_missing:
            for fp, f in existing.items():
                if fp not in seen and f.status in {"open", "acknowledged"}:
                    f.status = "resolved"
                    f.updated_at = utcnow()
                    resolved += 1
        self.db.flush()
        return new, resolved

    def list_findings(self, project_id: str, status: str | None = None) -> list[Finding]:
        stmt = select(Finding).where(Finding.project_id == project_id)
        if status:
            stmt = stmt.where(Finding.status == status)
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        items = list(self.db.scalars(stmt))
        return sorted(
            items,
            key=lambda f: (f.status == "resolved", f.status == "dismissed", order.get(f.severity, 9), f.created_at),
        )

    def list_runs(self, project_id: str, limit: int = 20) -> list[AnalysisRun]:
        return list(
            self.db.scalars(
                select(AnalysisRun)
                .where(AnalysisRun.project_id == project_id)
                .order_by(AnalysisRun.created_at.desc())
                .limit(limit)
            )
        )

    def update_finding(self, finding_id: str, data: schemas.FindingUpdate) -> Finding:
        f = self.db.get(Finding, finding_id)
        if f is None:
            raise not_found("Finding")
        f.status = data.status
        f.updated_at = utcnow()
        add_event(self.db, f.project_id, "finding", f"Finding '{f.title[:60]}' marked {data.status}")
        self.db.commit()
        return f

    def clarifications(self, project_id: str) -> list[schemas.ClarificationQuestion]:
        self.projects.get(project_id)
        out = []
        for f in self.list_findings(project_id, status="open"):
            if f.engine == "rule_based" and f.rule_id in CLARIFY_QUESTIONS:
                q, why, kind = CLARIFY_QUESTIONS[f.rule_id]
                out.append(
                    schemas.ClarificationQuestion(
                        id=f.fingerprint, question=q, why=why, suggested_kind=kind, source="rule_based", finding_id=f.id
                    )
                )
            elif f.kind == "unresolved_question":
                out.append(
                    schemas.ClarificationQuestion(
                        id=f.fingerprint,
                        question=f"Resolve: {f.evidence[0]['quote'] if f.evidence else f.title}",
                        why=f.explanation,
                        suggested_kind="constraint",
                        source=f.engine,
                        finding_id=f.id,
                    )
                )
        return out

    def answer_clarification(self, project_id: str, data: schemas.ClarificationAnswer):
        req = self.projects.add_requirement(
            project_id,
            schemas.RequirementCreate(kind=data.kind, text=data.answer, status="confirmed"),
            source="clarification",
            commit=False,
        )
        add_event(self.db, project_id, "clarification", f"Answered: {data.question[:80]}")
        self.db.commit()
        return req


class RecommendationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def sync(
        self,
        project: Project,
        drafts: list[FindingDraft],
        engine: str,
        model: str | None,
        extra: list[RecommendationDraft] | None = None,
    ) -> int:
        """Create recommendations for new fingerprints only. Rejected ones are never re-proposed."""
        existing = set(
            self.db.scalars(select(Recommendation.fingerprint).where(Recommendation.project_id == project.id))
        )
        findings = {
            f.fingerprint: f.id for f in self.db.scalars(select(Finding).where(Finding.project_id == project.id))
        }
        recs = [r for r in (recommend(d) for d in drafts) if r is not None] + (extra or [])
        created = 0
        for r in recs:
            if r.fingerprint in existing:
                continue
            existing.add(r.fingerprint)
            data = r.model_dump()
            data["alternatives"] = [a.model_dump() for a in r.alternatives]
            rec = Recommendation(
                project_id=project.id, finding_id=findings.get(r.fingerprint), engine=engine, model=model, **data
            )
            rec.events = [
                RecommendationEvent(
                    from_status=None,
                    to_status="proposed",
                    note=f"Generated by {'rule-based analysis' if engine == 'rule_based' else 'local AI (' + (model or '?') + ')'}",
                )
            ]
            self.db.add(rec)
            created += 1
        self.db.flush()
        return created

    def list(self, project_id: str, status: str | None = None) -> list[Recommendation]:
        stmt = select(Recommendation).where(Recommendation.project_id == project_id)
        if status:
            stmt = stmt.where(Recommendation.status == status)
        return list(self.db.scalars(stmt.order_by(Recommendation.created_at)))

    def get(self, rec_id: str) -> Recommendation:
        r = self.db.get(Recommendation, rec_id)
        if r is None:
            raise not_found("Recommendation")
        return r

    def _transition(self, rec: Recommendation, to: str, allowed_from: set[str], note: str) -> None:
        if rec.status not in allowed_from:
            raise conflict(f"Cannot change a {rec.status} recommendation to {to}.", status=rec.status)
        rec.events.append(RecommendationEvent(from_status=rec.status, to_status=to, note=note))
        rec.status = to
        rec.updated_at = utcnow()

    def approve(self, rec_id: str, data: schemas.RecommendationApprove) -> Recommendation:
        rec = self.get(rec_id)
        text, kind = rec.requirement_text, rec.requirement_kind
        note = data.note
        if data.alternative_index is not None:
            if data.alternative_index >= len(rec.alternatives):
                raise AppError(400, "bad_request", "Alternative index out of range.")
            alt = rec.alternatives[data.alternative_index]
            text = alt["requirement_text"]
            note = (note + " " if note else "") + f"Chose alternative: {alt['title']}"
        if data.requirement_text:
            if data.requirement_text != text:
                note = (note + " " if note else "") + "Requirement text edited before approval."
            text = data.requirement_text
        if data.requirement_kind:
            kind = data.requirement_kind
        if needs_edit(text):
            raise AppError(
                400, "needs_edit", "Replace the [bracketed placeholder] with your decision before approving."
            )
        self._transition(rec, "approved", {"proposed", "deferred"}, note)
        project = self.db.get(Project, rec.project_id)
        assert project is not None
        ProjectService(self.db).add_requirement(
            project.id,
            schemas.RequirementCreate(kind=kind, text=text, status="confirmed"),
            source="recommendation",
            recommendation_id=rec.id,
            commit=False,
        )
        if rec.finding_id:
            f = self.db.get(Finding, rec.finding_id)
            if f and f.status == "open":
                f.status = "acknowledged"
        add_event(self.db, project.id, "recommendation", f"Approved recommendation: {rec.title[:80]}")
        touch(project)
        self.db.commit()
        return rec

    def reject(self, rec_id: str, note: str) -> Recommendation:
        rec = self.get(rec_id)
        self._transition(rec, "rejected", {"proposed", "deferred"}, note)
        add_event(self.db, rec.project_id, "recommendation", f"Rejected recommendation: {rec.title[:80]}")
        self.db.commit()
        return rec

    def defer(self, rec_id: str, note: str) -> Recommendation:
        rec = self.get(rec_id)
        self._transition(rec, "deferred", {"proposed"}, note)
        add_event(self.db, rec.project_id, "recommendation", f"Deferred recommendation: {rec.title[:80]}")
        self.db.commit()
        return rec

    def restore(self, rec_id: str, note: str) -> Recommendation:
        rec = self.get(rec_id)
        self._transition(rec, "proposed", {"rejected", "deferred"}, note or "Restored for reconsideration")
        add_event(self.db, rec.project_id, "recommendation", f"Restored recommendation: {rec.title[:80]}")
        self.db.commit()
        return rec

    def edit(self, rec_id: str, data: schemas.RecommendationEdit) -> Recommendation:
        rec = self.get(rec_id)
        if rec.status not in {"proposed", "deferred"}:
            raise conflict("Only proposed or deferred recommendations can be edited.")
        changes = []
        if data.requirement_text and data.requirement_text != rec.requirement_text:
            changes.append(f"text was: {rec.requirement_text[:200]}")
            rec.requirement_text = data.requirement_text
        if data.requirement_kind and data.requirement_kind != rec.requirement_kind:
            changes.append(f"kind was: {rec.requirement_kind}")
            rec.requirement_kind = data.requirement_kind
        if data.proposal and data.proposal != rec.proposal:
            changes.append("proposal edited")
            rec.proposal = data.proposal
        if changes:
            rec.events.append(
                RecommendationEvent(from_status=rec.status, to_status=rec.status, note="Edited; " + "; ".join(changes))
            )
            rec.updated_at = utcnow()
        self.db.commit()
        return rec


def rec_out(rec: Recommendation) -> schemas.RecommendationOut:
    out = schemas.RecommendationOut.model_validate(rec)
    out.needs_edit = needs_edit(rec.requirement_text)
    return out
