"""Controlled agent handoff: explicit, contained, no silent overwrites, no execution."""

import os

import pytest

from tests.conftest import create_project


@pytest.fixture
def target(tmp_path, monkeypatch):
    from prompt_studio.services import codebase_service

    monkeypatch.setattr(
        codebase_service,
        "BLOCKED_ROOTS",
        [p for p in codebase_service.BLOCKED_ROOTS if str(p) not in {"/private", "/var"}],
    )
    d = tmp_path / "repo"
    d.mkdir()
    return d


def body(path, **kw):
    return {"path": str(path), "profile_id": "claude_code", **kw}


def test_preview_writes_nothing(client, target):
    p = create_project(client)
    r = client.post(f"/api/projects/{p['id']}/handoff/preview", json=body(target)).json()
    assert [f["path"] for f in r["files"]] == ["CLAUDE.md", ".prompt-studio/PROMPT.md", ".prompt-studio/TASKS.md"]
    assert r["command"].startswith("cd ") and "claude" in r["command"]
    assert list(target.iterdir()) == []


def test_write_requires_confirmation(client, target):
    p = create_project(client)
    r = client.post(f"/api/projects/{p['id']}/handoff/write", json=body(target, confirm="yes"))
    assert r.status_code == 400 and list(target.iterdir()) == []


def test_write_and_no_silent_overwrite(client, target):
    p = create_project(client)
    (target / "CLAUDE.md").write_text("MY OWN RULES")
    r = client.post(f"/api/projects/{p['id']}/handoff/write", json=body(target, confirm="WRITE")).json()
    assert r["skipped_existing"] == ["CLAUDE.md"] and (target / "CLAUDE.md").read_text() == "MY OWN RULES"
    assert (target / ".prompt-studio" / "PROMPT.md").read_text().strip()
    r = client.post(
        f"/api/projects/{p['id']}/handoff/write",
        json=body(target, confirm="WRITE", overwrite=["CLAUDE.md", ".prompt-studio/PROMPT.md"]),
    ).json()
    assert "CLAUDE.md" in r["written"] and len(r["backups"]) == 2
    backup = next(b for b in r["backups"] if b.startswith("CLAUDE.md"))
    assert (target / backup).read_text() == "MY OWN RULES" and "# CSV tool" in (target / "CLAUDE.md").read_text()


def test_cursor_and_codex_layouts(client, target):
    p = create_project(client)
    c = client.post(f"/api/projects/{p['id']}/handoff/preview", json=body(target, profile_id="cursor")).json()
    assert c["files"][0]["path"].startswith(".cursor/rules/") and c["files"][0]["path"].endswith(".mdc")
    x = client.post(f"/api/projects/{p['id']}/handoff/preview", json=body(target, profile_id="codex")).json()
    assert x["files"][0]["path"] == "AGENTS.md" and "codex" in x["command"]
    g = client.post(f"/api/projects/{p['id']}/handoff/preview", json=body(target, profile_id="generic_llm"))
    assert g.status_code == 400


def test_symlinked_target_refused(client, target, tmp_path):
    p = create_project(client)
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, target / ".prompt-studio")
    r = client.post(f"/api/projects/{p['id']}/handoff/write", json=body(target, confirm="WRITE"))
    assert r.status_code == 400 and r.json()["error"]["code"] == "symlink_refused"
    assert list(outside.iterdir()) == []


def test_system_dir_refused(client):
    p = create_project(client)
    assert client.post(f"/api/projects/{p['id']}/handoff/write", json=body("/etc", confirm="WRITE")).status_code == 400


def test_command_path_is_shell_quoted(client, tmp_path, monkeypatch):
    from prompt_studio.services import codebase_service

    monkeypatch.setattr(codebase_service, "BLOCKED_ROOTS", [])
    d = tmp_path / "it's a; dir"
    d.mkdir()
    p = create_project(client)
    cmd = client.post(f"/api/projects/{p['id']}/handoff/preview", json=body(d)).json()["command"]
    assert "'\"'\"'" in cmd  # single quote escaped by shlex.quote; `;` is inside quotes
