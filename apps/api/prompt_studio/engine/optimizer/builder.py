"""Deterministic structured prompt builder.

Design rules:
* User content (idea, requirements, config values) is rendered **verbatim**.
* Sections with no content are omitted; short tasks stay short.
* Generic process guidance written by this template (not by the user) is only
  added in the balanced/detailed variants of coding tasks, and every such
  section is reported with `source="template"` so the UI can label it.
* Rejected requirements are never rendered. Unresolved items are rendered
  under "Assumptions and open questions" and clearly labelled.
* Every confirmed requirement is checked for presence in the output
  (preservation report).
"""

from __future__ import annotations

import re
from collections.abc import Callable

from pydantic import BaseModel

from ..spec import ProjectSpec, SpecRequirement, Variant
from ..templates.profiles import AgentProfile, get_profile
from ..text import contains_requirement, estimate_tokens, token_coverage

CATEGORY_ROLES = {
    "new_application": "an experienced software engineer building a new application",
    "feature": "an experienced software engineer adding a feature to an existing codebase",
    "bug_fix": "an experienced software engineer diagnosing and fixing a defect",
    "refactor": "an experienced software engineer refactoring code without changing its behaviour",
    "code_review": "a meticulous code reviewer",
    "testing": "an experienced test engineer",
    "documentation": "an experienced technical writer",
    "data_analysis": "a careful data analyst",
    "writing": "a skilled writer",
    "general": "a knowledgeable assistant",
}

_API_RE = re.compile(r"\b(api|endpoint|rest|graphql|http)\b", re.I)
_UI_RE = re.compile(r"\b(ui|ux|frontend|front-end|page|screen|dashboard|form|button|layout|interface)\b", re.I)


class SectionInfo(BaseModel):
    id: str
    title: str
    source: str  # "user" | "template" | "mixed"


class PreservationItem(BaseModel):
    requirement_id: str
    kind: str
    text: str
    preserved: bool
    coverage: float  # fraction of content words present (1.0 for exact match)


class BuildResult(BaseModel):
    variant: str
    profile_id: str
    profile_version: str
    content: str
    sections: list[SectionInfo]
    preservation: list[PreservationItem]
    warnings: list[str]
    char_count: int
    word_count: int
    token_estimate: int


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items)


def _reqs(spec: ProjectSpec, *kinds: str) -> list[SpecRequirement]:
    return [r for r in spec.requirements if r.status == "confirmed" and r.kind in kinds]


def _numbered(items: list[str]) -> str:
    return "\n".join(f"{n}. {i}" for n, i in enumerate(items, 1))


class _Doc:
    def __init__(self, level: int) -> None:
        self.parts: list[str] = []
        self.sections: list[SectionInfo] = []
        self.h = "#" * level

    def add(self, sid: str, title: str, body: str, source: str = "user") -> None:
        body = body.strip()
        if not body:
            return
        self.parts.append(f"{self.h} {title}\n\n{body}")
        self.sections.append(SectionInfo(id=sid, title=title, source=source))


