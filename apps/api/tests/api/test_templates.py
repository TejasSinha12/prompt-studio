from tests.conftest import create_project


def test_builtin_and_custom_template_lifecycle(client):
    builtins = client.get("/api/templates").json()
    assert builtins and all(t["builtin"] for t in builtins)
    body = {
        "name": "API endpoint",
        "category": "feature",
        "idea": "Add endpoint [X]",
        "config": {"task_category": "feature", "language": "Python", "bogus": "dropped"},
        "requirements": [{"kind": "acceptance", "text": "Endpoint documented in OpenAPI"}],
    }
    tid = client.post("/api/templates", json=body).json()["id"]
    custom = next(t for t in client.get("/api/templates").json() if t["id"] == tid)
    assert custom["builtin"] is False and "bogus" not in custom["config"]

    p = client.post("/api/projects/from-template", json={"template_id": tid, "name": "From custom"}).json()
    assert p["config"]["language"] == "Python"
    assert [r["status"] for r in p["requirements"]] == ["proposed"]  # still requires review

    body["name"] = "Renamed"
    assert client.put(f"/api/templates/{tid}", json=body).status_code == 200
    assert client.delete(f"/api/templates/{tid}").status_code == 400
    assert client.delete(f"/api/templates/{tid}?confirm=true").status_code == 204


def test_builtin_templates_are_read_only(client):
    bid = client.get("/api/templates").json()[0]["id"]
    assert client.put(f"/api/templates/{bid}", json={"name": "x"}).json()["error"]["code"] == "builtin_template"
    assert client.delete(f"/api/templates/{bid}?confirm=true").status_code == 400


def test_save_project_as_template(client):
    p = create_project(client)
    client.post(f"/api/projects/{p['id']}/requirements", json={"kind": "security", "text": "Validate paths"})
    client.post(
        f"/api/projects/{p['id']}/requirements",
        json={"kind": "functional", "text": "Rejected one", "status": "rejected"},
    )
    client.post(f"/api/projects/{p['id']}/requirements", json={"kind": "assumption", "text": "UTF-8 input"})
    tid = client.post(
        f"/api/projects/{p['id']}/save-as-template", json={"name": "CSV tools", "include_idea": False}
    ).json()["id"]
    t = next(t for t in client.get("/api/templates").json() if t["id"] == tid)
    assert t["idea"] == "" and [r["text"] for r in t["requirements"]] == ["Validate paths"]
    assert t["category"] == "feature"


def test_unknown_template(client):
    assert client.post("/api/projects/from-template", json={"template_id": "nope", "name": "x"}).status_code == 404
