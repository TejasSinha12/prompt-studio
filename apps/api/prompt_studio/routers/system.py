"""Routes: health, dashboard, settings, local models, AI jobs, backups, data, templates."""

from __future__ import annotations

import os
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import __version__, schemas
from ..config import get_settings
from ..db import get_session
from ..engine.export.renderers import FORMATS
from ..engine.templates.profiles import PROFILES
from ..models import Finding, Project, Prompt, PromptVersion, Recommendation
from ..providers.base import ProviderError
from ..services.ai_service import JobManager, LocalModelService, model_list_payload
from ..services.backup_service import BackupService, PrivacyService
from ..services.codebase_service import ScanLimits, scan, summarize
from ..services.settings_service import SettingsService
from ..services.template_service import TemplateService

router = APIRouter(prefix="/api", tags=["system"])
DB = Depends(get_session)


def jobs(request: Request) -> JobManager:
    return request.app.state.jobs


def models_service(request: Request) -> LocalModelService:
    return request.app.state.local_models


@router.get("/health")
def health(db: Session = DB):
    db.execute(select(1))
    return {"status": "ok", "version": __version__, "database": "ok", "network_policy": "loopback-only"}


@router.get("/dashboard")
def dashboard(db: Session = DB):
    recent = list(
        db.scalars(select(Project).where(Project.archived.is_(False)).order_by(Project.updated_at.desc()).limit(6))
    )
    review = db.execute(
        select(Project.id, Project.name, func.count(Recommendation.id))
        .join(Recommendation, Recommendation.project_id == Project.id)
        .where(Recommendation.status == "proposed", Project.archived.is_(False))
        .group_by(Project.id)
        .order_by(func.count(Recommendation.id).desc())
        .limit(6)
    ).all()
    versions = db.execute(
        select(PromptVersion, Prompt.title)
        .join(Prompt, PromptVersion.prompt_id == Prompt.id)
        .order_by(PromptVersion.created_at.desc())
        .limit(6)
    ).all()
    findings = db.execute(
        select(Finding, Project.name)
        .join(Project, Finding.project_id == Project.id)
        .where(Finding.status == "open", Finding.severity.in_(["critical", "high", "medium"]))
        .order_by(Finding.updated_at.desc())
        .limit(6)
    ).all()
    return {
        "counts": {
            "projects": db.scalar(select(func.count()).select_from(Project).where(Project.archived.is_(False))) or 0,
            "archived_projects": db.scalar(select(func.count()).select_from(Project).where(Project.archived.is_(True)))
            or 0,
            "prompts": db.scalar(select(func.count()).select_from(Prompt)) or 0,
            "versions": db.scalar(select(func.count()).select_from(PromptVersion)) or 0,
        },
        "recent_projects": [schemas.ProjectSummary.model_validate(p).model_dump() for p in recent],
        "needs_review": [
            {"project_id": pid, "project_name": name, "proposed_recommendations": n} for pid, name, n in review
        ],
        "recent_versions": [
            {
                "id": v.id,
                "prompt_id": v.prompt_id,
                "prompt_title": t,
                "number": v.number,
                "variant": v.variant,
                "generator": v.generator,
                "created_at": v.created_at,
            }
            for v, t in versions
        ],
        "recent_findings": [
            {
                "id": f.id,
                "project_id": f.project_id,
                "project_name": n,
                "title": f.title,
                "severity": f.severity,
                "engine": f.engine,
                "kind": f.kind,
            }
            for f, n in findings
        ],
    }


@router.get("/settings", response_model=schemas.AppSettings)
def get_app_settings(db: Session = DB):
    return SettingsService(db).get()


@router.put("/settings", response_model=schemas.AppSettings)
def put_app_settings(data: schemas.AppSettings, db: Session = DB):
    return SettingsService(db).update(data)


@router.get("/system")
def system_info():
    s = get_settings()
    mem = None
    try:
        mem = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        pass
    return {
        "data_dir": str(s.data_dir),
        "database": str(s.db_path),
        "backups_dir": str(s.backups_dir),
        "total_memory_bytes": mem,
        "api_token_enabled": bool(s.api_token),
        "version": __version__,
    }


# ----------------------------------------------------------------------------- models


@router.get("/models", response_model=schemas.ModelsOut)
async def list_models(request: Request, db: Session = DB):
    settings = SettingsService(db).get()
    provider = models_service(request).provider_factory(settings)
    status = await provider.status()
    models = []
    if status.available:
        try:
            models = await provider.list_models()
        except ProviderError as e:
            status.available, status.error, status.error_code = False, e.message, e.code
    return model_list_payload(status, models, settings.model)


