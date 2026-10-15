"""Deterministic prompt quality diagnostics.

Each dimension returns a 0–100 sub-score with the evidence used to compute it.
Judgment-based dimensions (implementation feasibility) are *not* scored by
rules; they are reported as `requires_local_ai` until a local-AI evaluation runs.

Aggregate score (HEURISTIC): the unweighted mean of all dimensions that have a
rule-based score. It measures coverage of good-practice signals in the text.
It is NOT a probability that an agent will succeed, nor a measure of the
quality of the resulting code.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from ..analyzer.rules import _CONFLICT_PAIRS, _NEG_RE, _VAGUE_RE, VAGUE_TERMS, _strip_negation
from ..text import estimate_tokens, jaccard, normalize, snippet, word_count

SCORE_FORMULA = (
    "Aggregate = arithmetic mean of the rule-based dimension scores (each 0–100). Dimensions that require "
    "local AI or do not apply are excluded. Heuristic only: it reflects the presence of clarity, coverage and "
    "verification signals in the text, not the probability of a successful outcome."
)


class EvalFinding(BaseModel):
    message: str
    evidence: list[str] = Field(default_factory=list)
    fix: str = ""


class Dimension(BaseModel):
    id: str
    name: str
    score: float | None
    method: str  # rule_based | local_ai | requires_local_ai | not_applicable
    summary: str
    findings: list[EvalFinding] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    score: float | None
    formula: str = SCORE_FORMULA
    dimensions: list[Dimension]
    metrics: dict[str, int | float]


_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.M)
_LIST_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)]|- \[[ x]\])\s+(.+)$", re.M)
_FILLER = [
    "please note that",
    "it is important to",
    "make sure to",
    "in order to",
    "basically",
    "really ",
    "very ",
    "just ",
    "as an ai",
    "feel free to",
    "i would like you to",
]


def _clamp(x: float) -> float:
    return round(max(0.0, min(100.0, x)), 1)


def _has(text: str, pattern: str) -> bool:
    return re.search(pattern, text, re.I) is not None


def _lines(text: str) -> list[str]:
    return [m.group(1).strip() for m in _LIST_RE.finditer(text)]


def _section_items(text: str, heading_pattern: str) -> list[str]:
    """List items under the first heading matching the pattern."""
    parts = re.split(r"^(#{1,6}\s+.+)$", text, flags=re.M)
    for i in range(1, len(parts), 2):
        if re.search(heading_pattern, parts[i], re.I):
            return _lines(parts[i + 1]) if i + 1 < len(parts) else []
    return []


def evaluate(text: str, coding: bool = True) -> EvaluationResult:
    words = word_count(text)
    tokens = estimate_tokens(text)
    dims: list[Dimension] = []

    # Clarity -------------------------------------------------------------
    vague: dict[str, list[str]] = {}
    for m in _VAGUE_RE.finditer(text):
        term = m.group(1).lower()
        quote = snippet(text, m.start(), m.end(), 30)
        if VAGUE_TERMS[term] == "measurable" and re.search(r"\d", quote):
            continue
        vague.setdefault(term, []).append(quote)
    clarity = _clamp(100 - 12 * len(vague))
    dims.append(
        Dimension(
            id="clarity",
            name="Clarity",
            score=clarity,
            method="rule_based",
            summary=f"{len(vague)} distinct vague term(s) found." if vague else "No vague terms from the checked list.",
            findings=[
                EvalFinding(message=f'Vague term "{t}"', evidence=q[:2], fix="Replace with a concrete criterion.")
                for t, q in sorted(vague.items())
            ],
        )
    )

    # Completeness ---------------------------------------------------------
    checks = {
        "objective/task statement": len(text.strip()) > 0 and words >= 8,
        "requirements list": len(_lines(text)) >= 1 or _has(text, r"\b(must|should|shall)\b"),
        "constraints": _has(text, r"\b(constraint|restriction|must not|do not|don't|never|out of scope)\b"),
        "acceptance criteria": _has(text, r"acceptance|done when|definition of done|success criteri"),
        "output / deliverables": _has(text, r"\b(deliverable|output|return|produce|format)\b"),
    }
    if coding:
        checks["testing expectations"] = _has(text, r"\btest")
    missing = [k for k, ok in checks.items() if not ok]
    dims.append(
        Dimension(
            id="completeness",
            name="Completeness",
            score=_clamp(100 * (len(checks) - len(missing)) / len(checks)),
            method="rule_based",
            summary=f"{len(checks) - len(missing)}/{len(checks)} expected elements present.",
            findings=[EvalFinding(message=f"Missing: {k}", fix=f"Add {k}.") for k in missing],
        )
    )

    # Consistency ----------------------------------------------------------
    items = [s for s in _lines(text) if word_count(s) >= 3]
    conflicts: list[EvalFinding] = []
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            if (
                bool(_NEG_RE.search(a)) != bool(_NEG_RE.search(b))
                and jaccard(_strip_negation(a), _strip_negation(b)) >= 0.7
            ):
                conflicts.append(
                    EvalFinding(
                        message="Possible contradiction (negation pair)",
                        evidence=[a[:160], b[:160]],
                        fix="Keep one statement or add the condition under which each applies.",
                    )
                )
    for key, left, right, _ in _CONFLICT_PAIRS:
        ml, mr = left.search(text), right.search(text)
        if ml and mr:
            conflicts.append(
                EvalFinding(
                    message=f"Contradiction indicator: {key}",
                    evidence=[snippet(text, ml.start(), ml.end(), 30), snippet(text, mr.start(), mr.end(), 30)],
                    fix="Clarify which statement applies.",
                )
            )
    dims.append(
        Dimension(
            id="consistency",
            name="Consistency",
            score=_clamp(100 - 25 * len(conflicts)),
            method="rule_based",
            summary=f"{len(conflicts)} contradiction indicator(s). Heuristic: cannot detect all contradictions.",
            findings=conflicts[:10],
        )
    )

    # Context sufficiency --------------------------------------------------
    ctx_signals = {
        "background / project context": _has(text, r"context|background|currently|existing"),
        "technology / environment": _has(
            text, r"stack|language|framework|python|typescript|java|react|version|environment"
        ),
        "audience or users": _has(text, r"\b(users?|audience|customers?|reader|team)\b"),
        "goal / purpose": _has(text, r"\b(goal|objective|so that|purpose|in order to|because)\b"),
    }
    if not coding:
        ctx_signals.pop("technology / environment")
    have = [k for k, v in ctx_signals.items() if v]
    dims.append(
        Dimension(
            id="context",
            name="Context sufficiency",
            score=_clamp(100 * len(have) / len(ctx_signals)),
            method="rule_based",
            summary=f"{len(have)}/{len(ctx_signals)} context signals present (keyword-based).",
            findings=[
                EvalFinding(message=f"No {k} found", fix=f"Describe the {k}.") for k in ctx_signals if k not in have
            ],
        )
    )

    # Constraint coverage --------------------------------------------------
    cons = [
        s
        for s in _lines(text)
        if _has(s, r"\b(must not|do not|don't|never|only|avoid|without|limit|maximum|minimum|at most|at least)\b")
    ]
    cons_score = _clamp(min(100, 40 * len(cons))) if cons else (40.0 if checks["constraints"] else 0.0)
    dims.append(
        Dimension(
            id="constraints",
            name="Constraint coverage",
            score=cons_score,
            method="rule_based",
            summary=f"{len(cons)} explicit constraint line(s).",
            findings=[]
            if cons
            else [
                EvalFinding(
                    message="No explicit constraints (must not / only / limits)",
                    fix="State what must not change and any limits.",
                )
            ],
        )
    )

    # Acceptance criteria --------------------------------------------------
    acc = _section_items(text, r"acceptance|done when|success")
    acc_score = 0.0 if not acc else (60.0 if len(acc) == 1 else 100.0)
    if not acc and checks["acceptance criteria"]:
        acc_score = 40.0
    dims.append(
        Dimension(
            id="acceptance",
            name="Acceptance criteria",
            score=acc_score,
            method="rule_based",
            summary=f"{len(acc)} acceptance criteria item(s) under an acceptance heading.",
            findings=[]
            if len(acc) >= 2
            else [
                EvalFinding(
                    message="Fewer than 2 explicit acceptance criteria",
                    fix="Add observable, testable completion criteria.",
                )
            ],
        )
    )

    # Testability ----------------------------------------------------------
    t_signals = {
        "acceptance criteria present": bool(acc) or checks["acceptance criteria"],
        "tests mentioned": _has(text, r"\btest"),
        "measurable values (numbers/units)": _has(
            text, r"\d+\s?(ms|s|seconds?|%|mb|gb|kb|users?|requests?|items?|px)\b"
        ),
        "verification step": _has(text, r"\b(verify|verification|check|run the|confirm|demonstrat)\w*"),
    }
    if not coding:
        t_signals.pop("tests mentioned")
    t_have = [k for k, v in t_signals.items() if v]
    dims.append(
        Dimension(
            id="testability",
            name="Testability",
            score=_clamp(100 * len(t_have) / len(t_signals)),
            method="rule_based",
            summary=f"{len(t_have)}/{len(t_signals)} testability signals.",
            findings=[EvalFinding(message=f"Missing: {k}") for k in t_signals if k not in t_have],
        )
    )

    # Security coverage ----------------------------------------------------
    if coding:
        s_signals = {
            "input validation": _has(text, r"validat|sanitiz"),
            "secrets handling": _has(text, r"secret|credential|api key|token|password"),
            "access control / privacy": _has(text, r"auth|permission|privacy|least[- ]privilege|access"),
            "error exposure": _has(text, r"stack trace|internal details|expos|leak"),
        }
        s_have = [k for k, v in s_signals.items() if v]
        dims.append(
            Dimension(
                id="security",
                name="Security coverage",
                score=_clamp(100 * len(s_have) / len(s_signals)),
                method="rule_based",
                summary=f"{len(s_have)}/{len(s_signals)} security topics mentioned. Mentioning a topic is not a guarantee of security.",
                findings=[EvalFinding(message=f"Not mentioned: {k}") for k in s_signals if k not in s_have],
            )
        )
    else:
        dims.append(
            Dimension(
                id="security",
                name="Security coverage",
                score=None,
                method="not_applicable",
                summary="Not applicable to non-coding prompts.",
            )
        )

    # Redundancy -----------------------------------------------------------
    units = [normalize(u) for u in re.split(r"(?<=[.!?])\s+|\n+", text) if word_count(u) >= 5]
    dupes: list[EvalFinding] = []
    seen: list[str] = []
    for u in units:
        if u.startswith("#"):
            continue
        if any(u == s or jaccard(u, s) >= 0.85 for s in seen):
            dupes.append(
                EvalFinding(
                    message="Repeated or near-duplicate statement", evidence=[u[:160]], fix="Remove the repetition."
                )
            )
        seen.append(u)
    ratio = len(dupes) / max(1, len(units))
    dims.append(
        Dimension(
            id="redundancy",
            name="Redundancy",
            score=_clamp(100 - 200 * ratio),
            method="rule_based",
            summary=f"{len(dupes)} of {len(units)} statements repeat earlier ones.",
            findings=dupes[:10],
        )
    )

    # Token efficiency -----------------------------------------------------
    lower = text.lower()
    filler = {f.strip(): lower.count(f) for f in _FILLER if lower.count(f)}
    filler_total = sum(filler.values())
    eff = 100 - 5 * filler_total - (20 if tokens > 6000 else 0)
    dims.append(
        Dimension(
            id="efficiency",
            name="Token efficiency",
            score=_clamp(eff),
            method="rule_based",
            summary=f"≈{tokens} tokens (estimate, not a tokenizer count); {filler_total} filler phrase(s).",
            findings=[
                EvalFinding(message=f'Filler phrase "{k}" ×{v}', fix="Remove or rephrase.") for k, v in filler.items()
            ]
            + (
                [
                    EvalFinding(
                        message="Very long prompt (>6000 estimated tokens)",
                        fix="Split into phases or move stable conventions into an instruction file.",
                    )
                ]
                if tokens > 6000
                else []
            ),
        )
    )

    # Feasibility — judgment-based ----------------------------------------
    dims.append(
        Dimension(
            id="feasibility",
            name="Implementation feasibility",
            score=None,
            method="requires_local_ai",
            summary="Judgment-based. Run a local-AI evaluation to assess; not scored by rules.",
        )
    )

    scored = [d.score for d in dims if d.score is not None and d.method == "rule_based"]
    agg = round(sum(scored) / len(scored), 1) if scored else None
    return EvaluationResult(
        score=agg,
        dimensions=dims,
        metrics={
            "characters": len(text),
            "words": words,
            "token_estimate": tokens,
            "lines": text.count("\n") + 1,
            "list_items": len(_lines(text)),
        },
    )
