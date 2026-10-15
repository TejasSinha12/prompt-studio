from tests.conftest import create_project


def test_roundtrip_bundle(client):
    p = create_project(client, tags=["a"])
    client.post(f"/api/projects/{p['id']}/requirements", json={"kind": "functional", "text": "Parse quotes"})
    client.post(f"/api/projects/{p['id']}/analysis")
    client.post("/api/prompts", json={"project_id": p["id"], "title": "T", "content": "v1"})
    bundle = client.get(f"/api/projects/{p['id']}/bundle").json()
    r = client.post("/api/projects/import", json=bundle)
    assert r.status_code == 201
    new = r.json()
    assert new["id"] != p["id"] and new["requirements"][0]["text"] == "Parse quotes"
    assert client.get(f"/api/prompts?project_id={new['id']}").json()["total"] == 1
    assert len(client.get(f"/api/projects/{new['id']}/recommendations").json()) == len(
        bundle["project"]["recommendations"]
    )


def test_malformed_import_rejected(client):
    assert (
        client.post(
            "/api/projects/import", json={"format": "other", "format_version": 1, "project": {"name": "x"}}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/projects/import",
            json={
                "format": "prompt-studio-project",
                "format_version": 1,
                "project": {"name": "x", "requirements": [{"kind": "bogus", "text": "y"}]},
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/projects/import", content=b"{not json", headers={"Content-Type": "application/json"}
        ).status_code
        == 422
    )


def test_import_failure_is_atomic(client):
    bundle = {
        "format": "prompt-studio-project",
        "format_version": 1,
        "project": {
            "name": "Dup",
            "prompts": [{"title": "t", "versions": [{"number": 1, "content": "a"}, {"number": 1, "content": "b"}]}],
        },
    }
    r = client.post("/api/projects/import", json=bundle)
    assert r.status_code == 400
    assert client.get("/api/projects").json()["total"] == 0


def test_oversized_import_rejected(client):
    big = "x" * (10 * 1024 * 1024 + 1)
    r = client.post("/api/projects/import", content=big, headers={"Content-Type": "application/json"})
    assert r.status_code == 413
