from tests.conftest import create_project


def analyze(client, pid):
    r = client.post(f"/api/projects/{pid}/analysis")
    assert r.status_code == 200, r.text
    return r.json()


def recs(client, pid, status=None):
    q = f"?status={status}" if status else ""
    return client.get(f"/api/projects/{pid}/recommendations{q}").json()


def find(items, title_part):
    return next(i for i in items if title_part in i["title"])


def test_analysis_creates_labelled_findings_and_recommendations(client):
    p = create_project(client)
    out = analyze(client, p["id"])
    assert out["run"]["engine"] == "rule_based"
    assert all(f["engine"] == "rule_based" for f in out["findings"])
    assert out["new_recommendations"] > 0
    assert any(f["category"] == "missing_acceptance_criteria" for f in out["findings"])


def test_approve_adds_confirmed_requirement_and_resolves_finding(client):
    p = create_project(client)
    analyze(client, p["id"])
    rec = find(recs(client, p["id"]), "acceptance criteria")
    r = client.post(f"/api/recommendations/{rec['id']}/approve", json={"note": "ok"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    reqs = client.get(f"/api/projects/{p['id']}").json()["requirements"]
    added = [x for x in reqs if x["recommendation_id"] == rec["id"]]
    assert added and added[0]["status"] == "confirmed" and added[0]["kind"] == "acceptance"
    out = analyze(client, p["id"])
    assert not [f for f in out["findings"] if f["rule_id"] == "ACC-001" and f["status"] == "open"]


def test_approve_with_edit_and_alternative(client):
    p = create_project(client)
    analyze(client, p["id"])
    rec = find(recs(client, p["id"]), "testing")
    r = client.post(f"/api/recommendations/{rec['id']}/approve", json={"alternative_index": 0})
    assert r.status_code == 200
    assert "Chose alternative" in r.json()["events"][-1]["note"]
    texts = [x["text"] for x in client.get(f"/api/projects/{p['id']}").json()["requirements"]]
    assert rec["alternatives"][0]["requirement_text"] in texts


def test_placeholder_requires_edit(client):
    p = create_project(client)
    analyze(client, p["id"])
    rec = find(recs(client, p["id"]), 'Define "fast"')
    assert rec["needs_edit"] is True
    r = client.post(f"/api/recommendations/{rec['id']}/approve", json={})
    assert r.status_code == 400 and r.json()["error"]["code"] == "needs_edit"
    r = client.post(
        f"/api/recommendations/{rec['id']}/approve",
        json={"requirement_text": "Converting a 100 MB file takes under 10 seconds"},
    )
    assert r.status_code == 200


def test_rejected_never_reproposed(client):
    p = create_project(client)
    analyze(client, p["id"])
    rec = find(recs(client, p["id"]), "acceptance criteria")
    assert (
        client.post(f"/api/recommendations/{rec['id']}/reject", json={"note": "not now"}).json()["status"] == "rejected"
    )
    analyze(client, p["id"])
    analyze(client, p["id"])
    same = [r for r in recs(client, p["id"]) if r["fingerprint"] == rec["fingerprint"]]
    assert len(same) == 1 and same[0]["status"] == "rejected"


def test_status_transitions_and_history(client):
    p = create_project(client)
    analyze(client, p["id"])
    rec = recs(client, p["id"])[0]
    rid = rec["id"]
    assert client.post(f"/api/recommendations/{rid}/defer", json={}).json()["status"] == "deferred"
    assert client.post(f"/api/recommendations/{rid}/defer", json={}).status_code == 409
    assert client.post(f"/api/recommendations/{rid}/restore", json={}).json()["status"] == "proposed"
    assert client.post(f"/api/recommendations/{rid}/reject", json={}).json()["status"] == "rejected"
    restored = client.post(f"/api/recommendations/{rid}/restore", json={"note": "reconsidered"}).json()
    assert restored["status"] == "proposed"
    assert [e["to_status"] for e in restored["events"]] == ["proposed", "deferred", "proposed", "rejected", "proposed"]


def test_edit_recorded_in_history(client):
    p = create_project(client)
    analyze(client, p["id"])
    rec = find(recs(client, p["id"]), "acceptance criteria")
    r = client.patch(f"/api/recommendations/{rec['id']}", json={"requirement_text": "CSV with 3 rows gives 3 objects"})
    assert r.json()["requirement_text"] == "CSV with 3 rows gives 3 objects"
    assert "Edited" in r.json()["events"][-1]["note"]


def test_dismissed_finding_stays_dismissed(client):
    p = create_project(client)
    f = analyze(client, p["id"])["findings"][0]
    client.patch(f"/api/findings/{f['id']}", json={"status": "dismissed"})
    again = {x["fingerprint"]: x for x in analyze(client, p["id"])["findings"]}
    assert again[f["fingerprint"]]["status"] == "dismissed"


def test_clarification_answer_becomes_requirement(client):
    p = create_project(client)
    analyze(client, p["id"])
    qs = client.get(f"/api/projects/{p['id']}/clarifications").json()
    q = next(x for x in qs if x["suggested_kind"] == "acceptance")
    r = client.post(
        f"/api/projects/{p['id']}/clarifications",
        json={"question": q["question"], "answer": "sample.csv converts exactly", "kind": "acceptance"},
    )
    assert r.status_code == 201 and r.json()["source"] == "clarification"
