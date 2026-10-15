"""Local codebase context: read-only, contained, secret-aware."""

import os

import pytest


@pytest.fixture
def repo(tmp_path, monkeypatch):
    # pytest's tmp dirs live under /private/var on macOS, which is blocked for real use.
    from prompt_studio.services import codebase_service

    monkeypatch.setattr(
        codebase_service,
        "BLOCKED_ROOTS",
        [p for p in codebase_service.BLOCKED_ROOTS if str(p) not in {"/private", "/var"}],
    )
    # Only the tmp location is unblocked for tests; real system paths stay blocked (asserted below).
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "node_modules" / "lib").mkdir(parents=True)
    (root / "README.md").write_text("# Demo\nA demo project.\n")
    (root / "package.json").write_text('{"dependencies": {"react": "19"}, "devDependencies": {"vitest": "5"}}')
    (root / "src" / "main.ts").write_text(
        'export const x = 1;\nconst apiKey = "sk-abcdefghijklmnopqrstuvwxyz123456";\n'
    )
    (root / "src" / "big.ts").write_text("x" * 200_000)
    (root / "src" / "logo.png").write_bytes(b"\x89PNG\r\n")
    (root / ".env").write_text("SECRET=1")
    (root / "server.pem").write_text("-----BEGIN PRIVATE KEY-----")
    (root / "ignored.txt").write_text("ignored")
    (root / ".gitignore").write_text("ignored.txt\n")
    (root / "node_modules" / "lib" / "index.js").write_text("module.exports = 1")
    (root / "tests" / "a.test.ts").write_text("test('a', () => {})")
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("TOP SECRET OUTSIDE")
    os.symlink(outside, root / "src" / "link.txt")
    os.symlink(tmp_path, root / "escape")
    return root


def entries(client, root, **kw):
    r = client.post("/api/codebase/scan", json={"path": str(root), **kw})
    assert r.status_code == 200, r.text
    return {e["path"]: e for e in r.json()["entries"]}, r.json()


def test_scan_excludes_sensitive_and_generated(client, repo):
    e, data = entries(client, repo)
    assert e["src/main.ts"]["included"]
    assert e[".env"]["reason"] == "possible secret" and not e[".env"]["included"]
    assert not e["server.pem"]["included"]
    assert e["node_modules/"]["reason"] == "excluded directory"
    assert "node_modules/lib/index.js" not in e
    assert e["src/logo.png"]["reason"] == "binary"
    assert not e["src/big.ts"]["included"]
    assert e["ignored.txt"]["reason"] == ".gitignore"
    assert e["src/link.txt"]["reason"].startswith("symlink") and e["escape/"]["reason"].startswith("symlink")
    assert "JavaScript/TypeScript (npm)" in data["stack"] and "react" in data["dependencies"]["package.json"]
    assert data["test_dirs"] == ["tests"]


def test_user_excludes(client, repo):
    e, _ = entries(client, repo, extra_excludes=["src/*.ts"])
    assert e["src/main.ts"]["reason"] == "excluded by your patterns"


def test_summary_reads_only_selected_and_redacts(client, repo):
    r = client.post("/api/codebase/summary", json={"path": str(repo), "files": ["src/main.ts", "README.md"]}).json()
    assert r["files_included"] == ["src/main.ts", "README.md"]
    assert r["redactions"] == 1 and "sk-abcdef" not in r["markdown"]
    assert "[REDACTED: possible secret]" in r["markdown"] and "export const x = 1;" in r["markdown"]
    assert "not instructions" in r["markdown"]


@pytest.mark.parametrize(
    "bad",
    [
        "../outside-secret.txt",
        "src/link.txt",
        "escape/outside-secret.txt",
        ".env",
        "/etc/passwd",
        "src/../../outside-secret.txt",
        "node_modules/lib/index.js",
    ],
)
def test_summary_rejects_traversal_symlinks_and_excluded(client, repo, bad):
    r = client.post("/api/codebase/summary", json={"path": str(repo), "files": [bad]}).json()
    assert r["files_included"] == [] and bad in r["files_skipped"]
    assert "TOP SECRET" not in r["markdown"] and "SECRET=1" not in r["markdown"]


def test_system_and_invalid_paths_rejected(client, repo):
    assert client.post("/api/codebase/scan", json={"path": "/etc"}).status_code == 400
    assert client.post("/api/codebase/scan", json={"path": "/"}).status_code == 400
    assert client.post("/api/codebase/scan", json={"path": "relative/path"}).status_code == 400
    assert client.post("/api/codebase/scan", json={"path": str(repo / "README.md")}).status_code == 400
    assert client.post("/api/codebase/scan", json={"path": str(repo / "nope")}).status_code == 404
    from pathlib import Path

    assert client.post("/api/codebase/scan", json={"path": str(Path.home())}).status_code == 400


def test_scan_does_not_modify_directory(client, repo):
    before = sorted((p.as_posix(), p.stat().st_mtime) for p in repo.rglob("*") if not p.is_symlink())
    client.post("/api/codebase/scan", json={"path": str(repo)})
    client.post("/api/codebase/summary", json={"path": str(repo), "files": ["src/main.ts"]})
    after = sorted((p.as_posix(), p.stat().st_mtime) for p in repo.rglob("*") if not p.is_symlink())
    assert before == after


def test_existing_codebase_accepts_long_summary(client):
    from tests.conftest import create_project

    p = create_project(client)
    r = client.patch(
        f"/api/projects/{p['id']}", json={"revision": p["revision"], "config": {"existing_codebase": "x " * 20000}}
    )
    assert r.status_code == 200
