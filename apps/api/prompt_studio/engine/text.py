"""Pure text helpers shared by the deterministic engine. No I/O."""

from __future__ import annotations

import hashlib
import re

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9+#.\-]*", re.IGNORECASE)
_STOPWORDS = frozenset(
    "a an the and or of to in on for with by be is are was were it this that as at from must should "
    "will shall can could would may might have has had do does not no".split()
)


def normalize(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation at the ends."""
    return re.sub(r"\s+", " ", text.lower()).strip(" .;:,!-")


def words(text: str) -> list[str]:
    return [w.lower().rstrip(".") for w in _WORD_RE.findall(text)]


def content_tokens(text: str) -> set[str]:
    return {w for w in words(text) if w not in _STOPWORDS and len(w) > 1}


def jaccard(a: str, b: str) -> float:
    ta, tb = content_tokens(a), content_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def word_count(text: str) -> int:
    return len(text.split())


def estimate_tokens(text: str) -> int:
    """Approximate token count. NOT a real tokenizer.

    Uses the max of chars/4 and words*1.3, two common rules of thumb for
    English text with BPE tokenizers. Always label the result as an estimate.
    """
    if not text:
        return 0
    return round(max(len(text) / 4, word_count(text) * 1.3))


def fingerprint(*parts: str) -> str:
    h = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return h[:24]


def snippet(text: str, start: int, end: int, radius: int = 40) -> str:
    s = max(0, start - radius)
    e = min(len(text), end + radius)
    prefix = "…" if s > 0 else ""
    suffix = "…" if e < len(text) else ""
    return prefix + re.sub(r"\s+", " ", text[s:e]).strip() + suffix


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def contains_requirement(haystack: str, requirement: str) -> bool:
    """True if `requirement` is present in `haystack` (whitespace/case-insensitive)."""
    return normalize(requirement) in normalize(haystack)


def token_coverage(haystack: str, requirement: str) -> float:
    """Fraction of the requirement's content tokens present in haystack."""
    req = content_tokens(requirement)
    if not req:
        return 1.0
    hay = content_tokens(haystack)
    return len(req & hay) / len(req)
