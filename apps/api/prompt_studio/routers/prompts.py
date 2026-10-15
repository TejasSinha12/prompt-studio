"""Routes: prompt library, versions, evaluations."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_session
from ..engine.evaluator.quality import SCORE_FORMULA, evaluate
from ..errors import bad_request, not_found
from ..services.prompt_service import EvaluationService, PromptService, to_out

router = APIRouter(prefix="/api", tags=["prompts"])
DB = Depends(get_session)


@router.get("/prompts", response_model=schemas.Page[schemas.PromptSummary])
def list_prompts(
    q: str = Query("", max_length=200),
    tag: str = Query("", max_length=50),
    category: str = Query("", max_length=40),
    favorite: bool | None = None,
    archived: Literal["false", "true", "all"] = "false",
    project_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = DB,
):
    items, total = PromptService(db).list(q, tag, category, favorite, archived, project_id, limit, offset)
    return {"items": items, "total": total}


@router.post("/prompts", response_model=schemas.PromptOut, status_code=201)
def create_prompt(data: schemas.PromptCreate, db: Session = DB):
    svc = PromptService(db)
    return svc.detail(svc.create(data).id)


@router.get("/prompts/{prompt_id}", response_model=schemas.PromptOut)
def get_prompt(prompt_id: str, db: Session = DB):
    return PromptService(db).detail(prompt_id)


@router.patch("/prompts/{prompt_id}", response_model=schemas.PromptOut)
def update_prompt(prompt_id: str, data: schemas.PromptUpdate, db: Session = DB):
    svc = PromptService(db)
    svc.update(prompt_id, data)
    return svc.detail(prompt_id)


@router.post("/prompts/{prompt_id}/duplicate", response_model=schemas.PromptOut, status_code=201)
def duplicate_prompt(prompt_id: str, db: Session = DB):
    svc = PromptService(db)
    return svc.detail(svc.duplicate(prompt_id).id)


@router.delete("/prompts/{prompt_id}", status_code=204)
def delete_prompt(prompt_id: str, confirm: bool = False, db: Session = DB):
    if not confirm:
        raise bad_request("Deleting a prompt requires confirm=true.", "confirmation_required")
    PromptService(db).delete(prompt_id)
    return Response(status_code=204)


@router.post("/prompts/{prompt_id}/versions", response_model=schemas.VersionOut, status_code=201)
def add_version(prompt_id: str, data: schemas.VersionCreate, db: Session = DB):
    return PromptService(db).add_version(prompt_id, data)


@router.get("/prompts/{prompt_id}/versions/{version_id}", response_model=schemas.VersionOut)
def get_version(prompt_id: str, version_id: str, db: Session = DB):
    v = PromptService(db).get_version(version_id)
    if v.prompt_id != prompt_id:
        raise not_found("Prompt version")
    return v


@router.post("/prompts/{prompt_id}/versions/{version_id}/restore", response_model=schemas.VersionOut, status_code=201)
def restore_version(prompt_id: str, version_id: str, db: Session = DB):
    return PromptService(db).restore(prompt_id, version_id)


@router.post("/prompt-versions/{version_id}/evaluate", response_model=schemas.EvaluationOut, status_code=201)
def evaluate_version(version_id: str, db: Session = DB):
    return to_out(EvaluationService(db).evaluate_version(version_id))


@router.get("/prompt-versions/{version_id}/evaluations", response_model=list[schemas.EvaluationOut])
def version_evaluations(version_id: str, db: Session = DB):
    PromptService(db).get_version(version_id)
    return [to_out(e) for e in EvaluationService(db).list_for_version(version_id)]


@router.get("/evaluations", response_model=list[schemas.EvaluationOut])
def recent_evaluations(limit: int = Query(50, ge=1, le=200), db: Session = DB):
    return EvaluationService(db).recent(limit)


@router.post("/evaluate-text", response_model=schemas.EvaluationOut)
def evaluate_text(data: schemas.EvaluateText):
    """Evaluate unsaved text (e.g. the live preview). Nothing is stored."""
    res = evaluate(data.content, coding=data.coding)
    return schemas.EvaluationOut(
        engine="rule_based",
        score=res.score,
        formula=SCORE_FORMULA,
        dimensions=[d.model_dump() for d in res.dimensions],
        metrics=dict(res.metrics),
    )
