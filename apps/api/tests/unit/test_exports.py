import io
import zipfile

from prompt_studio.engine.export.renderers import FORMATS, render, render_zip, to_plain_text
from tests.unit.test_builder import make


def test_every_format_renders():
    for fmt in FORMATS:
        f = render(fmt, make(), "## Role\n\nDo **it**")
        assert f.content.strip(), fmt


def test_cursor_mdc_frontmatter():
    c = render("cursor_mdc", make(), "").content
    assert c.startswith("---\ndescription:") and "alwaysApply: true" in c


def test_plain_text_strips_markdown():
    t = to_plain_text("## Title\n\nUse **bold** and `code` and [link](http://x)\n- [ ] item")
    assert "**" not in t and "`" not in t and "TITLE" in t and "[ ] item" in t


def test_zip_contains_files():
    data = render_zip(make(), "x", ["claude_md", "agents_md", "cursor_mdc"])
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert "CLAUDE.md" in names and "AGENTS.md" in names and any(n.startswith(".cursor/rules/") for n in names)


def test_rejected_not_exported():
    assert "Stream rows" not in render("spec", make(), "").content