@router.get("/models/details")
async def model_details(request: Request, name: str = Query(..., min_length=1, max_length=200), db: Session = DB):
    settings = SettingsService(db).get()
    provider = models_service(request).provider_factory(settings)
    try:
        return (await provider.show(name)).model_dump()
    except ProviderError as e:
        return Response(
            status_code=502,
            media_type="application/json",
            content=f'{{"error": {{"code": "{e.code}", "message": "Could not load model details."}}}}',
        )


# ----------------------------------------------------------------------------- AI jobs


@router.post("/ai/jobs", response_model=schemas.JobOut, status_code=202)
async def create_job(data: schemas.JobCreate, request: Request):
    return jobs(request).start(data).out()


@router.get("/ai/jobs", response_model=list[schemas.JobOut])
async def list_jobs(request: Request):
    return [j.out() for j in jobs(request).list()]


@router.get("/ai/jobs/{job_id}", response_model=schemas.JobOut)
async def get_job(job_id: str, request: Request):
    return jobs(request).get(job_id).out()


@router.delete("/ai/jobs/{job_id}", response_model=schemas.JobOut)
async def cancel_job(job_id: str, request: Request):
    return jobs(request).cancel(job_id).out()


# ----------------------------------------------------------------------------- backups & data


@router.get("/backups", response_model=list[schemas.BackupOut])
def list_backups():
    return BackupService().list()


@router.post("/backups", response_model=schemas.BackupOut, status_code=201)
def create_backup():
    return BackupService().create()


@router.post("/backups/{name}/validate", response_model=schemas.BackupValidation)
def validate_backup(name: str):
    return BackupService().validate(name)


@router.post("/backups/{name}/restore")
async def restore_backup(name: str, data: schemas.ConfirmBody, request: Request):
    await jobs(request).cancel_all()
    return BackupService().restore(name, data.confirm)


@router.delete("/backups/{name}", status_code=204)
def delete_backup(name: str, confirm: bool = False):
    if not confirm:
        from ..errors import bad_request

        raise bad_request("Deleting a backup requires confirm=true.", "confirmation_required")
    BackupService().delete(name)
    return Response(status_code=204)


@router.post("/data/delete-all")
def delete_all(data: schemas.ConfirmBody, db: Session = DB):
    return PrivacyService(db).delete_all(data.confirm)


# ----------------------------------------------------------------------------- codebase context (read-only)


def _limits(data: schemas.CodebaseScanRequest) -> ScanLimits:
    return ScanLimits(max_file_bytes=data.max_file_kb * 1000, extra_excludes=data.extra_excludes)


@router.post("/codebase/scan")
def codebase_scan(data: schemas.CodebaseScanRequest):
    """List files in a user-chosen directory (no contents read except dependency manifests)."""
    return scan(data.path, _limits(data)).model_dump()


@router.post("/codebase/summary")
def codebase_summary(data: schemas.CodebaseSummaryRequest):
    """Read only the selected files (within limits, secrets redacted) and return a Markdown summary."""
    return summarize(data.path, data.files, _limits(data)).model_dump()


# ----------------------------------------------------------------------------- catalogues


@router.get("/templates")
def list_templates(db: Session = DB):
    return TemplateService(db).list()


@router.post("/templates", status_code=201)
def create_template(data: schemas.TemplateIn, db: Session = DB):
    return {"id": TemplateService(db).create(data).id}


@router.put("/templates/{template_id}")
def update_template(template_id: str, data: schemas.TemplateIn, db: Session = DB):
    return {"id": TemplateService(db).update(template_id, data).id}


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(template_id: str, confirm: bool = False, db: Session = DB):
    if not confirm:
        from ..errors import bad_request

        raise bad_request("Deleting a template requires confirm=true.", "confirmation_required")
    TemplateService(db).delete(template_id)
    return Response(status_code=204)


@router.post("/projects/{project_id}/save-as-template", status_code=201)
def save_as_template(project_id: str, data: schemas.TemplateFromProject, db: Session = DB):
    return {"id": TemplateService(db).from_project(project_id, data).id}


@router.get("/profiles")
def list_profiles():
    return [p.model_dump() for p in PROFILES.values()]


@router.get("/export-formats")
def export_formats() -> list[dict[str, Any]]:
    return [{"id": k, "label": v[0], "filename": v[1]} for k, v in FORMATS.items()]


_ = Literal  # re-exported for route signatures
