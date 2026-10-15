"""Routes: projects, requirements, analysis, recommendations, generation, export."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_session
from ..engine.export.renderers import render, render_zip
from ..engine.optimizer.builder import build_prompt, check_preservation
from ..errors import AppError, bad_request
from ..services import handoff_service
from ..services.analysis_service import AnalysisService, RecommendationService, rec_out
from ..services.project_service import ProjectService
from ..services.prompt_service import PromptService

router = APIRouter(prefix="/api", tags=["projects"])
DB = Depends(get_session)


# ----------------------------------------------------------------------------- projects


@router.get("/projects", response_model=schemas.Page[schemas.ProjectSummary])
def list_projects(
    q: str = Query("", max_length=200),
    tag: str = Query("", max_length=50),
    archived: Literal["false", "true", "all"] = "false",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = DB,
):
    items, total = ProjectService(db).list(q, tag, archived, limit, offset)
    return {"items": items, "total": total}


@router.post("/projects", response_model=schemas.ProjectOut, status_code=201)
def create_project(data: schemas.ProjectCreate, db: Session = DB):
    return ProjectService(db).create(data)


@router.post("/projects/from-template", response_model=schemas.ProjectOut, status_code=201)
def create_from_template(data: schemas.ProjectFromTemplate, db: Session = DB):
    return ProjectService(db).create_from_template(data)


@router.post("/projects/import", response_model=schemas.ProjectOut, status_code=201)
def import_project(bundle: schemas.ProjectBundle, db: Session = DB):
    return ProjectService(db).import_bundle(bundle)


@router.get("/projects/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: str, db: Session = DB):
    return ProjectService(db).get(project_id)


@router.patch("/projects/{project_id}", response_model=schemas.ProjectOut)
def update_project(project_id: str, data: schemas.ProjectUpdate, db: Session = DB):
    return ProjectService(db).update(project_id, data)


@router.post("/projects/{project_id}/duplicate", response_model=schemas.ProjectOut, status_code=201)
def duplicate_project(project_id: str, db: Session = DB):
    return ProjectService(db).duplicate(project_id)


@router.post("/projects/{project_id}/archive", response_model=schemas.ProjectOut)
def archive_project(project_id: str, db: Session = DB):
    return ProjectService(db).set_archived(project_id, True)


@router.post("/projects/{project_id}/restore", response_model=schemas.ProjectOut)
def restore_project(project_id: str, db: Session = DB):
    return ProjectService(db).set_archived(project_id, False)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, confirm: bool = False, db: Session = DB):
    if not confirm:
        raise bad_request("Deleting a project requires confirm=true.", "confirmation_required")
    ProjectService(db).delete(project_id)
    return Response(status_code=204)


@router.get("/projects/{project_id}/events", response_model=list[schemas.ProjectEventOut])
def project_events(project_id: str, limit: int = Query(100, ge=1, le=500), db: Session = DB):
    return ProjectService(db).events(project_id, limit)


@router.get("/projects/{project_id}/bundle")
def export_bundle(project_id: str, db: Session = DB):
    return ProjectService(db).export_bundle(project_id)


# ----------------------------------------------------------------------------- requirements


@router.post("/projects/{project_id}/requirements", response_model=schemas.RequirementOut, status_code=201)
def add_requirement(project_id: str, data: schemas.RequirementCreate, db: Session = DB):
    return ProjectService(db).add_requirement(project_id, data)


@router.patch("/requirements/{req_id}", response_model=schemas.RequirementOut)
def update_requirement(req_id: str, data: schemas.RequirementUpdate, db: Session = DB):
    return ProjectService(db).update_requirement(req_id, data)


@router.delete("/requirements/{req_id}", status_code=204)
def delete_requirement(req_id: str, db: Session = DB):
    ProjectService(db).delete_requirement(req_id)
    return Response(status_code=204)


# ----------------------------------------------------------------------------- analysis


@router.post("/projects/{project_id}/analysis", response_model=schemas.AnalysisOut)
def run_analysis(project_id: str, db: Session = DB):
    """Rule-based analysis. Local-AI analysis runs as a job: POST /api/ai/jobs {kind: analysis}."""
    return AnalysisService(db).run_rule_based(project_id)


@router.get("/projects/{project_id}/findings", response_model=list[schemas.FindingOut])
def list_findings(project_id: str, status: str | None = Query(None, max_length=20), db: Session = DB):
    ProjectService(db).get(project_id)
    return AnalysisService(db).list_findings(project_id, status)


@router.get("/projects/{project_id}/analysis-runs", response_model=list[schemas.AnalysisRunOut])
def list_runs(project_id: str, db: Session = DB):
    ProjectService(db).get(project_id)
    return AnalysisService(db).list_runs(project_id)


@router.patch("/findings/{finding_id}", response_model=schemas.FindingOut)
def update_finding(finding_id: str, data: schemas.FindingUpdate, db: Session = DB):
    return AnalysisService(db).update_finding(finding_id, data)


@router.get("/projects/{project_id}/clarifications", response_model=list[schemas.ClarificationQuestion])
def clarifications(project_id: str, db: Session = DB):
    return AnalysisService(db).clarifications(project_id)


@router.post("/projects/{project_id}/clarifications", response_model=schemas.RequirementOut, status_code=201)
def answer_clarification(project_id: str, data: schemas.ClarificationAnswer, db: Session = DB):
    return AnalysisService(db).answer_clarification(project_id, data)


# ----------------------------------------------------------------------------- recommendations


@router.get("/projects/{project_id}/recommendations", response_model=list[schemas.RecommendationOut])
def list_recommendations(project_id: str, status: str | None = Query(None, max_length=20), db: Session = DB):
    ProjectService(db).get(project_id)
    return [rec_out(r) for r in RecommendationService(db).list(project_id, status)]


@router.post("/recommendations/{rec_id}/approve", response_model=schemas.RecommendationOut)
def approve(rec_id: str, data: schemas.RecommendationApprove, db: Session = DB):
    return rec_out(RecommendationService(db).approve(rec_id, data))


@router.post("/recommendations/{rec_id}/reject", response_model=schemas.RecommendationOut)
def reject(rec_id: str, data: schemas.RecommendationNote, db: Session = DB):
    return rec_out(RecommendationService(db).reject(rec_id, data.note))


@router.post("/recommendations/{rec_id}/defer", response_model=schemas.RecommendationOut)
def defer(rec_id: str, data: schemas.RecommendationNote, db: Session = DB):
    return rec_out(RecommendationService(db).defer(rec_id, data.note))


@router.post("/recommendations/{rec_id}/restore", response_model=schemas.RecommendationOut)
def restore(rec_id: str, data: schemas.RecommendationNote, db: Session = DB):
    return rec_out(RecommendationService(db).restore(rec_id, data.note))


@router.patch("/recommendations/{rec_id}", response_model=schemas.RecommendationOut)
def edit_recommendation(rec_id: str, data: schemas.RecommendationEdit, db: Session = DB):
    return rec_out(RecommendationService(db).edit(rec_id, data))


# ----------------------------------------------------------------------------- generation & export


@router.post("/projects/{project_id}/generate", response_model=schemas.GenerateOut)
def generate(project_id: str, data: schemas.GenerateRequest, db: Session = DB):
    svc = ProjectService(db)
    spec = svc.to_spec(svc.get(project_id))
    return {"results": [build_prompt(spec, v, data.profile_id).model_dump() for v in data.variants]}


@router.post("/projects/{project_id}/preservation", response_model=list[schemas.PreservationOut])
def preservation(project_id: str, data: schemas.PreservationCheckRequest, db: Session = DB):
    svc = ProjectService(db)
    return [p.model_dump() for p in check_preservation(data.content, svc.to_spec(svc.get(project_id)))]


def _export_content(db: Session, project_id: str, content: str | None, version_id: str | None) -> str | None:
    if version_id:
        v = PromptService(db).get_version(version_id)
        prompt = PromptService(db).get(v.prompt_id)
        if prompt.project_id != project_id:
            raise AppError(404, "not_found", "Prompt version not found for this project.")
        return v.content
    return content


@router.post("/projects/{project_id}/export", response_model=schemas.ExportFileOut)
def export(project_id: str, data: schemas.ExportRequest, db: Session = DB):
    svc = ProjectService(db)
    project = svc.get(project_id)
    content = _export_content(db, project_id, data.content, data.version_id)
    if data.format in {"markdown", "text", "template"} and not content:
        content = build_prompt(svc.to_spec(project), "balanced").content
    return render(data.format, svc.to_spec(project), content).model_dump()


@router.post("/projects/{project_id}/export.zip")
def export_zip(project_id: str, data: schemas.ExportZipRequest, db: Session = DB):
    svc = ProjectService(db)
    project = svc.get(project_id)
    content = (
        _export_content(db, project_id, data.content, data.version_id)
        or build_prompt(svc.to_spec(project), "balanced").content
    )
    payload = render_zip(svc.to_spec(project), content, list(dict.fromkeys(data.formats)))
    return Response(
        payload,
        media_type="application/zip",
        headers={"content-disposition": 'attachment; filename="prompt-studio-export.zip"'},
    )


# ----------------------------------------------------------------------------- agent handoff (explicit, no execution)


def _handoff_inputs(db: Session, project_id: str, data: schemas.HandoffRequest):
    svc = ProjectService(db)
    project = svc.get(project_id)
    spec = svc.to_spec(project)
    prompt = _export_content(db, project_id, data.content, data.version_id) or build_prompt(spec, "balanced").content
    return spec, prompt


@router.post("/projects/{project_id}/handoff/preview")
def handoff_preview(project_id: str, data: schemas.HandoffRequest, db: Session = DB):
    """Show which files would be written. Writes nothing."""
    spec, prompt = _handoff_inputs(db, project_id, data)
    return handoff_service.plan(data.path, data.profile_id, spec, prompt).model_dump()


@router.post("/projects/{project_id}/handoff/write")
def handoff_write(project_id: str, data: schemas.HandoffWriteRequest, db: Session = DB):
    """Write the previewed files after explicit confirmation. Never executes anything."""
    spec, prompt = _handoff_inputs(db, project_id, data)
    result = handoff_service.write(data.path, data.profile_id, spec, prompt, data.overwrite, data.confirm)
    from ..services.project_service import add_event

    add_event(
        db, project_id, "handoff", f"Wrote {len(result['written'])} file(s) to {result['root']} for {data.profile_id}"
    )
    db.commit()
    return result
