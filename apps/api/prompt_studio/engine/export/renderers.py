"""Export renderers. Pure functions from a spec / prompt text to file content.

All renderers work offline and never include application settings or secrets.
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import UTC, datetime

from pydantic import BaseModel

from ..spec import ProjectSpec
from ..templates.profiles import get_profile

KIND_LABELS = {
    "goal": "Goals",
    "functional": "Functional requirements",
    "non_functional": "Non-functional requirements",
    "security": "Security requirements",
    "constraint": "Constraints",
    "acceptance": "Acceptance criteria",
    "assumption": "Assumptions",
    "out_of_scope": "Out of scope",
}


class ExportFile(BaseModel):
    format: str
    filename: str
    media_type: str
    content: str


FORMATS: dict[str, tuple[str, str, str]] = {
    # id: (label, default filename, media type)
    "markdown": ("Markdown prompt", "prompt.md", "text/markdown"),
    "text": ("Plain text prompt", "prompt.txt", "text/plain"),
    "claude_md": ("CLAUDE.md", "CLAUDE.md", "text/markdown"),
    "agents_md": ("AGENTS.md", "AGENTS.md", "text/markdown"),
    "cursor_mdc": ("Cursor rule (.mdc)", "project.mdc", "text/markdown"),
    "plan": ("Implementation plan", "IMPLEMENTATION_PLAN.md", "text/markdown"),
    "tasks": ("Task breakdown", "TASKS.md", "text/markdown"),
    "tests": ("Testing instructions", "TESTING.md", "text/markdown"),
    "spec": ("Project specification", "SPEC.md", "text/markdown"),
    "template": ("Reusable prompt template", "prompt-template.md", "text/markdown"),
}


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:60] or "project"


def to_plain_text(md: str) -> str:
    out = []
    in_code = False
    for line in md.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            out.append(line)
            continue
        h = re.match(r"^(#{1,6})\s+(.*)$", line)
        if h:
            title = h.group(2).strip()
            out.append(title.upper() if len(h.group(1)) <= 2 else title)
            continue
        line = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", line)
        line = re.sub(r"^\s*- \[ \]\s+", "[ ] ", line)
        out.append(line)
    return "\n".join(out).strip() + "\n"


def _req_sections(spec: ProjectSpec, kinds: list[str], level: str = "##") -> str:
    parts = []
    for kind in kinds:
        items = spec.by_kind(kind)
        if items:
            parts.append(f"{level} {KIND_LABELS[kind]}\n\n" + "\n".join(f"- {r.text}" for r in items))
    return "\n\n".join(parts)


def _open_assumptions(spec: ProjectSpec) -> list[str]:
    return [
        r.text
        for r in spec.requirements
        if r.status == "unresolved" or (r.kind == "assumption" and r.status == "proposed")
    ]


def _instruction_body(spec: ProjectSpec) -> str:
    """Stable project conventions for instruction files (not task-specific prose)."""
    cfg = spec.config
    parts = [f"# {spec.name}"]
    if spec.description:
        parts.append(spec.description)
    stack = [x for x in [spec.tech_stack, cfg.language, cfg.framework] if x]
    if stack:
        parts.append("## Tech stack\n\n" + "\n".join(f"- {s}" for s in stack))
    if cfg.architecture:
        parts.append("## Architecture\n\n" + cfg.architecture)
    rules = [r.text for r in spec.by_kind("constraint")] + [r.text for r in spec.by_kind("security")]
    if cfg.restrictions:
        rules.append(cfg.restrictions)
    if rules:
        parts.append("## Rules\n\n" + "\n".join(f"- {r}" for r in rules))
    if cfg.testing:
        parts.append("## Testing\n\n" + cfg.testing)
    nfr = spec.by_kind("non_functional")
    if nfr:
        parts.append("## Quality standards\n\n" + "\n".join(f"- {r.text}" for r in nfr))
    oos = spec.by_kind("out_of_scope")
    if oos:
        parts.append("## Do not\n\n" + "\n".join(f"- {r.text}" for r in oos))
    return "\n\n".join(parts) + "\n"


def render(fmt: str, spec: ProjectSpec, prompt: str | None) -> ExportFile:
    if fmt not in FORMATS:
        raise ValueError(f"Unknown export format: {fmt}")
    label, filename, media = FORMATS[fmt]
    prompt = prompt or ""
    slug = _slug(spec.name)
    if fmt == "markdown":
        content = prompt
        filename = f"{slug}-prompt.md"
    elif fmt == "text":
        content = to_plain_text(prompt)
        filename = f"{slug}-prompt.txt"
    elif fmt in {"claude_md", "agents_md"}:
        content = _instruction_body(spec)
        profile = get_profile("claude_code" if fmt == "claude_md" else "codex")
        if profile.size_guidance:
            lines = content.count("\n")
            if fmt == "claude_md" and lines > 200:
                content += f"\n<!-- Prompt Studio: {lines} lines; {profile.size_guidance} -->\n"
    elif fmt == "cursor_mdc":
        desc = (spec.description or spec.name).replace("\n", " ").replace('"', "'")[:200]
        content = f'---\ndescription: "{desc}"\nglobs:\nalwaysApply: true\n---\n\n' + _instruction_body(spec)
        filename = f"{slug}.mdc"
    elif fmt == "plan":
        func = spec.by_kind("functional") + spec.by_kind("goal")
        steps = "\n".join(
            f"{n}. Implement: {r.text}\n   - Verify with a test or documented check." for n, r in enumerate(func, 1)
        )
        acc = "\n".join(f"- [ ] {r.text}" for r in spec.by_kind("acceptance"))
        content = (
            f"# Implementation plan — {spec.name}\n\n## Objective\n\n{spec.idea or spec.description}\n\n"
            + (f"## Steps\n\n{steps}\n\n" if steps else "")
            + (f"## Exit criteria\n\n{acc}\n\n" if acc else "")
            + (
                _req_sections(spec, ["constraint", "out_of_scope"]) + "\n"
                if spec.by_kind("constraint") or spec.by_kind("out_of_scope")
                else ""
            )
        )
    elif fmt == "tasks":
        items = (
            spec.by_kind("goal")
            + spec.by_kind("functional")
            + spec.by_kind("non_functional")
            + spec.by_kind("security")
        )
        content = (
            f"# Tasks — {spec.name}\n\n"
            + ("\n".join(f"- [ ] {r.text}" for r in items) or "- [ ] (no confirmed requirements yet)")
            + "\n"
        )
        acc = spec.by_kind("acceptance")
        if acc:
            content += "\n## Done when\n\n" + "\n".join(f"- [ ] {r.text}" for r in acc) + "\n"
    elif fmt == "tests":
        acc = spec.by_kind("acceptance")
        func = spec.by_kind("functional")
        content = f"# Testing instructions — {spec.name}\n\n"
        if spec.config.testing:
            content += f"## Expectations\n\n{spec.config.testing}\n\n"
        if acc:
            content += "## Acceptance tests\n\n" + "\n".join(f"- {r.text}" for r in acc) + "\n\n"
        if func:
            content += "## Behaviour to cover\n\n" + "\n".join(f"- {r.text}" for r in func) + "\n"
        if not (spec.config.testing or acc or func):
            content += "No testing expectations, acceptance criteria or functional requirements are confirmed yet.\n"
    elif fmt == "spec":
        content = f"# {spec.name} — Specification\n\n"
        if spec.description:
            content += spec.description + "\n\n"
        content += f"## Original idea\n\n{spec.idea or '(none)'}\n\n"
        if spec.tech_stack:
            content += f"## Technology stack\n\n{spec.tech_stack}\n\n"
        content += _req_sections(
            spec, ["goal", "functional", "non_functional", "security", "constraint", "acceptance", "out_of_scope"]
        )
        opens = _open_assumptions(spec)
        if opens:
            content += "\n\n## Open assumptions (unconfirmed)\n\n" + "\n".join(f"- {t}" for t in opens)
        content += "\n"
    else:  # template
        content = re.sub(re.escape(spec.name), "{{project_name}}", prompt) if spec.name else prompt
        content = (
            "<!-- Reusable prompt template generated by Prompt Studio. Replace {{placeholders}} before use. -->\n\n"
            + content
        )
        filename = f"{slug}-template.md"
    return ExportFile(format=fmt, filename=filename, media_type=media, content=content)


def render_zip(spec: ProjectSpec, prompt: str | None, formats: list[str]) -> bytes:
    buf = io.BytesIO()
    now = datetime.now(UTC).timetuple()[:6]
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fmt in formats:
            f = render(fmt, spec, prompt)
            path = f".cursor/rules/{f.filename}" if fmt == "cursor_mdc" else f.filename
            info = zipfile.ZipInfo(path, date_time=now)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, f.content)
    return buf.getvalue()
