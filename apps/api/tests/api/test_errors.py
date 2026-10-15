from sqlalchemy.exc import OperationalError

from tests.conftest import create_project


def test_database_failure_returns_503_without_leaking(client, monkeypatch):
    from prompt_studio.services import project_service

    def boom(self, data):
        raise OperationalError("INSERT secret user content", {}, Exception("database is locked"))

    monkeypatch.setattr(project_service.ProjectService, "create", boom)
    r = client.post("/api/projects", json={"name": "x"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "database_unavailable"
    assert "secret" not in r.text


def test_unexpected_error_generic(client, monkeypatch):
    from fastapi.testclient import TestClient

    from prompt_studio.services import project_service

    monkeypatch.setattr(project_service.ProjectService, "list", lambda *a, **k: 1 / 0)
    c = TestClient(client.app, base_url="http://127.0.0.1:8000", raise_server_exceptions=False)
    r = c.get("/api/projects")
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal_error" and "ZeroDivision" not in r.text


def test_unknown_route(client):
    assert client.get("/api/nope").json()["error"]["code"] == "not_found"


def test_dashboard(client):
    create_project(client)
    d = client.get("/api/dashboard").json()
    assert d["counts"]["projects"] == 1 and d["recent_projects"]
