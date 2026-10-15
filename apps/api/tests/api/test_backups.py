import os

from tests.conftest import create_project


def test_backup_create_validate_restore(client, data_dir):
    p = create_project(client, name="Before")
    b = client.post("/api/backups").json()
    assert b["name"].startswith("prompt-studio-")
    v = client.post(f"/api/backups/{b['name']}/validate").json()
    assert v["valid"] and all(c["ok"] for c in v["checks"])
    client.patch(f"/api/projects/{p['id']}", json={"revision": p["revision"], "name": "After"})
    assert client.post(f"/api/backups/{b['name']}/restore", json={"confirm": "yes"}).status_code == 400
    r = client.post(f"/api/backups/{b['name']}/restore", json={"confirm": "RESTORE"})
    assert r.status_code == 200 and "pre-restore" in r.json()["safety_backup"]
    assert client.get(f"/api/projects/{p['id']}").json()["name"] == "Before"
    assert len(client.get("/api/backups").json()) == 2


def test_traversal_rejected(client, data_dir):
    for name in ["../prompt_studio.db", "..%2Fprompt_studio.db", "prompt-studio-x.sqlite3", "/etc/passwd"]:
        r = client.post(f"/api/backups/{name}/validate")
        assert r.status_code in {400, 404}, name


def test_symlink_backup_rejected(client, data_dir):
    target = data_dir / "outside.sqlite3"
    target.write_bytes(b"x")
    link = data_dir / "backups" / "prompt-studio-20260101-000000-000000.sqlite3"
    os.symlink(target, link)
    assert client.post(f"/api/backups/{link.name}/validate").status_code == 400
    assert client.post(f"/api/backups/{link.name}/restore", json={"confirm": "RESTORE"}).status_code == 400


def test_corrupt_backup_fails_validation_and_restore(client, data_dir):
    create_project(client)
    bad = data_dir / "backups" / "prompt-studio-20260101-000000-000001.sqlite3"
    bad.write_bytes(b"SQLite format 3\x00" + b"garbage" * 100)
    v = client.post(f"/api/backups/{bad.name}/validate").json()
    assert v["valid"] is False
    r = client.post(f"/api/backups/{bad.name}/restore", json={"confirm": "RESTORE"})
    assert r.status_code == 422
    assert client.get("/api/projects").json()["total"] == 1  # nothing changed


def test_delete_backup_requires_confirm(client):
    b = client.post("/api/backups").json()
    assert client.delete(f"/api/backups/{b['name']}").status_code == 400
    assert client.delete(f"/api/backups/{b['name']}?confirm=true").status_code == 204


def test_delete_all_data(client):
    create_project(client)
    client.put("/api/settings", json={"model": "m1", "ollama_url": "http://127.0.0.1:11434"})
    assert client.post("/api/data/delete-all", json={"confirm": "delete"}).status_code == 400
    r = client.post("/api/data/delete-all", json={"confirm": "DELETE ALL DATA"}).json()
    assert r["deleted"]["projects"] == 1 and "pre-delete" in r["safety_backup"]
    assert client.get("/api/projects").json()["total"] == 0
    assert client.get("/api/settings").json()["model"] == "m1"  # settings kept
