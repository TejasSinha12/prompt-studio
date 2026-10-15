from tests.conftest import create_project


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_project_crud_lifecycle(client):
    p = create_project(client, tags=["CLI", "data"])
    assert [t["name"] for t in p["tags"]] == ["cli", "data"]
    r = client.patch(
        f"/api/projects/{p['id']}", json={"revision": p["revision"], "name": "Renamed", "description": "D"}
    )
    assert r.status_code == 200 and r.json()["name"] == "Renamed" and r.json()["revision"] == p["revision"] + 1

    dup = client.post(f"/api/projects/{p['id']}/duplicate").json()
    assert dup["name"] == "Renamed (copy)" and dup["id"] != p["id"]

    assert client.post(f"/api/projects/{p['id']}/archive").json()["archived"] is True
    assert client.get("/api/projects").json()["total"] == 1  # only the duplicate
    assert client.get("/api/projects?archived=true").json()["items"][0]["id"] == p["id"]
    assert client.post(f"/api/projects/{p['id']}/restore").json()["archived"] is False

    assert client.delete(f"/api/projects/{p['id']}").status_code == 400  # confirmation required
    assert client.delete(f"/api/projects/{p['id']}?confirm=true").status_code == 204
    assert client.get(f"/api/projects/{p['id']}").status_code == 404


def test_search_and_tag_filter(client):
    create_project(client, name="Alpha", tags=["x"])
    create_project(client, name="Beta", original_idea="Something about invoices")
    assert [i["name"] for i in client.get("/api/projects?q=invoice").json()["items"]] == ["Beta"]
    assert [i["name"] for i in client.get("/api/projects?tag=x").json()["items"]] == ["Alpha"]


def test_stale_revision_conflict(client):
    p = create_project(client)
    assert client.patch(f"/api/projects/{p['id']}", json={"revision": p["revision"], "name": "A"}).status_code == 200
    r = client.patch(f"/api/projects/{p['id']}", json={"revision": p["revision"], "name": "B"})
    assert r.status_code == 409 and r.json()["error"]["details"]["current_revision"] == p["revision"] + 1
    assert client.get(f"/api/projects/{p['id']}").json()["name"] == "A"  # no silent overwrite


def test_requirements_and_events(client):
    p = create_project(client)
    r = client.post(f"/api/projects/{p['id']}/requirements", json={"kind": "functional", "text": "Parse quoted fields"})
    assert r.status_code == 201
    rid = r.json()["id"]
    assert client.patch(f"/api/requirements/{rid}", json={"status": "rejected"}).json()["status"] == "rejected"
    assert client.delete(f"/api/requirements/{rid}").status_code == 204
    kinds = [e["kind"] for e in client.get(f"/api/projects/{p['id']}/events").json()]
    assert {"created", "requirement_added", "requirement_updated", "requirement_deleted"} <= set(kinds)


def test_invalid_requirement_kind(client):
    p = create_project(client)
    r = client.post(f"/api/projects/{p['id']}/requirements", json={"kind": "wish", "text": "x"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_template_creates_proposed_requirements(client):
    t = client.get("/api/templates").json()[0]
    p = client.post("/api/projects/from-template", json={"template_id": t["id"], "name": "From tpl"}).json()
    assert p["requirements"] and all(r["status"] == "proposed" for r in p["requirements"])


def test_persistence_across_app_restart(make_client):
    c1 = make_client(use_fake=False)
    p = create_project(c1)
    c1.__exit__(None, None, None)
    from prompt_studio import db

    db.dispose_engine()
    c2 = make_client(use_fake=False)
    assert c2.get(f"/api/projects/{p['id']}").json()["name"] == "CSV tool"


def test_timestamps_are_timezone_aware(client):
    p = create_project(client)
    assert p["created_at"].endswith(("Z", "+00:00"))
    assert client.get(f"/api/projects/{p['id']}").json()["updated_at"].endswith(("Z", "+00:00"))
