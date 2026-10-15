"""Task templates: built-in (read-only, in code) and custom (user-defined, in the database)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..engine.spec import PromptConfig
from ..engine.templates.task_templates import TEMPLATES, TEMPLATES_BY_ID, TaskTemplate, TemplateRequirement
from ..errors import not_found
from ..models import CustomTemplate, utcnow
from .project_service import ProjectService


def _custom_to_template(t: CustomTemplate) -> TaskTemplate:
    return TaskTemplate(
        id=t.id,
        name=t.name,
        description=t.description,
        category=t.category,
        idea=t.idea,
        config=t.config,
        requirements=[TemplateRequirement(**r) for r in t.requirements],
    )


class TemplateService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[dict[str, Any]]:
        builtin = [t.model_dump() | {"builtin": True} for t in TEMPLATES]
        custom = [
            _custom_to_template(t).model_dump() | {"builtin": False, "updated_at": t.updated_at}
            for t in self.db.scalars(select(CustomTemplate).order_by(CustomTemplate.name))
        ]
        return builtin + custom

    def resolve(self, template_id: str) -> TaskTemplate:
        if template_id in TEMPLATES_BY_ID:
            return TEMPLATES_BY_ID[template_id]
        t = self.db.get(CustomTemplate, template_id)
        if t is None:
            raise not_found("Template")
        return _custom_to_template(t)

    def _get_custom(self, template_id: str) -> CustomTemplate:
        if template_id in TEMPLATES_BY_ID:
            raise schemas_error_builtin()
        t = self.db.get(CustomTemplate, template_id)
        if t is None:
            raise not_found("Template")
        return t

    def create(self, data: schemas.TemplateIn) -> CustomTemplate:
        t = CustomTemplate(
            name=data.name,
            description=data.description,
            category=data.category,
            idea=data.idea,
            config=_clean_config(data.config),
            requirements=[r.model_dump() for r in data.requirements],
        )
        self.db.add(t)
        self.db.commit()
        return t

    def update(self, template_id: str, data: schemas.TemplateIn) -> CustomTemplate:
        t = self._get_custom(template_id)
        t.name, t.description, t.category, t.idea = data.name, data.description, data.category, data.idea
        t.config = _clean_config(data.config)
        t.requirements = [r.model_dump() for r in data.requirements]
        t.updated_at = utcnow()
        self.db.commit()
        return t

    def delete(self, template_id: str) -> None:
        self.db.delete(self._get_custom(template_id))
        self.db.commit()

    def from_project(self, project_id: str, data: schemas.TemplateFromProject) -> CustomTemplate:
        p = ProjectService(self.db).get(project_id)
        reqs = [
            {"kind": r.kind, "text": r.text}
            for r in p.requirements
            if r.status == "confirmed" and r.kind != "assumption"
        ][:100]
        config = {k: v for k, v in (p.config or {}).items() if v and k != "existing_codebase"}
        t = CustomTemplate(
            name=data.name,
            description=data.description or p.description,
            category=config.get("task_category", "general"),
            idea=p.original_idea if data.include_idea else "",
            config=_clean_config(config),
            requirements=reqs,
        )
        self.db.add(t)
        self.db.commit()
        return t


def _clean_config(cfg: dict[str, Any]) -> dict[str, str]:
    """Keep only known PromptConfig fields with non-empty string values."""
    known = set(PromptConfig.model_fields)
    return {k: str(v) for k, v in cfg.items() if k in known and isinstance(v, str) and v}


def schemas_error_builtin():
    from ..errors import AppError

    return AppError(
        400, "builtin_template", "Built-in templates cannot be modified. Duplicate it as a custom template."
    )