def build_prompt(spec: ProjectSpec, variant: Variant = "balanced", profile_id: str | None = None) -> BuildResult:
    profile = get_profile(profile_id or spec.config.target_agent)
    cfg = spec.config
    coding = spec.is_coding and profile.coding
    detailed = variant == "detailed"
    concise = variant == "concise"
    guidance = coding and not concise
    doc = _Doc(level=2)
    all_text = spec.all_text()

    # 1. Role and objective
    role = CATEGORY_ROLES.get(cfg.task_category, CATEGORY_ROLES["general"])
    lang = " / ".join(x for x in [cfg.language, cfg.framework] if x)
    role_line = f"You are {role}" + (f" working with {lang}" if lang else "") + "."
    objective = spec.idea.strip() or spec.description.strip() or f"Work on: {spec.name}"
    tone = f"\n\nTone: {cfg.tone}" if cfg.tone else ""
    doc.add("role_objective", "Role and objective", f"{role_line}\n\n{objective}{tone}")

    # 2-3. Context
    if not concise:
        ctx = []
        if spec.description and spec.description.strip() != objective:
            ctx.append(spec.description)
        if cfg.budget:
            ctx.append(f"Budget: {cfg.budget}")
        doc.add("context", "Project context", "\n\n".join(ctx))
    doc.add("existing", "Existing implementation", cfg.existing_codebase)

    # 4-6. Requirements
    if concise:
        lines = []
        for kind, label in [
            ("goal", "Goal"),
            ("functional", "Must"),
            ("non_functional", "Quality"),
            ("security", "Security"),
            ("constraint", "Constraint"),
        ]:
            lines += [f"{label}: {r.text}" for r in _reqs(spec, kind)]
        doc.add("requirements", "Requirements", _bullets(lines))
    else:
        doc.add("goals", "Goals", _bullets([r.text for r in _reqs(spec, "goal")]))
        doc.add("functional", "Functional requirements", _numbered([r.text for r in _reqs(spec, "functional")]))
        doc.add(
            "non_functional", "Non-functional requirements", _bullets([r.text for r in _reqs(spec, "non_functional")])
        )

    # 7-8. Stack and architecture
    stack = []
    if spec.tech_stack:
        stack.append(spec.tech_stack)
    if lang and lang not in spec.tech_stack:
        stack.append(f"Language/framework: {lang}")
    doc.add("stack", "Technology stack", "\n".join(stack))
    if not concise:
        doc.add("architecture", "Architecture", cfg.architecture)

    # 9-14 template guidance (labelled)
    if detailed and coding:
        doc.add(
            "modules",
            "Module boundaries",
            "Keep business logic separate from I/O (HTTP, database, UI). Describe the modules you create or "
            "change and their responsibilities.",
            source="template",
        )
        doc.add(
            "data_models",
            "Data models",
            "Define data structures explicitly with types and validation. Document any schema changes.",
            source="template",
        )
    if not concise and _API_RE.search(all_text):
        doc.add(
            "api",
            "API contracts",
            "Document every endpoint you add or change: method, path, request/response schema, error responses."
            if coding
            else "",
            source="template",
        )
    if not concise and _UI_RE.search(all_text) and coding:
        doc.add(
            "ui",
            "UI/UX requirements",
            "Interfaces must be keyboard accessible, show loading and error states, and not include "
            "non-functional placeholder controls.",
            source="template",
        )
    if guidance:
        doc.add(
            "errors",
            "Validation and error handling",
            "Validate inputs at boundaries. Handle failures explicitly with clear messages; never fail silently "
            "or expose internal details.",
            source="template",
        )
    if detailed and coding:
        doc.add(
            "edge_cases",
            "Edge cases",
            "Identify and handle edge cases (empty input, very large input, concurrent use, unavailable "
            "dependencies). List the ones you handled.",
            source="template",
        )

    # 15. Security
    sec = [r.text for r in _reqs(spec, "security")] if not concise else []
    if cfg.security:
        sec.append(cfg.security)
    doc.add("security", "Security and privacy", _bullets(sec))

    # 16-17. Performance, constraints, compatibility
    perf = [x for x in [cfg.performance, f"Hardware: {cfg.hardware}" if cfg.hardware else ""] if x]
    doc.add("performance", "Performance and scalability", _bullets(perf))
    cons = ([r.text for r in _reqs(spec, "constraint")] if not concise else []) + (
        [cfg.restrictions] if cfg.restrictions else []
    )
    doc.add("constraints", "Constraints and restrictions", _bullets(cons))
    if detailed and coding:
        doc.add(
            "dependencies",
            "Dependencies and compatibility",
            "Prefer existing dependencies. Justify any new dependency, pin versions, and verify compatibility "
            "rather than assuming it.",
            source="template",
        )
        doc.add(
            "phases",
            "Implementation phases",
            "Work in small, verifiable steps. After each step, run the relevant tests and fix failures before "
            "continuing.",
            source="template",
        )

    # 19. Testing
    tests = [cfg.testing] if cfg.testing else []
    if guidance and not tests:
        doc.add(
            "testing",
            "Testing strategy",
            "Add or update automated tests for the changed behaviour and run the full test suite.",
            source="template",
        )
    else:
        doc.add("testing", "Testing strategy", _bullets(tests))

    # 20. Acceptance
    doc.add("acceptance", "Acceptance criteria", _bullets([r.text for r in _reqs(spec, "acceptance")]))

    # 21-22. Deliverables, docs
    deliverables = cfg.output_format
    if guidance and not deliverables:
        doc.add(
            "deliverables",
            "Expected deliverables",
            "Working code, tests, and a short summary of what changed, how it was verified, and any known limitations.",
            source="template",
        )
    else:
        doc.add("deliverables", "Expected output" if not coding else "Expected deliverables", deliverables)
    if detailed and coding:
        doc.add(
            "docs",
            "Documentation requirements",
            "Update README or relevant docs for any new setup steps, configuration or behaviour.",
            source="template",
        )

    # 23. Out of scope + assumptions
    oos = [r.text for r in _reqs(spec, "out_of_scope")]
    doc.add("out_of_scope", "Out of scope", _bullets(oos))
    open_items = [
        r
        for r in spec.requirements
        if r.status == "unresolved" or (r.kind == "assumption" and r.status in {"proposed", "confirmed"})
    ]
    if open_items:
        lines = []
        for r in open_items:
            label = (
                "Assumption (confirmed)"
                if r.status == "confirmed"
                else "Unconfirmed assumption — verify before relying on it"
            )
            lines.append(f"{label}: {r.text}")
        doc.add(
            "assumptions",
            "Assumptions and open questions",
            _bullets(lines) + "\n\nIf an open question blocks correct implementation, ask before proceeding.",
            source="mixed",
        )

    # 24. Completion checklist
    if not concise and (coding or _reqs(spec, "acceptance")):
        checklist = ["All requirements above are addressed"]
        checklist += [f"Acceptance: {r.text}" for r in _reqs(spec, "acceptance")]
        if coding:
            checklist += ["Tests pass", "Known limitations are reported honestly"]
        doc.add("checklist", "Completion checklist", "\n".join(f"- [ ] {c}" for c in checklist), source="mixed")

    content = "\n\n".join(doc.parts) + "\n"
    preservation = check_preservation(content, spec)
    warnings = []
    missing = [p for p in preservation if not p.preserved]
    if missing:
        warnings.append(f"{len(missing)} confirmed requirement(s) are not present verbatim in the output.")
    if variant == "detailed" and not coding:
        warnings.append("Detailed variant of a non-coding task: coding guidance sections were omitted.")
    return BuildResult(
        variant=variant,
        profile_id=profile.id,
        profile_version=profile.version,
        content=content,
        sections=doc.sections,
        preservation=preservation,
        warnings=warnings,
        char_count=len(content),
        word_count=len(content.split()),
        token_estimate=estimate_tokens(content),
    )


def check_preservation(content: str, spec: ProjectSpec) -> list[PreservationItem]:
    out = []
    for r in spec.confirmed:
        if r.kind == "assumption":
            continue
        exact = contains_requirement(content, r.text)
        cov = 1.0 if exact else token_coverage(content, r.text)
        out.append(
            PreservationItem(requirement_id=r.id, kind=r.kind, text=r.text, preserved=exact, coverage=round(cov, 2))
        )
    return out


def build_all(spec: ProjectSpec, profile_id: str | None = None) -> list[BuildResult]:
    variants: list[Variant] = ["concise", "balanced", "detailed"]
    return [build_prompt(spec, v, profile_id) for v in variants]


def profile_for(profile_id: str) -> AgentProfile:
    return get_profile(profile_id)


Builder = Callable[[ProjectSpec, Variant, str | None], BuildResult]
