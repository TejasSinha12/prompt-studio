"""Deterministic requirement-analysis rules.

Every rule is a pure function `(spec) -> list[FindingDraft]`. Rules only claim
what they can observe: a *missing* section is a confirmed issue, a keyword
heuristic is a *potential risk* with lower confidence. Severity is chosen
from the observed evidence, and each rule documents why.

Fingerprints are derived from the rule id plus the evidence key (e.g. the
vague term), so the same issue keeps the same id across runs.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

from ..spec import Evidence, FindingDraft, ProjectSpec
from ..text import fingerprint, jaccard, line_of, normalize, snippet, word_count

Rule = Callable[[ProjectSpec], list[FindingDraft]]
RULES: list[Rule] = []


def rule(fn: Rule) -> Rule:
    RULES.append(fn)
    return fn


def _sources(spec: ProjectSpec) -> list[tuple[str, str]]:
    """(source label, text) pairs for user-authored, non-rejected text."""
    out: list[tuple[str, str]] = []
    if spec.idea:
        out.append(("idea", spec.idea))
    if spec.description:
        out.append(("description", spec.description))
    if spec.tech_stack:
        out.append(("tech_stack", spec.tech_stack))
    for key, val in spec.config.model_dump().items():
        if (
            isinstance(val, str)
            and val
            and key not in {"target_agent", "task_category", "project_size", "detail_level", "existing_codebase"}
        ):
            out.append((f"config.{key}", val))
    for r in spec.requirements:
        if r.status != "rejected":
            out.append((f"requirement:{r.id}", r.text))
    return out


def _search(spec: ProjectSpec, pattern: re.Pattern[str], limit: int = 5) -> list[Evidence]:
    found: list[Evidence] = []
    for source, text in _sources(spec):
        for m in pattern.finditer(text):
            found.append(
                Evidence(source=source, quote=snippet(text, m.start(), m.end()), line=line_of(text, m.start()))
            )
            if len(found) >= limit:
                return found
    return found


def _mentions(spec: ProjectSpec, pattern: re.Pattern[str]) -> bool:
    return any(pattern.search(t) for _, t in _sources(spec))


def _has_kind(spec: ProjectSpec, *kinds: str) -> bool:
    return any(r.kind in kinds and r.status == "confirmed" for r in spec.requirements)


def _f(rule_id: str, key: str, **kw) -> FindingDraft:
    return FindingDraft(rule_id=rule_id, fingerprint=fingerprint(rule_id, key), **kw)


# --------------------------------------------------------------------------- completeness


@rule
def idea_too_short(spec: ProjectSpec) -> list[FindingDraft]:
    n = word_count(spec.idea)
    if n >= 12 or len(spec.confirmed) >= 3:
        return []
    return [
        _f(
            "REQ-001",
            "idea",
            category="missing_requirements",
            kind="confirmed_issue",
            title="Idea is too brief to define the task",
            explanation=f"The original idea has {n} word(s) and fewer than 3 confirmed requirements. "
            "An agent will have to guess most of the intent.",
            evidence=[Evidence(source="idea", quote=spec.idea[:200] or "(empty)")],
            severity="high",
            confidence="high",
            impact="High risk that generated output does not match what you want.",
            solution="Describe who it is for, what it must do, and what 'done' looks like, "
            "or add functional requirements.",
            alternative="Start from a built-in template and fill in its fields.",
            verification="Re-run analysis: this finding resolves when the idea has ≥12 words "
            "or ≥3 confirmed requirements.",
        )
    ]


@rule
def missing_functional(spec: ProjectSpec) -> list[FindingDraft]:
    if _has_kind(spec, "functional", "goal"):
        return []
    return [
        _f(
            "REQ-002",
            "functional",
            category="missing_requirements",
            kind="confirmed_issue",
            title="No confirmed goals or functional requirements",
            explanation="The specification has no confirmed 'goal' or 'functional' requirement items. "
            "The prompt will rely entirely on the free-text idea.",
            evidence=[Evidence(source="requirements", quote="0 confirmed goal/functional items")],
            severity="medium",
            confidence="high",
            impact="Requirements cannot be tracked, preserved during optimization, or verified individually.",
            solution="Add the key behaviours as separate functional requirements.",
            verification="Requirements panel shows at least one confirmed goal or functional item.",
        )
    ]


_ACCEPT_RE = re.compile(r"acceptance criteri|definition of done|done when|success criteri|is complete when", re.I)


@rule
def missing_acceptance(spec: ProjectSpec) -> list[FindingDraft]:
    if _has_kind(spec, "acceptance") or _mentions(spec, _ACCEPT_RE):
        return []
    return [
        _f(
            "ACC-001",
            "acceptance",
            category="missing_acceptance_criteria",
            kind="confirmed_issue",
            title="No acceptance criteria",
            explanation="No acceptance requirement exists and the text never states when the task is complete.",
            evidence=[
                Evidence(
                    source="requirements",
                    quote="0 confirmed acceptance items; no 'done when'/'acceptance criteria' phrase",
                )
            ],
            severity="high" if spec.is_coding else "medium",
            confidence="high",
            impact="The agent cannot tell when to stop, and you cannot objectively verify the result.",
            solution="Add 2–5 observable, testable acceptance criteria.",
            alternative="Ask the agent to propose acceptance criteria for your approval before implementing.",
            verification="At least one confirmed acceptance requirement exists.",
        )
    ]


_TEST_RE = re.compile(r"\btest(s|ing|ed)?\b|\bpytest\b|\bjest\b|\bvitest\b|\bunit\b|\be2e\b|\bplaywright\b", re.I)


@rule
def missing_tests(spec: ProjectSpec) -> list[FindingDraft]:
    if not spec.is_coding or spec.config.testing.strip() or _mentions(spec, _TEST_RE):
        return []
    return [
        _f(
            "TST-001",
            "tests",
            category="missing_tests",
            kind="confirmed_issue",
            title="No testing expectations",
            explanation="This is a coding task but neither the configuration nor any requirement mentions tests.",
            evidence=[Evidence(source="config.testing", quote="(empty)")],
            severity="medium",
            confidence="high",
            impact="Agents frequently skip tests unless asked; regressions go unnoticed.",
            solution="State which tests are expected (unit, integration, end-to-end) and that they must pass.",
            verification="Testing field or a requirement mentions the expected tests.",
        )
    ]


_SENSITIVE_RE = re.compile(
    r"\b(auth\w*|log ?in|sign ?in|password\w*|payment\w*|credit card|upload\w*|personal data|pii|"
    r"user data|tokens?|api keys?|admin|medical|health records?|financial|secrets?|e-?mail addresses)\b",
    re.I,
)
_SECURITY_RE = re.compile(r"\b(secur\w*|privacy|encrypt\w*|sanitiz\w*|owasp|xss|csrf|injection|permission\w*)\b", re.I)


@rule
def missing_security(spec: ProjectSpec) -> list[FindingDraft]:
    if (
        not spec.is_coding
        or _has_kind(spec, "security")
        or spec.config.security.strip()
        or _mentions(spec, _SECURITY_RE)
    ):
        return []
    sensitive = _search(spec, _SENSITIVE_RE, limit=4)
    return [
        _f(
            "SEC-001",
            "security",
            category="missing_security",
            kind="confirmed_issue" if sensitive else "potential_risk",
            title="No security requirements" + (" for sensitive functionality" if sensitive else ""),
            explanation=(
                "The text mentions security-sensitive functionality but states no security requirements."
                if sensitive
                else "No security requirements are stated. No obviously sensitive functionality was detected."
            ),
            evidence=sensitive or [Evidence(source="requirements", quote="0 confirmed security items")],
            severity="high" if sensitive else "low",
            confidence="high" if sensitive else "medium",
            impact="Agents may implement insecure defaults (e.g. unvalidated input, plaintext secrets).",
            solution="Add security requirements: input validation, authentication/authorization rules, "
            "secret handling, and data protection relevant to the task.",
            verification="At least one confirmed security requirement exists.",
        )
    ]


_ERROR_RE = re.compile(
    r"\b(error\w*|fail\w*|exception\w*|invalid|validat\w*|retr(y|ies)|timeouts?|fallback|edge cases?)\b", re.I
)


@rule
def missing_error_handling(spec: ProjectSpec) -> list[FindingDraft]:
    if not spec.is_coding or _mentions(spec, _ERROR_RE):
        return []
    return [
        _f(
            "ERR-001",
            "errors",
            category="incomplete_error_handling",
            kind="confirmed_issue",
            title="Error handling is not specified",
            explanation="No text mentions errors, failures, validation, timeouts or edge cases.",
            evidence=[Evidence(source="all text", quote="no error/failure/validation keywords found")],
            severity="medium",
            confidence="medium",
            impact="Happy-path-only implementations that fail unpredictably on bad input.",
            solution="Specify how invalid input, external failures and edge cases must be handled.",
            verification="A requirement describes expected behaviour for invalid input or failures.",
        )
    ]


@rule
def missing_nfr(spec: ProjectSpec) -> list[FindingDraft]:
    if not spec.is_coding or _has_kind(spec, "non_functional") or spec.config.performance.strip():
        return []
    return [
        _f(
            "REQ-003",
            "nfr",
            category="missing_requirements",
            kind="confirmed_issue",
            title="No non-functional requirements",
            explanation="No performance, reliability, accessibility or maintainability expectations are stated.",
            evidence=[Evidence(source="requirements", quote="0 confirmed non_functional items")],
            severity="low",
            confidence="high",
            impact="Quality attributes are left to the agent's defaults.",
            solution="Add the quality attributes that matter (e.g. accessibility level, response time, supported platforms).",
            verification="At least one confirmed non-functional requirement exists.",
        )
    ]


@rule
def unclear_boundaries(spec: ProjectSpec) -> list[FindingDraft]:
    if _has_kind(spec, "out_of_scope") or spec.config.restrictions.strip():
        return []
    if word_count(spec.idea) < 12 and not spec.confirmed:
        return []  # REQ-001 already covers an essentially empty spec
    return [
        _f(
            "BND-001",
            "boundaries",
            category="unclear_boundaries",
            kind="confirmed_issue",
            title="Project boundaries are not stated",
            explanation="There are no out-of-scope items and no restrictions, so it is unclear what must not be done.",
            evidence=[Evidence(source="requirements", quote="0 out_of_scope items; restrictions empty")],
            severity="low",
            confidence="high",
            impact="Agents may expand scope (extra features, refactors, new dependencies).",
            solution="List what is explicitly out of scope and any files/areas that must not change.",
            verification="At least one out-of-scope requirement or restriction exists.",
        )
    ]


@rule
def stack_unspecified(spec: ProjectSpec) -> list[FindingDraft]:
    if spec.config.task_category not in {"new_application", "feature"}:
        return []
    if spec.tech_stack.strip() or spec.config.language.strip() or spec.config.framework.strip():
        return []
    return [
        _f(
            "ASM-002",
            "stack",
            category="unsupported_assumptions",
            kind="assumption",
            title="Technology stack is unspecified",
            explanation="No language, framework or stack is given; the agent will choose one.",
            evidence=[Evidence(source="tech_stack", quote="(empty)")],
            severity="low",
            confidence="high",
            impact="The chosen stack may not match your environment or skills.",
            solution="Specify language/framework, or explicitly let the agent choose and justify.",
            verification="Tech stack, language or framework field is filled in.",
        )
    ]


# --------------------------------------------------------------------------- wording

VAGUE_TERMS: dict[str, str] = {
    "fast": "measurable",
    "quick": "measurable",
    "quickly": "measurable",
    "performant": "measurable",
    "scalable": "measurable",
    "efficient": "measurable",
    "secure": "measurable",
    "robust": "measurable",
    "reliable": "measurable",
    "responsive": "measurable",
    "high quality": "measurable",
    "user-friendly": "subjective",
    "user friendly": "subjective",
    "intuitive": "subjective",
    "modern": "subjective",
    "clean": "subjective",
    "nice": "subjective",
    "simple": "subjective",
    "easy": "subjective",
    "beautiful": "subjective",
    "seamless": "subjective",
    "etc": "open-ended",
    "and so on": "open-ended",
    "as needed": "open-ended",
    "if possible": "open-ended",
    "some": "open-ended",
    "various": "open-ended",
    "several": "open-ended",
    "appropriate": "open-ended",
    "best practices": "open-ended",
    "and more": "open-ended",
}
_VAGUE_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in sorted(VAGUE_TERMS, key=len, reverse=True)) + r")\b", re.I
)
_NUMBER_RE = re.compile(r"\d")


@rule
def ambiguous_wording(spec: ProjectSpec) -> list[FindingDraft]:
    hits: dict[str, list[Evidence]] = {}
    for source, text in _sources(spec):
        for m in _VAGUE_RE.finditer(text):
            term = m.group(1).lower()
            hits.setdefault(term, [])
            if len(hits[term]) < 3:
                hits[term].append(
                    Evidence(source=source, quote=snippet(text, m.start(), m.end()), line=line_of(text, m.start()))
                )
    out: list[FindingDraft] = []
    for term, ev in sorted(hits.items())[:12]:
        kind = VAGUE_TERMS[term]
        quoted_has_number = any(_NUMBER_RE.search(e.quote) for e in ev)
        if kind == "measurable" and quoted_has_number:
            continue  # e.g. "fast (< 200 ms)" is already quantified
        out.append(
            _f(
                "AMB-001",
                term,
                category="ambiguous_wording",
                kind="confirmed_issue",
                title=f'Ambiguous term: "{term}"',
                explanation={
                    "measurable": f'"{term}" describes a quality without a measurable target.',
                    "subjective": f'"{term}" is subjective; different readers will interpret it differently.',
                    "open-ended": f'"{term}" leaves the list or scope open-ended.',
                }[kind],
                evidence=ev,
                severity="medium" if kind == "measurable" else "low",
                confidence="high",
                impact="The agent will pick its own interpretation, which may not match yours.",
                solution={
                    "measurable": f'Replace "{term}" with a measurable criterion (number, unit, condition).',
                    "subjective": f'Replace "{term}" with concrete, observable characteristics.',
                    "open-ended": f'Replace "{term}" with the complete, explicit list or scope.',
                }[kind],
                verification=f'The term "{term}" no longer appears without a concrete definition.',
            )
        )
    return out


_TBD_RE = re.compile(r"\b(tbd|todo|to be (decided|determined)|unknown|not sure|\?\?+)\b|\?\?+", re.I)


@rule
def unresolved_markers(spec: ProjectSpec) -> list[FindingDraft]:
    ev = _search(spec, _TBD_RE, limit=5)
    if not ev:
        return []
    return [
        _f(
            "UNR-001",
            "markers",
            category="unclear_boundaries",
            kind="unresolved_question",
            title="Unresolved placeholders in the specification",
            explanation="The text contains TBD/TODO/unknown markers that the agent cannot resolve.",
            evidence=ev,
            severity="medium",
            confidence="high",
            impact="The agent will guess or stall on these decisions.",
            solution="Decide each placeholder, or record it as an explicit assumption with a default.",
            verification="No TBD/TODO/unknown markers remain.",
        )
    ]


@rule
def unresolved_requirements(spec: ProjectSpec) -> list[FindingDraft]:
    out = []
    for r in spec.requirements:
        if r.status == "unresolved" or (r.kind == "assumption" and r.status == "proposed"):
            out.append(
                _f(
                    "UNR-002",
                    r.id,
                    category="unsupported_assumptions",
                    kind="unresolved_question",
                    title="Unresolved assumption awaiting a decision",
                    explanation="This item is not confirmed. It will be labelled as an assumption in generated prompts.",
                    evidence=[Evidence(source=f"requirement:{r.id}", quote=r.text[:200])],
                    severity="info",
                    confidence="high",
                    impact="The agent sees it as an assumption rather than a requirement.",
                    solution="Confirm it, reject it, or rewrite it as a firm requirement.",
                    verification="Item status is confirmed or rejected.",
                )
            )
    return out


_UNSUPPORTED_RE = re.compile(
    r"\b(obviously|as usual|the usual way|the standard way|like before|same as (before|last time)|you know|"
    r"everyone knows|of course)\b",
    re.I,
)


@rule
def unsupported_assumptions(spec: ProjectSpec) -> list[FindingDraft]:
    ev = _search(spec, _UNSUPPORTED_RE, limit=4)
    if not ev:
        return []
    return [
        _f(
            "ASM-001",
            "implicit",
            category="unsupported_assumptions",
            kind="assumption",
            title="Relies on unstated shared context",
            explanation="Phrases like 'as usual' or 'like before' assume context the agent does not have.",
            evidence=ev,
            severity="medium",
            confidence="medium",
            impact="The agent cannot know what 'usual' or 'before' refers to.",
            solution="Spell out the referenced convention, previous decision or example.",
            verification="Phrases referring to unstated context are replaced by explicit statements.",
        )
    ]


# --------------------------------------------------------------------------- consistency

_NEG_RE = re.compile(r"\b(not|never|no|without|don't|do not|must not|mustn't|cannot|can't|avoid)\b", re.I)


def _strip_negation(text: str) -> str:
    return _NEG_RE.sub(" ", text)


@rule
def duplicate_requirements(spec: ProjectSpec) -> list[FindingDraft]:
    reqs = [r for r in spec.requirements if r.status != "rejected"]
    out: list[FindingDraft] = []
    for i, a in enumerate(reqs):
        for b in reqs[i + 1 :]:
            if bool(_NEG_RE.search(a.text)) != bool(_NEG_RE.search(b.text)):
                continue  # handled by the contradiction rule
            exact = normalize(a.text) == normalize(b.text)
            sim = 1.0 if exact else jaccard(a.text, b.text)
            if sim < 0.8:
                continue
            key = "|".join(sorted([a.id, b.id]))
            out.append(
                _f(
                    "DUP-001",
                    key,
                    category="duplicate_requirements",
                    kind="confirmed_issue" if exact else "potential_risk",
                    title="Duplicate requirements" if exact else "Near-duplicate requirements",
                    explanation=f"Two requirements are {'identical' if exact else f'{sim:.0%} similar by word overlap'}.",
                    evidence=[
                        Evidence(source=f"requirement:{a.id}", quote=a.text[:200]),
                        Evidence(source=f"requirement:{b.id}", quote=b.text[:200]),
                    ],
                    severity="low",
                    confidence="high" if exact else "medium",
                    impact="Redundant instructions waste context and may drift apart when edited.",
                    solution="Merge them into one requirement.",
                    verification="Only one of the two remains.",
                )
            )
            if len(out) >= 10:
                return out
    return out


@rule
def negation_contradictions(spec: ProjectSpec) -> list[FindingDraft]:
    reqs = [r for r in spec.requirements if r.status != "rejected"]
    out: list[FindingDraft] = []
    for i, a in enumerate(reqs):
        for b in reqs[i + 1 :]:
            na, nb = bool(_NEG_RE.search(a.text)), bool(_NEG_RE.search(b.text))
            if na == nb:
                continue
            sim = jaccard(_strip_negation(a.text), _strip_negation(b.text))
            if sim < 0.7:
                continue
            key = "|".join(sorted([a.id, b.id]))
            out.append(
                _f(
                    "CON-001",
                    key,
                    category="contradictory_requirements",
                    kind="potential_risk",
                    title="Possible contradiction between requirements",
                    explanation=f"One requirement negates the other ({sim:.0%} word overlap once negation words are removed). "
                    "This is a heuristic indicator; please review.",
                    evidence=[
                        Evidence(source=f"requirement:{a.id}", quote=a.text[:200]),
                        Evidence(source=f"requirement:{b.id}", quote=b.text[:200]),
                    ],
                    severity="high",
                    confidence="medium",
                    impact="The agent must break one of the two instructions.",
                    solution="Keep one, reject the other, or add the condition under which each applies.",
                    verification="Only one of the conflicting requirements remains confirmed.",
                )
            )
    return out


_CONFLICT_PAIRS: list[tuple[str, re.Pattern[str], re.Pattern[str], str]] = [
    (
        "offline-vs-cloud",
        re.compile(r"\b(offline|local[- ]only|no internet|air[- ]?gapped|without (an )?internet)\b", re.I),
        re.compile(
            r"\b(requires?|call(s|ing)?|use(s)?|using|via|send(s)? (data )?to) (an? |the )?(cloud|hosted|remote|openai|saas)\b",
            re.I,
        ),
        "The text asks for offline/local-only operation but also mentions using a cloud/hosted service.",
    ),
    (
        "no-db-vs-db",
        re.compile(r"\b(no database|without (a )?database|no db)\b", re.I),
        re.compile(r"\b(postgres\w*|mysql|mongodb|store (it |data )?in (a |the )?database|sql database)\b", re.I),
        "The text says no database but also names a database or database storage.",
    ),
    (
        "no-auth-vs-auth",
        re.compile(
            r"\b(no (login|authentication|accounts?|sign[- ]?in)|without (login|authentication|accounts?))\b", re.I
        ),
        re.compile(r"\b(user accounts?|sign[- ]?up|log ?in page|oauth|registration)\b", re.I),
        "The text says no authentication/accounts but also describes login or account features.",
    ),
    (
        "single-vs-multi-user",
        re.compile(r"\bsingle[- ]user\b", re.I),
        re.compile(r"\b(multi[- ]?(user|tenant)|teams? collaborat\w*|shared workspaces?)\b", re.I),
        "The text describes a single-user application but also multi-user/team features.",
    ),
    (
        "no-deps-vs-deps",
        re.compile(r"\b(no (external )?dependencies|zero dependencies|dependency[- ]free)\b", re.I),
        re.compile(r"\b(npm install|pip install|use (the )?\w+ (library|package|framework))\b", re.I),
        "The text forbids dependencies but also asks to use a library or package.",
    ),
]


@rule
def keyword_contradictions(spec: ProjectSpec) -> list[FindingDraft]:
    out: list[FindingDraft] = []
    for key, left, right, explanation in _CONFLICT_PAIRS:
        ev_l = _search(spec, left, limit=2)
        ev_r = _search(spec, right, limit=2)
        if ev_l and ev_r:
            out.append(
                _f(
                    "CON-002",
                    key,
                    category="contradictory_requirements",
                    kind="potential_risk",
                    title="Contradiction indicator: " + key.replace("-", " "),
                    explanation=explanation + " This is a keyword heuristic; it may be a false positive.",
                    evidence=ev_l + ev_r,
                    severity="medium",
                    confidence="low",
                    impact="If real, the agent must violate one of the two instructions.",
                    solution="Clarify which statement wins, or under what conditions each applies.",
                    verification="Review the quoted statements; dismiss this finding if they are compatible.",
                )
            )
    return out


# --------------------------------------------------------------------------- risk heuristics

_PERF_RE = re.compile(
    r"\b(real[- ]?time|low[- ]latency|latency|large files?|big data|video|streaming|high[- ]throughput|"
    r"heavy load|concurrent users?|thousands of|millions of)\b",
    re.I,
)


def _has_numeric_nfr(spec: ProjectSpec) -> bool:
    texts = [r.text for r in spec.by_kind("non_functional")] + [spec.config.performance]
    return any(_NUMBER_RE.search(t) for t in texts if t)


@rule
def performance_risk(spec: ProjectSpec) -> list[FindingDraft]:
    ev = _search(spec, _PERF_RE, limit=4)
    if not ev or _has_numeric_nfr(spec):
        return []
    return [
        _f(
            "PRF-001",
            "performance",
            category="performance_risk",
            kind="potential_risk",
            title="Performance-sensitive work without measurable targets",
            explanation="The text mentions performance-sensitive aspects but no non-functional requirement "
            "or performance constraint contains a number.",
            evidence=ev,
            severity="medium",
            confidence="medium",
            impact="Implementation may be functionally correct but unusably slow, or over-engineered.",
            solution="Add measurable targets (e.g. latency percentile, file size, concurrent users, target hardware).",
            verification="A non-functional requirement or the performance field contains a numeric target.",
        )
    ]


_SCALE_RE = re.compile(
    r"\b(scal(e|able|ability|ing)|millions of users|high traffic|grow(th)? to|enterprise[- ]scale)\b", re.I
)


@rule
def scalability_risk(spec: ProjectSpec) -> list[FindingDraft]:
    ev = _search(spec, _SCALE_RE, limit=3)
    if not ev or _has_numeric_nfr(spec):
        return []
    return [
        _f(
            "SCL-001",
            "scalability",
            category="scalability_concern",
            kind="potential_risk",
            title="Scalability expectation without a target",
            explanation="Scale is mentioned but no expected load, data volume or growth figure is given.",
            evidence=ev,
            severity="medium",
            confidence="medium",
            impact="The agent may over-engineer for hypothetical scale or under-engineer for real scale.",
            solution="State expected users, requests/second or data volume, now and in 12 months.",
            alternative="Explicitly state that scale is not a concern for the first version.",
            verification="A non-functional requirement contains a numeric load or volume target.",
        )
    ]


_LATEST_RE = re.compile(r"\b(latest|newest|most recent|any version|bleeding[- ]edge)\b", re.I)


@rule
def compatibility_uncertainty(spec: ProjectSpec) -> list[FindingDraft]:
    ev = _search(spec, _LATEST_RE, limit=3)
    if not ev:
        return []
    return [
        _f(
            "CMP-001",
            "latest",
            category="compatibility_uncertainty",
            kind="potential_risk",
            title="Unpinned dependency versions",
            explanation="'Latest' or unspecified versions change over time and may be incompatible with each other.",
            evidence=ev,
            severity="low",
            confidence="medium",
            impact="Builds may break, or the agent may use APIs that differ from its training data.",
            solution="Pin major versions, or ask the agent to verify compatibility and record the versions used.",
            verification="Versions are pinned in the requirements or a lockfile is required.",
        )
    ]


_STACK_SPLIT_RE = re.compile(r"[,;/\n+]|\band\b", re.I)


@rule
def dependency_risk(spec: ProjectSpec) -> list[FindingDraft]:
    items = [t.strip() for t in _STACK_SPLIT_RE.split(spec.tech_stack) if t.strip()]
    if len(items) < 9:
        return []
    return [
        _f(
            "DEP-001",
            "stack-size",
            category="dependency_risk",
            kind="potential_risk",
            title=f"Large technology stack ({len(items)} items)",
            explanation="Many separate technologies increase integration, upgrade and compatibility risk.",
            evidence=[Evidence(source="tech_stack", quote=spec.tech_stack[:240])],
            severity="medium",
            confidence="medium",
            impact="More setup work, more failure modes, larger attack surface.",
            solution="Remove technologies that are not essential for the first version.",
            verification="Each listed technology maps to at least one requirement.",
        )
    ]


_COMPLEX_RE = re.compile(
    r"\b(micro-?services?|kubernetes|k8s|kafka|service mesh|event sourcing|cqrs|blockchain|multi-region|"
    r"distributed (system|cache|database))\b",
    re.I,
)


@rule
def unnecessary_complexity(spec: ProjectSpec) -> list[FindingDraft]:
    size = spec.config.project_size
    if size == "large":
        return []
    ev = _search(spec, _COMPLEX_RE, limit=4)
    if not ev:
        return []
    return [
        _f(
            "CPX-001",
            "complexity",
            category="unnecessary_complexity",
            kind="potential_risk",
            title="Heavyweight architecture for a " + (size or "unsized") + " project",
            explanation="Distributed-systems technology is mentioned but the project size is "
            + ("small." if size == "small" else "not stated."),
            evidence=ev,
            severity="medium" if size == "small" else "low",
            confidence="low",
            impact="Significant operational complexity that may not pay off.",
            solution="Start with the simplest architecture that meets the stated requirements; justify each heavy component.",
            alternative="Set project size to 'large' if this scale is genuinely required.",
            verification="Each heavy component is backed by a stated requirement.",
        )
    ]


_BULLET_RE = re.compile(r"^\s*([-*•]|\d+[.)])\s+", re.M)


@rule
def excessive_scope(spec: ProjectSpec) -> list[FindingDraft]:
    func = len(spec.by_kind("functional"))
    bullets = len(_BULLET_RE.findall(spec.idea))
    words_ = word_count(spec.idea)
    if func <= 20 and bullets <= 20 and words_ <= 1500:
        return []
    return [
        _f(
            "SCP-001",
            "scope",
            category="excessive_scope",
            kind="potential_risk",
            title="Very large scope for a single prompt",
            explanation=f"{func} functional requirements, {bullets} bullet points and {words_} words in the idea.",
            evidence=[
                Evidence(source="requirements", quote=f"functional={func}, idea bullets={bullets}, idea words={words_}")
            ],
            severity="medium",
            confidence="medium",
            impact="Agents lose track of requirements in very long tasks; quality drops toward the end.",
            solution="Split into phases, each with its own prompt and acceptance criteria.",
            verification="Each generated prompt covers ≤20 functional requirements.",
        )
    ]


def analyze(spec: ProjectSpec, rules: Iterable[Rule] = RULES) -> list[FindingDraft]:
    """Run all rules. Output order is deterministic (rule order, then rule output order)."""
    out: list[FindingDraft] = []
    seen: set[str] = set()
    for r in rules:
        for f in r(spec):
            if f.fingerprint not in seen:
                seen.add(f.fingerprint)
                out.append(f)
    return out
