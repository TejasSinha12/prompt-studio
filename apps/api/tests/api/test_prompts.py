from tests.conftest import create_project


def setup_prompt(client):
    p = create_project(client)
    client.post(f"/api/projects/{p['id']}/requirements", json={"kind": "acceptance", "text": "sample.csv converts"})
    gen = client.post(f"/api/projects/{p['id']}/generate", json={}).json()["results"]
    assert [g["variant"] for g in gen] == ["concise", "balanced", "detailed"]
    bal = gen[1]
    r = client.post(
        "/api/prompts",
        json={
            "project_id": p["id"],
            "title": "CSV prompt",
            "content": bal["content"],
            "variant": "balanced",
            "generator": "rule_based",
            "category": "feature",
        },
    )
    assert r.status_code == 201
    return p, r.json(), gen


def test_generate_variants_preserve_requirements(client):
    _, _, gen = setup_prompt(client)
    for g in gen:
        assert g["generator"] == "rule_based"
        assert all(x["preserved"] for x in g["preservation"])
        assert g["token_estimate"] > 0


def test_versions_are_immutable_and_restore_creates_new(client):
    p, prompt, _ = setup_prompt(client)
    pid = prompt["id"]
    v1 = prompt["current_version"]
    v2 = client.post(f"/api/prompts/{pid}/versions", json={"content": "Manual edit\n", "variant": "manual"}).json()
    assert v2["number"] == 2 and v2["parent_version_id"] == v1["id"] and "lines" in v2["change_summary"]
    v3 = client.post(f"/api/prompts/{pid}/versions/{v1['id']}/restore").json()
    assert v3["number"] == 3 and v3["content"] == v1["content"] and "Restored from v1" in v3["change_summary"]
    detail = client.get(f"/api/prompts/{pid}").json()
    assert [v["number"] for v in detail["versions"]] == [3, 2, 1]
    assert detail["current_version"]["id"] == v3["id"]
    assert v1["source_snapshot"]["project_id"] == p["id"]
    assert client.get(f"/api/prompts/{pid}/versions/{v1['id']}").json()["content"] == v1["content"]


def test_db_trigger_blocks_version_update(client, data_dir):
    import sqlite3

    import pytest

    _, prompt, _ = setup_prompt(client)
    conn = sqlite3.connect(data_dir / "prompt_studio.db")
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        conn.execute("UPDATE prompt_versions SET content='x' WHERE id=?", (prompt["current_version"]["id"],))
    conn.close()


def test_library_filters_favorite_duplicate_delete(client):
    _, prompt, _ = setup_prompt(client)
    pid = prompt["id"]
    client.patch(f"/api/prompts/{pid}", json={"favorite": True, "tags": ["cli"]})
    assert client.get("/api/prompts?favorite=true").json()["total"] == 1
    assert client.get("/api/prompts?tag=cli").json()["total"] == 1
    assert client.get("/api/prompts?q=sample.csv").json()["total"] == 1  # content search
    dup = client.post(f"/api/prompts/{pid}/duplicate").json()
    assert (
        dup["title"] == "CSV prompt (copy)"
        and dup["current_version"]["content"] == prompt["current_version"]["content"]
    )
    assert client.delete(f"/api/prompts/{dup['id']}").status_code == 400
    assert client.delete(f"/api/prompts/{dup['id']}?confirm=true").status_code == 204


def test_evaluation_rule_based_and_compare(client):
    _, prompt, _ = setup_prompt(client)
    vid = prompt["current_version"]["id"]
    e = client.post(f"/api/prompt-versions/{vid}/evaluate").json()
    assert e["engine"] == "rule_based" and e["score"] is not None and "Heuristic" in e["formula"]
    assert any(d["id"] == "feasibility" and d["method"] == "requires_local_ai" for d in e["dimensions"])
    v2 = client.post(f"/api/prompts/{prompt['id']}/versions", json={"content": "Make it fast etc."}).json()
    e2 = client.post(f"/api/prompt-versions/{v2['id']}/evaluate").json()
    assert e2["score"] < e["score"]
    assert len(client.get("/api/evaluations").json()) == 2


def test_exports(client):
    p, prompt, _ = setup_prompt(client)
    vid = prompt["current_version"]["id"]
    for fmt in [
        "markdown",
        "text",
        "claude_md",
        "agents_md",
        "cursor_mdc",
        "plan",
        "tasks",
        "tests",
        "spec",
        "template",
    ]:
        r = client.post(f"/api/projects/{p['id']}/export", json={"format": fmt, "version_id": vid})
        assert r.status_code == 200 and r.json()["content"], fmt
    z = client.post(f"/api/projects/{p['id']}/export.zip", json={"formats": ["claude_md", "agents_md"]})
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip" and z.content[:2] == b"PK"
