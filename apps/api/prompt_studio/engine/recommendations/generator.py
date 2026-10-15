"""Turn findings into actionable recommendations (deterministic).

A recommendation proposes a concrete *requirement* that will be added to the
specification only if the user approves it. Severity `info` findings and
findings that are pure questions do not get recommendations.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from ..spec import FindingDraft


class Alternative(BaseModel):
    title: str
    requirement_text: str
    tradeoffs: str


PLACEHOLDER_RE = re.compile(r"\[[A-Za-z][^\]]*\s[^\]]+\]")


def needs_edit(text: str) -> bool:
    """True if the text still contains a [placeholder] that the user must fill in."""
    return bool(PLACEHOLDER_RE.search(text))


class RecommendationDraft(BaseModel):
    fingerprint: str
    title: str
    problem: str
    rationale: str
    proposal: str
    benefits: str
    tradeoffs: str
    complexity: str  # low | medium | high
    dependencies: str = ""
    disadvantages: str = ""
    verification: str
    requirement_kind: str
    requirement_text: str
    alternatives: list[Alternative] = Field(default_factory=list)


def _r(f: FindingDraft, **kw) -> RecommendationDraft:
    kw.setdefault("problem", f.title)
    kw.setdefault("rationale", f.impact)
    kw.setdefault("verification", f.verification)
    return RecommendationDraft(fingerprint=f.fingerprint, **kw)


def recommend(f: FindingDraft) -> RecommendationDraft | None:
    rid = f.rule_id
    if f.severity == "info" or f.kind == "unresolved_question":
        return None
    if rid == "ACC-001":
        return _r(
            f,
            title="Add acceptance criteria",
            proposal="Add a confirmed acceptance requirement describing observable completion.",
            benefits="Gives the agent a stopping condition and you an objective review checklist.",
            tradeoffs="Takes a few minutes to write; criteria may need revision as scope changes.",
            complexity="low",
            disadvantages="Overly rigid criteria can discourage better alternative solutions.",
            requirement_kind="acceptance",
            requirement_text="All functional requirements are implemented and each is demonstrated by at least one "
            "passing automated test or documented manual check.",
            alternatives=[
                Alternative(
                    title="Agent proposes criteria first",
                    requirement_text="Before implementing, propose acceptance criteria and wait for approval.",
                    tradeoffs="Adds a review round-trip but captures criteria you may not have thought of.",
                ),
            ],
        )
    if rid == "TST-001":
        return _r(
            f,
            title="Specify testing expectations",
            proposal="Require automated tests for new behaviour and a passing test run before completion.",
            benefits="Catches regressions; makes the agent verify its own work.",
            tradeoffs="Longer implementation time.",
            complexity="medium",
            dependencies="A test runner suitable for the stack.",
            requirement_kind="non_functional",
            requirement_text="Add automated unit tests for new logic and integration tests for changed interfaces; "
            "the full test suite must pass before the task is complete.",
            alternatives=[
                Alternative(
                    title="Unit tests only",
                    requirement_text="Add unit tests for new logic; the test suite must pass.",
                    tradeoffs="Faster, but integration issues go undetected.",
                ),
                Alternative(
                    title="Unit + integration + end-to-end",
                    requirement_text="Add unit, integration and end-to-end tests covering the main user "
                    "workflow; all must pass.",
                    tradeoffs="Highest confidence; considerably more effort and tooling.",
                ),
            ],
        )
    if rid == "SEC-001":
        return _r(
            f,
            title="Add security requirements",
            proposal="Add baseline security requirements appropriate to the task.",
            benefits="Prevents common vulnerabilities from being introduced by default.",
            tradeoffs="May add validation code and dependencies.",
            complexity="medium",
            requirement_kind="security",
            requirement_text="Validate and sanitize all external input, never hard-code or log secrets, and apply "
            "least-privilege access to data and operations.",
            alternatives=[
                Alternative(
                    title="Reference OWASP ASVS level 1",
                    requirement_text="Meet OWASP ASVS Level 1 controls relevant to this feature.",
                    tradeoffs="Comprehensive and standard, but long; agents may apply it superficially.",
                ),
            ],
        )
    if rid == "ERR-001":
        return _r(
            f,
            title="Define error handling",
            proposal="State how invalid input and failures must be handled.",
            benefits="Predictable failure behaviour and clearer user-facing errors.",
            tradeoffs="More code paths to implement and test.",
            complexity="low",
            requirement_kind="functional",
            requirement_text="Handle invalid input and external failures explicitly: validate inputs, return clear "
            "error messages without exposing internals, and never fail silently.",
        )
    if rid == "REQ-003":
        return _r(
            f,
            title="Add non-functional requirements",
            proposal="Add the quality attributes that matter for this task.",
            benefits="Prevents surprises around performance, accessibility and maintainability.",
            tradeoffs="Each attribute adds verification effort.",
            complexity="low",
            requirement_kind="non_functional",
            requirement_text="Follow the existing code style and conventions, keep functions small and typed, and "
            "document any new configuration.",
        )
    if rid == "REQ-002":
        return _r(
            f,
            title="Break the idea into functional requirements",
            proposal="Add each key behaviour as its own functional requirement.",
            benefits="Requirements become individually trackable, preservable and verifiable.",
            tradeoffs="Requires you to enumerate behaviours explicitly.",
            complexity="low",
            requirement_kind="goal",
            requirement_text=f.evidence[0].quote
            if f.evidence and f.evidence[0].source == "idea"
            else "Implement the behaviour described in the project idea.",
        )
    if rid == "BND-001":
        return _r(
            f,
            title="State what is out of scope",
            proposal="Add explicit out-of-scope boundaries.",
            benefits="Stops scope creep and unrequested refactors.",
            tradeoffs="May block helpful improvements the agent would otherwise make.",
            complexity="low",
            requirement_kind="out_of_scope",
            requirement_text="Do not add features, dependencies or refactors that are not required by the stated "
            "requirements; list any suggested extras separately instead of implementing them.",
        )
    if rid == "ASM-002":
        return _r(
            f,
            title="Decide the technology stack",
            proposal="Either specify the stack or ask the agent to propose one with justification.",
            benefits="Avoids a stack you cannot run or maintain.",
            tradeoffs="Fixing the stack early limits the agent's options.",
            complexity="low",
            requirement_kind="constraint",
            requirement_text="Propose a technology stack with a short justification and wait for approval before "
            "writing code.",
        )
    if rid == "AMB-001":
        term = f.title.split('"')[1] if '"' in f.title else "the vague term"
        return _r(
            f,
            title=f'Define "{term}" concretely',
            proposal=f.solution,
            benefits="Removes interpretation risk and makes the requirement verifiable.",
            tradeoffs="Requires you to choose concrete values.",
            complexity="low",
            requirement_kind="non_functional",
            requirement_text=f'Where the specification says "{term}", interpret it as: [state the concrete, '
            "measurable criterion here].",
        )
    if rid in {"PRF-001", "SCL-001"}:
        return _r(
            f,
            title="Add measurable performance/scale targets",
            proposal=f.solution,
            benefits="Lets the agent size the solution correctly and lets you verify it.",
            tradeoffs="Targets may need benchmarking to choose.",
            complexity="medium",
            dependencies="Knowledge of target hardware and expected load.",
            requirement_kind="non_functional",
            requirement_text="Performance target: [state latency, throughput, data size or user count and the "
            "target hardware].",
            alternatives=[
                Alternative(
                    title="Scale is out of scope for v1",
                    requirement_text="Optimise for simplicity; performance at scale is out of scope for the "
                    "first version.",
                    tradeoffs="Faster to build; may need rework later.",
                ),
            ],
        )
    if rid == "CMP-001":
        return _r(
            f,
            title="Pin dependency versions",
            proposal=f.solution,
            benefits="Reproducible builds and fewer compatibility surprises.",
            tradeoffs="Pinned versions need deliberate upgrades.",
            complexity="low",
            requirement_kind="constraint",
            requirement_text="Use explicitly pinned, mutually compatible dependency versions, verify compatibility, "
            "and commit lockfiles.",
        )
    if rid == "CPX-001":
        return _r(
            f,
            title="Prefer the simplest viable architecture",
            proposal=f.solution,
            benefits="Less operational overhead and faster delivery.",
            tradeoffs="May need re-architecture if scale grows substantially.",
            complexity="low",
            requirement_kind="constraint",
            requirement_text="Use the simplest architecture that satisfies the requirements; justify any distributed "
            "component with a specific requirement.",
        )
    if rid == "SCP-001":
        return _r(
            f,
            title="Split the work into phases",
            proposal=f.solution,
            benefits="Smaller tasks are completed more reliably and are easier to review.",
            tradeoffs="More prompts to manage.",
            complexity="medium",
            requirement_kind="constraint",
            requirement_text="Implement in phases; finish, test and report on each phase before starting the next.",
        )
    if rid == "ASM-001":
        return _r(
            f,
            title="Make implicit context explicit",
            proposal=f.solution,
            benefits="The agent does not need to guess what 'usual' means.",
            tradeoffs="Requires writing down conventions.",
            complexity="low",
            requirement_kind="constraint",
            requirement_text="Follow these conventions explicitly: [describe the referenced convention or prior "
            "decision].",
        )
    if rid == "DEP-001":
        return _r(
            f,
            title="Reduce the technology stack",
            proposal=f.solution,
            benefits="Smaller attack surface and less integration risk.",
            tradeoffs="Some convenience libraries may be dropped.",
            complexity="medium",
            requirement_kind="constraint",
            requirement_text="Do not introduce technologies beyond those required; justify each new dependency.",
        )
    # Contradictions and duplicates need a human decision about which item wins;
    # the recommendation is a review action without a canned requirement.
    if rid in {"CON-001", "CON-002", "DUP-001"}:
        return _r(
            f,
            title="Resolve: " + f.title.lower(),
            proposal=f.solution,
            benefits="Removes conflicting or redundant instructions.",
            tradeoffs="You must decide which statement is correct.",
            complexity="low",
            requirement_kind="constraint",
            requirement_text="[Write the single reconciled requirement here, then reject the conflicting items.]",
        )
    return None
