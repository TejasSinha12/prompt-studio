"""Pydantic request/response schemas for the HTTP API.

All inputs carry explicit length / size limits. Outputs use `from_attributes`
so services can return ORM objects.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationInfo, field_validator

from .engine.spec import PromptConfig

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ShortText = Annotated[str, StringConstraints(max_length=5_000)]
LongText = Annotated[str, StringConstraints(max_length=100_000)]
TagName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50, pattern=r"^[\w\- .]+$")]
ReqKind = Literal[
    "goal", "functional", "non_functional", "security", "constraint", "acceptance", "assumption", "out_of_scope"
]
ReqStatus = Literal["confirmed", "proposed", "rejected", "unresolved"]
VariantName = Literal["concise", "balanced", "detailed"]
ProfileId = Literal["claude_code", "codex", "cursor", "generic_coding", "generic_llm"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ConfigIn(PromptConfig):
    """PromptConfig with input length limits."""

    @field_validator("*", mode="before")
    @classmethod
    def _limit(cls, v: Any, info: ValidationInfo) -> Any:
        limit = 100_000 if info.field_name == "existing_codebase" else 5_000
        if isinstance(v, str) and len(v) > limit:
            raise ValueError(f"field exceeds {limit} characters")
        return v


# ----------------------------------------------------------------------------- projects


class TagOut(ORM):
    id: str
    name: str


class RequirementOut(ORM):
    id: str
    kind: str
    text: str
    status: str
    source: str
    recommendation_id: str | None
    position: int
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    name: Name
    description: ShortText = ""
    original_idea: LongText = ""
    tech_stack: ShortText = ""
    config: ConfigIn = Field(default_factory=ConfigIn)
    tags: list[TagName] = Field(default_factory=list, max_length=20)


class ProjectUpdate(BaseModel):
    revision: int
    name: Name | None = None
    description: ShortText | None = None
    original_idea: LongText | None = None
    tech_stack: ShortText | None = None
    config: ConfigIn | None = None
    tags: list[TagName] | None = Field(default=None, max_length=20)


class ProjectFromTemplate(BaseModel):
    template_id: Annotated[str, StringConstraints(max_length=60)]
    name: Name


class ProjectSummary(ORM):
    id: str
    name: str
    description: str
    archived: bool
    revision: int
    tags: list[TagOut]
    created_at: datetime
    updated_at: datetime
    task_category: str = "general"
    open_findings: int = 0
    proposed_recommendations: int = 0


class ProjectOut(ORM):
    id: str
    name: str
    description: str
    original_idea: str
    tech_stack: str
    config: PromptConfig
    archived: bool
    revision: int
    tags: list[TagOut]
    requirements: list[RequirementOut]
    created_at: datetime
    updated_at: datetime


class Page[T](BaseModel):
    items: list[T]
    total: int


class ProjectEventOut(ORM):
    id: str
    kind: str
    summary: str
    created_at: datetime


class RequirementCreate(BaseModel):
    kind: ReqKind
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5_000)]
    status: ReqStatus = "confirmed"


class RequirementUpdate(BaseModel):
    kind: ReqKind | None = None
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5_000)] | None = None
    status: ReqStatus | None = None


# ----------------------------------------------------------------------------- analysis


class EvidenceOut(BaseModel):
    source: str
    quote: str = ""
    line: int | None = None


class FindingOut(ORM):
    id: str
    fingerprint: str
    engine: str
    model: str | None
    rule_id: str
    category: str
    kind: str
    title: str
    explanation: str
    evidence: list[EvidenceOut]
    severity: str
    confidence: str
    impact: str
    solution: str
    alternative: str
    verification: str
    status: str
    created_at: datetime
    updated_at: datetime


class FindingUpdate(BaseModel):
    status: Literal["open", "acknowledged", "dismissed"]


class AnalysisRunOut(ORM):
    id: str
    engine: str
    model: str | None
    status: str
    finding_count: int
    duration_ms: int
    error: str | None
    created_at: datetime


class AnalysisOut(BaseModel):
    run: AnalysisRunOut
    findings: list[FindingOut]
    new_findings: int
    resolved_findings: int
    new_recommendations: int


class ClarificationQuestion(BaseModel):
    id: str
    question: str
    why: str
    suggested_kind: str
    source: str  # rule_based | local_ai
    finding_id: str | None = None


class ClarificationAnswer(BaseModel):
    question: Annotated[str, StringConstraints(max_length=1_000)]
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5_000)]
    kind: ReqKind


# ----------------------------------------------------------------------------- recommendations


class AlternativeOut(BaseModel):
    title: str
    requirement_text: str
    tradeoffs: str


class RecommendationEventOut(ORM):
    id: str
    from_status: str | None
    to_status: str
    note: str
    created_at: datetime


class RecommendationOut(ORM):
    id: str
    finding_id: str | None
    fingerprint: str
    engine: str
    model: str | None
    title: str
    problem: str
    rationale: str
    proposal: str
    benefits: str
    tradeoffs: str
    complexity: str
    dependencies: str
    disadvantages: str
    verification: str
    requirement_kind: str
    requirement_text: str
    alternatives: list[AlternativeOut]
    status: str
    needs_edit: bool = False
    events: list[RecommendationEventOut]
    created_at: datetime
    updated_at: datetime


class RecommendationApprove(BaseModel):
    requirement_text: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5_000)] | None
    ) = None
    requirement_kind: ReqKind | None = None
    alternative_index: int | None = Field(default=None, ge=0, le=10)
    note: Annotated[str, StringConstraints(max_length=1_000)] = ""


class RecommendationNote(BaseModel):
    note: Annotated[str, StringConstraints(max_length=1_000)] = ""


class RecommendationEdit(BaseModel):
    requirement_text: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5_000)] | None
    ) = None
    requirement_kind: ReqKind | None = None
    proposal: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5_000)] | None = None


# ----------------------------------------------------------------------------- generation


class GenerateRequest(BaseModel):
    variants: list[VariantName] = Field(
        default_factory=lambda: ["concise", "balanced", "detailed"], min_length=1, max_length=3
    )
    profile_id: ProfileId | None = None


class SectionOut(BaseModel):
    id: str
    title: str
    source: str


class PreservationOut(BaseModel):
    requirement_id: str
    kind: str
    text: str
    preserved: bool
    coverage: float


class BuildOut(BaseModel):
    variant: str
    profile_id: str
    profile_version: str
    content: str
    sections: list[SectionOut]
    preservation: list[PreservationOut]
    warnings: list[str]
    char_count: int
    word_count: int
    token_estimate: int
    generator: str = "rule_based"


class GenerateOut(BaseModel):
    results: list[BuildOut]


class PreservationCheckRequest(BaseModel):
    content: LongText


# ----------------------------------------------------------------------------- prompts


class PromptCreate(BaseModel):
    project_id: str | None = None
    title: Name
    category: Annotated[str, StringConstraints(max_length=40)] = "general"
    target_agent: ProfileId = "generic_coding"
    tags: list[TagName] = Field(default_factory=list, max_length=20)
    content: LongText
    variant: Literal["concise", "balanced", "detailed", "manual"] = "manual"
    generator: Literal["rule_based", "local_ai", "manual"] = "manual"
    model: Annotated[str, StringConstraints(max_length=200)] | None = None
    change_summary: Annotated[str, StringConstraints(max_length=1_000)] = ""


class VersionCreate(BaseModel):
    content: LongText
    variant: Literal["concise", "balanced", "detailed", "manual"] = "manual"
    profile_id: ProfileId | None = None
    generator: Literal["rule_based", "local_ai", "manual"] = "manual"
    model: Annotated[str, StringConstraints(max_length=200)] | None = None
    change_summary: Annotated[str, StringConstraints(max_length=1_000)] = ""


class PromptUpdate(BaseModel):
    title: Name | None = None
    category: Annotated[str, StringConstraints(max_length=40)] | None = None
    target_agent: ProfileId | None = None
    favorite: bool | None = None
    archived: bool | None = None
    tags: list[TagName] | None = Field(default=None, max_length=20)


class VersionOut(ORM):
    id: str
    prompt_id: str
    number: int
    content: str
    variant: str
    profile_id: str
    profile_version: str
    generator: str
    model: str | None
    source_snapshot: dict[str, Any]
    change_summary: str
    parent_version_id: str | None
    created_at: datetime


class VersionMeta(ORM):
    id: str
    number: int
    variant: str
    profile_id: str
    generator: str
    model: str | None
    change_summary: str
    parent_version_id: str | None
    created_at: datetime


class PromptSummary(ORM):
    id: str
    project_id: str | None
    project_name: str | None = None
    title: str
    category: str
    target_agent: str
    favorite: bool
    archived: bool
    tags: list[TagOut]
    current_version_id: str | None
    version_count: int = 0
    created_at: datetime
    updated_at: datetime


class PromptOut(PromptSummary):
    current_version: VersionOut | None = None
    versions: list[VersionMeta] = Field(default_factory=list)


# ----------------------------------------------------------------------------- evaluation


class EvalFindingOut(BaseModel):
    message: str
    evidence: list[str] = Field(default_factory=list)
    fix: str = ""


class DimensionOut(BaseModel):
    id: str
    name: str
    score: float | None
    method: str
    summary: str
    findings: list[EvalFindingOut] = Field(default_factory=list)


class EvaluationOut(ORM):
    id: str | None = None
    prompt_version_id: str | None = None
    engine: str
    model: str | None = None
    score: float | None
    formula: str = ""
    dimensions: list[DimensionOut]
    metrics: dict[str, Any]
    created_at: datetime | None = None
    prompt_id: str | None = None
    prompt_title: str | None = None
    version_number: int | None = None


class EvaluateText(BaseModel):
    content: LongText
    coding: bool = True


# ----------------------------------------------------------------------------- export


class ExportRequest(BaseModel):
    format: Literal[
        "markdown", "text", "claude_md", "agents_md", "cursor_mdc", "plan", "tasks", "tests", "spec", "template"
    ]
    content: LongText | None = None
    version_id: str | None = None


class ExportZipRequest(BaseModel):
    formats: list[
        Literal[
            "markdown", "text", "claude_md", "agents_md", "cursor_mdc", "plan", "tasks", "tests", "spec", "template"
        ]
    ] = Field(min_length=1, max_length=10)
    content: LongText | None = None
    version_id: str | None = None


class ExportFileOut(BaseModel):
    format: str
    filename: str
    media_type: str
    content: str


# ----------------------------------------------------------------------------- settings / models / jobs


class AppSettings(BaseModel):
    ollama_url: Annotated[str, StringConstraints(max_length=300)] = "http://127.0.0.1:11434"
    allow_remote_ollama: bool = False
    model: Annotated[str, StringConstraints(max_length=200)] | None = None
    timeout_seconds: int = Field(default=180, ge=5, le=1800)
    max_retries: int = Field(default=2, ge=0, le=5)
    num_ctx: int = Field(default=8192, ge=512, le=262_144)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_concurrent_jobs: int = Field(default=1, ge=1, le=4)
    default_target_agent: ProfileId = "generic_coding"


class ModelsOut(BaseModel):
    available: bool
    endpoint: str
    version: str | None = None
    error: str | None = None
    error_code: str | None = None
    selected_model: str | None = None
    selected_model_installed: bool = False
    models: list[dict[str, Any]] = Field(default_factory=list)


class JobCreate(BaseModel):
    kind: Literal["analysis", "optimize", "clarify", "evaluate"]
    project_id: str | None = None
    version_id: str | None = None
    variant: VariantName = "balanced"
    profile_id: ProfileId | None = None
    content: LongText | None = None


class JobOut(BaseModel):
    id: str
    kind: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    project_id: str | None
    version_id: str | None
    model: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    error_code: str | None
    result: dict[str, Any] | None


# ----------------------------------------------------------------------------- backups / data


class BackupOut(BaseModel):
    name: str
    size_bytes: int
    created_at: datetime


class BackupValidation(BaseModel):
    name: str
    valid: bool
    checks: list[dict[str, Any]]


class ConfirmBody(BaseModel):
    confirm: Annotated[str, StringConstraints(max_length=50)]


# ----------------------------------------------------------------------------- import bundle


class BundleRequirement(BaseModel):
    kind: ReqKind
    text: Annotated[str, StringConstraints(min_length=1, max_length=5_000)]
    status: ReqStatus = "confirmed"
    source: Annotated[str, StringConstraints(max_length=30)] = "import"


class BundleRecommendation(BaseModel):
    fingerprint: Annotated[str, StringConstraints(max_length=64)]
    engine: Literal["rule_based", "local_ai"] = "rule_based"
    model: Annotated[str, StringConstraints(max_length=200)] | None = None
    title: Annotated[str, StringConstraints(max_length=300)]
    problem: ShortText
    rationale: ShortText
    proposal: ShortText
    benefits: ShortText = ""
    tradeoffs: ShortText = ""
    complexity: Annotated[str, StringConstraints(max_length=20)] = "low"
    dependencies: ShortText = ""
    disadvantages: ShortText = ""
    verification: ShortText = ""
    requirement_kind: ReqKind
    requirement_text: ShortText
    alternatives: list[AlternativeOut] = Field(default_factory=list, max_length=10)
    status: Literal["proposed", "approved", "rejected", "deferred"] = "proposed"


class BundleVersion(BaseModel):
    number: int = Field(ge=1)
    content: LongText
    variant: Literal["concise", "balanced", "detailed", "manual"] = "manual"
    profile_id: Annotated[str, StringConstraints(max_length=40)] = "generic_coding"
    profile_version: Annotated[str, StringConstraints(max_length=20)] = "1.0.0"
    generator: Literal["rule_based", "local_ai", "manual"] = "manual"
    model: Annotated[str, StringConstraints(max_length=200)] | None = None
    change_summary: Annotated[str, StringConstraints(max_length=1_000)] = ""
    source_snapshot: dict[str, Any] = Field(default_factory=dict)


class BundlePrompt(BaseModel):
    title: Name
    category: Annotated[str, StringConstraints(max_length=40)] = "general"
    target_agent: Annotated[str, StringConstraints(max_length=40)] = "generic_coding"
    favorite: bool = False
    tags: list[TagName] = Field(default_factory=list, max_length=20)
    versions: list[BundleVersion] = Field(default_factory=list, max_length=500)


class BundleProject(BaseModel):
    name: Name
    description: ShortText = ""
    original_idea: LongText = ""
    tech_stack: ShortText = ""
    config: ConfigIn = Field(default_factory=ConfigIn)
    tags: list[TagName] = Field(default_factory=list, max_length=20)
    requirements: list[BundleRequirement] = Field(default_factory=list, max_length=1_000)
    recommendations: list[BundleRecommendation] = Field(default_factory=list, max_length=1_000)
    prompts: list[BundlePrompt] = Field(default_factory=list, max_length=100)


class ProjectBundle(BaseModel):
    format: Literal["prompt-studio-project"]
    format_version: Literal[1]
    exported_at: datetime | None = None
    project: BundleProject


# ----------------------------------------------------------------------------- codebase context


class CodebaseScanRequest(BaseModel):
    path: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    max_file_kb: int = Field(default=100, ge=1, le=1000)
    extra_excludes: list[Annotated[str, StringConstraints(min_length=1, max_length=200)]] = Field(
        default_factory=list, max_length=100
    )


class CodebaseSummaryRequest(CodebaseScanRequest):
    files: list[Annotated[str, StringConstraints(min_length=1, max_length=1024)]] = Field(max_length=200)
