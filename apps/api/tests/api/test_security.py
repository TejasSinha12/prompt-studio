import re
from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import create_project

PKG = Path(__file__).resolve().parents[2] / "prompt_studio"


def test_mutation_requires_header(client):
    r = client.post("/api/projects", json={"name": "x"}, headers={"X-Prompt-Studio": ""})
    assert r.status_code == 403 and r.json()["error"]["code"] == "missing_client_header"


def test_foreign_origin_rejected(client):
    r = client.post("/api/projects", json={"name": "x"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden_origin"
    ok = client.post("/api/projects", json={"name": "x"}, headers={"Origin": "http://127.0.0.1:3000"})
    assert ok.status_code == 201


def test_no_cors_headers(client):
    r = client.options(
        "/api/projects", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
    )
    assert "access-control-allow-origin" not in r.headers


def test_untrusted_host_rejected(client):
    r = client.get("/api/health", headers={"Host": "attacker.example:8000"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "untrusted_host"


def test_api_token_enforced(data_dir, monkeypatch):
    monkeypatch.setenv("PROMPT_STUDIO_API_TOKEN", "s3cret-token")
    from prompt_studio.config import get_settings

    get_settings.cache_clear()
    from prompt_studio.main import create_app

    with TestClient(create_app(), base_url="http://127.0.0.1:8000") as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/projects").status_code == 401
        assert c.get("/api/projects", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert c.get("/api/projects", headers={"Authorization": "Bearer s3cret-token"}).status_code == 200


def test_oversized_body(client):
    big = "x" * (2 * 1024 * 1024 + 10)
    r = client.post(
        "/api/projects", content=f'{{"name":"a","original_idea":"{big}"}}', headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 413


def test_overlong_field_rejected(client):
    r = client.post("/api/projects", json={"name": "a" * 201})
    assert r.status_code == 422
    r = client.post("/api/projects", json={"name": "ok", "config": {"tone": "t" * 5001}})
    assert r.status_code == 422


def test_too_many_tags_rejected(client):
    assert client.post("/api/projects", json={"name": "a", "tags": [f"t{i}" for i in range(21)]}).status_code == 422


def test_security_headers(client):
    r = client.get("/api/health")
    assert (
        r.headers["x-content-type-options"] == "nosniff"
        and "frame-ancestors 'none'" in r.headers["content-security-policy"]
    )


def test_error_does_not_leak(client):
    r = client.get("/api/projects/does-not-exist")
    assert (
        r.status_code == 404
        and "Traceback" not in r.text
        and r.json() == {"error": {"code": "not_found", "message": "Project not found."}}
    )


def test_swagger_ui_disabled(client):
    assert client.get("/docs").status_code == 404  # would load CDN assets


def test_no_shell_execution_in_source():
    pattern = re.compile(r"\b(subprocess|os\.system|os\.popen|eval\(|exec\(|pty\.spawn)")
    hits = [str(p) for p in PKG.rglob("*.py") if pattern.search(p.read_text())]
    assert hits == []


def test_no_cloud_endpoints_in_source():
    pattern = re.compile(r"https?://(?!127\.0\.0\.1|localhost)[a-z0-9.-]+\.(com|ai|io|net)", re.I)
    allowed = {"profiles.py"}  # documentation URLs only, never requested
    hits = [p.name for p in PKG.rglob("*.py") if p.name not in allowed and pattern.search(p.read_text())]
    assert hits == []


def test_export_bundle_contains_no_settings(client):
    client.put("/api/settings", json={"model": "secret-model-name", "ollama_url": "http://127.0.0.1:11434"})
    p = create_project(client)
    text = client.get(f"/api/projects/{p['id']}/bundle").text
    assert "secret-model-name" not in text and "ollama" not in text.lower()


def test_settings_reject_remote_endpoint(client):
    r = client.put("/api/settings", json={"ollama_url": "http://169.254.169.254/"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_endpoint"
    r = client.put("/api/settings", json={"ollama_url": "http://user:pw@127.0.0.1:11434"})
    assert r.status_code == 400
    r = client.put("/api/settings", json={"ollama_url": "http://10.0.0.5:11434", "allow_remote_ollama": True})
    assert r.status_code == 200  # explicit opt-in only
