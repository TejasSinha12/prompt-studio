"""Offline workflow: no API keys, Ollama unreachable, fresh DB, and every
non-loopback socket connection blocked for the duration of the test.

This proves the application makes no external connections in this workflow.
It is not the same as a physically disconnected machine.
"""

import socket

import pytest

from tests.conftest import create_project


@pytest.fixture
def block_external(monkeypatch):
    attempts = []
    real_connect = socket.socket.connect

    def guarded(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host not in {"127.0.0.1", "::1", "localhost"} and not host.startswith("/"):
            attempts.append(host)
            raise OSError(f"external network blocked in test: {host}")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    real_gai = socket.getaddrinfo

    def guarded_gai(host, *a, **k):
        if host not in {"127.0.0.1", "::1", "localhost", None}:
            attempts.append(host)
            raise OSError("DNS blocked in test")
        return real_gai(host, *a, **k)

    monkeypatch.setattr(socket, "getaddrinfo", guarded_gai)
    return attempts


def test_offline_workflow(client, block_external, monkeypatch):
    for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert client.get("/api/projects").json()["total"] == 0  # fresh database
    models = client.get("/api/models").json()  # real provider -> closed loopback port
    assert models["available"] is False

    p = create_project(client)
    out = client.post(f"/api/projects/{p['id']}/analysis").json()
    assert out["findings"] and out["run"]["engine"] == "rule_based"
    rec = client.get(f"/api/projects/{p['id']}/recommendations").json()[0]
    if rec["needs_edit"]:
        client.post(f"/api/recommendations/{rec['id']}/approve", json={"requirement_text": "Concrete decision"})
    else:
        client.post(f"/api/recommendations/{rec['id']}/approve", json={})
    gen = client.post(f"/api/projects/{p['id']}/generate", json={}).json()["results"]
    pr = client.post("/api/prompts", json={"project_id": p["id"], "title": "t", "content": gen[1]["content"]}).json()
    v2 = client.post(f"/api/prompts/{pr['id']}/versions", json={"content": gen[2]["content"]}).json()
    client.post(f"/api/prompts/{pr['id']}/versions/{pr['current_version']['id']}/restore")
    assert client.post(f"/api/prompt-versions/{v2['id']}/evaluate").json()["score"] is not None
    for fmt in ("markdown", "text", "claude_md", "agents_md", "cursor_mdc"):
        assert client.post(f"/api/projects/{p['id']}/export", json={"format": fmt}).status_code == 200
    assert client.post("/api/backups").status_code == 201
    assert block_external == [], f"external network attempted: {block_external}"
