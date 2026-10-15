"""SQLAlchemy ORM models. The schema is created by Alembic migrations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Stores UTC; always returns timezone-aware UTC datetimes.

    SQLite has no native timezone support, so values come back naive. Without
    this, API responses would lack an offset and browsers would misread them
    as local time.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


project_tags = Table(
    "project_tags",
    Base.metadata,
    Column("project_id", String(36), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

prompt_tags = Table(
    "prompt_tags",
    Base.metadata,
    Column("prompt_id", String(36), ForeignKey("prompts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    original_idea: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tech_stack: Mapped[str] = mapped_column(Text, default="", nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    tags: Mapped[list[Tag]] = relationship(secondary=project_tags, lazy="selectin", order_by=Tag.name)
    requirements: Mapped[list[Requirement]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Requirement.position",
    )

    __table_args__ = (Index("ix_projects_archived_updated", "archived", "updated_at"),)


class ProjectEvent(Base):
    __tablename__ = "project_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    __table_args__ = (Index("ix_project_events_project_created", "project_id", "created_at"),)


class Requirement(Base):
    __tablename__ = "requirements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="confirmed", nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="user", nullable=False)
    recommendation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="requirements")

    __table_args__ = (Index("ix_requirements_project_kind", "project_id", "kind"),)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    engine: Mapped[str] = mapped_column(String(20), nullable=False)  # rule_based | local_ai
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # completed | failed
    finding_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    __table_args__ = (Index("ix_analysis_runs_project_created", "project_id", "created_at"),)


class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True
    )
    engine: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rule_id: Mapped[str] = mapped_column(String(40), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    impact: Mapped[str] = mapped_column(Text, default="", nullable=False)
    solution: Mapped[str] = mapped_column(Text, default="", nullable=False)
    alternative: Mapped[str] = mapped_column(Text, default="", nullable=False)
    verification: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "fingerprint", name="uq_findings_project_fingerprint"),
        Index("ix_findings_project_status", "project_id", "status"),
    )


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    finding_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    engine: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    problem: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    proposal: Mapped[str] = mapped_column(Text, nullable=False)
    benefits: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tradeoffs: Mapped[str] = mapped_column(Text, default="", nullable=False)
    complexity: Mapped[str] = mapped_column(String(20), default="low", nullable=False)
    dependencies: Mapped[str] = mapped_column(Text, default="", nullable=False)
    disadvantages: Mapped[str] = mapped_column(Text, default="", nullable=False)
    verification: Mapped[str] = mapped_column(Text, default="", nullable=False)
    requirement_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    alternatives: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="proposed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    events: Mapped[list[RecommendationEvent]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RecommendationEvent.created_at",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("project_id", "fingerprint", name="uq_recommendations_project_fingerprint"),
        Index("ix_recommendations_project_status", "project_id", "status"),
    )


class RecommendationEvent(Base):
    __tablename__ = "recommendation_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recommendation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class Prompt(Base):
    __tablename__ = "prompts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="general", nullable=False)
    target_agent: Mapped[str] = mapped_column(String(40), default="generic_coding", nullable=False)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    tags: Mapped[list[Tag]] = relationship(secondary=prompt_tags, lazy="selectin", order_by=Tag.name)

    __table_args__ = (
        Index("ix_prompts_project", "project_id"),
        Index("ix_prompts_archived_updated", "archived", "updated_at"),
    )


class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    prompt_id: Mapped[str] = mapped_column(String(36), ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variant: Mapped[str] = mapped_column(String(20), nullable=False)
    profile_id: Mapped[str] = mapped_column(String(40), nullable=False)
    profile_version: Mapped[str] = mapped_column(String(20), nullable=False)
    generator: Mapped[str] = mapped_column(String(20), nullable=False)  # rule_based | local_ai | manual
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    parent_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("prompt_id", "number", name="uq_prompt_versions_number"),)


class Evaluation(Base):
    __tablename__ = "evaluations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    prompt_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("prompt_versions.id", ondelete="CASCADE"), nullable=False
    )
    engine: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    dimensions: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    __table_args__ = (Index("ix_evaluations_version", "prompt_version_id", "created_at"),)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
