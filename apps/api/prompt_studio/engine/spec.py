"""Domain models consumed by the deterministic engine.

These are plain Pydantic models decoupled from the ORM, so the engine can be
unit-tested without a database.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RequirementKind = Literal[
    "goal", "functional", "non_functional", "security", "constraint", "acceptance", "assumption", "out_of_scope"
]
RequirementStatus = Literal["confirmed", "proposed", "rejected", "unresolved"]
Severity = Literal["critical", "high", "medium", "low", "info"]
Confidence = Literal["high", "medium", "low"]
FindingKind = Literal["confirmed_issue", "potential_risk", "assumption", "recommendation", "unresolved_question"]
Engine = Literal["rule_based", "local_ai"]
Variant = Literal["concise", "balanced", "detailed"]

REQUIREMENT_KINDS: tuple[str, ...] = RequirementKind.__args__  # type: ignore[attr-defined]

TASK_CATEGORIES = (
    "new_application",
    "feature",
    "bug_fix",
    "refactor",
    "code_review",
    "testing",
    "documentation",
    "data_analysis",
    "writing",
    "general",
)
CODING_CATEGORIES = frozenset({"new_application", "feature", "bug_fix", "refactor", "code_review", "testing"})


class PromptConfig(BaseModel):
    """Optional prompt-generation settings. Every field may be empty."""

    target_agent: str = "generic_coding"
    task_category: str = "general"
    language: str = ""
    framework: str = ""
    existing_codebase: str = ""
    project_size: Literal["", "small", "medium", "large"] = ""
    detail_level: Literal["", "concise", "balanced", "detailed"] = ""
    tone: str = ""
    output_format: str = ""
    testing: str = ""
    security: str = ""
    performance: str = ""
    hardware: str = ""
    budget: str = ""
    architecture: str = ""
    restrictions: str = ""


class SpecRequirement(BaseModel):
    id: str
    kind: str
    text: str
    status: str = "confirmed"


class ProjectSpec(BaseModel):
    name: str
    description: str = ""
    idea: str = ""
    tech_stack: str = ""
    config: PromptConfig = Field(default_factory=PromptConfig)
    requirements: list[SpecRequirement] = Field(default_factory=list)

    def by_kind(self, kind: str, status: str = "confirmed") -> list[SpecRequirement]:
        return [r for r in self.requirements if r.kind == kind and r.status == status]

    @property
    def confirmed(self) -> list[SpecRequirement]:
        return [r for r in self.requirements if r.status == "confirmed"]

    @property
    def is_coding(self) -> bool:
        return self.config.task_category in CODING_CATEGORIES

    def all_text(self) -> str:
        """All user-authored text the rules inspect (excluding rejected items)."""
        parts = [self.idea, self.description, self.tech_stack]
        parts += [v for v in self.config.model_dump().values() if isinstance(v, str)]
        parts += [r.text for r in self.requirements if r.status != "rejected"]
        return "\n".join(p for p in parts if p)


class Evidence(BaseModel):
    source: str  # e.g. "idea", "requirement:<id>", "config.performance"
    quote: str = ""
    line: int | None = None


class FindingDraft(BaseModel):
    rule_id: str
    fingerprint: str
    category: str
    kind: FindingKind
    title: str
    explanation: str
    evidence: list[Evidence]
    severity: Severity
    confidence: Confidence
    impact: str
    solution: str
    alternative: str = ""
    verification: str
