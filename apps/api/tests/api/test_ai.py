import json
import time

import httpx

from tests.conftest import create_project

GOOD = json.dumps(
    {
        "findings": [
            {
                "category": "missing_tests",
                "kind": "confirmed_issue",
                "title": "No error cases tested",
                "explanation": "Only happy path described.",
                "evidence_quote": "converts CSV files to JSON",
                "severity": "medium",
                "confidence": "high",
                "impact": "Bugs",
                "solution": "Add tests",
                "verification": "Tests exist",
                "proposed_requirement": {"kind": "acceptance", "text": "Malformed CSV yields a clear error"},
            }
        ]
    }
)


def wait(client, job_id, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/ai/jobs/{job_id}").json()
        if j["status"] not in {"queued", "running"}:
            return j
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def select_model(client):
    assert (
        client.put("/api/settings", json={"model": "llama3.2:3b", "ollama_url": "http://127.0.0.1:11434"}).status_code
        == 200
    )


def test_missing_ollama_reported(client):
    r = client.get("/api/models").json()
    assert r["available"] is False and r["error_code"] == "unavailable" and r["models"] == []


def test_models_listed(ai_client):
    select_model(ai_client)
    r = ai_client.get("/api/models").json()
    assert r["available"] and r["version"] == "0.12.0" and r["selected_model_installed"]
    assert r["models"][0]["parameter_size"] == "3.2B"
    d = ai_client.get("/api/models/details?name=llama3.2:3b").json()
    assert d["context_length"] == 131072


def test_job_without_model_fails_clearly(ai_client):
    p = create_project(ai_client)
    j = wait(ai_client, ai_client.post("/api/ai/jobs", json={"kind": "analysis", "project_id": p["id"]}).json()["id"])
    assert j["status"] == "failed" and j["error_code"] == "no_model"


def test_ai_analysis_valid_output_stored_and_labelled(ai_client, fake_ollama):
    select_model(ai_client)
    p = create_project(ai_client)
    fake_ollama.chat_responses = [GOOD]
    j = wait(ai_client, ai_client.post("/api/ai/jobs", json={"kind": "analysis", "project_id": p["id"]}).json()["id"])
    assert j["status"] == "succeeded", j
    assert j["result"]["engine"] == "local_ai" and j["result"]["repaired"] is False
    findings = ai_client.get(f"/api/projects/{p['id']}/findings").json()
    ai = [f for f in findings if f["engine"] == "local_ai"]
    assert ai and ai[0]["model"] == "llama3.2:3b" and ai[0]["confidence"] == "high"
    recs = [r for r in ai_client.get(f"/api/projects/{p['id']}/recommendations").json() if r["engine"] == "local_ai"]
    assert recs and recs[0]["status"] == "proposed"  # suggestion only, requires approval
    req = fake_ollama.chat_requests[0]
    assert req["format"]["type"] == "object" and "untrusted" in req["messages"][0]["content"]
    assert "<spec>" in req["messages"][1]["content"]


def test_malformed_output_repaired_once(ai_client, fake_ollama):
    select_model(ai_client)
    p = create_project(ai_client)
    fake_ollama.chat_responses = ["not json at all", GOOD]
    j = wait(ai_client, ai_client.post("/api/ai/jobs", json={"kind": "analysis", "project_id": p["id"]}).json()["id"])
    assert j["status"] == "succeeded" and j["result"]["repaired"] is True
    assert "did not match" in fake_ollama.chat_requests[1]["messages"][1]["content"]


def test_malformed_output_twice_fails_and_stores_nothing(ai_client, fake_ollama):
    select_model(ai_client)
    p = create_project(ai_client)
    fake_ollama.chat_responses = ['{"findings": [{"severity": "apocalyptic"}]}', "still bad"]
    j = wait(ai_client, ai_client.post("/api/ai/jobs", json={"kind": "analysis", "project_id": p["id"]}).json()["id"])
    assert j["status"] == "failed" and j["error_code"] == "invalid_output"
    assert len(fake_ollama.chat_requests) == 2  # bounded: exactly one repair
    assert ai_client.get(f"/api/projects/{p['id']}/findings").json() == []


def test_unverified_evidence_lowers_confidence(ai_client, fake_ollama):
    select_model(ai_client)
    p = create_project(ai_client)
    bad_quote = json.loads(GOOD)
    bad_quote["findings"][0]["evidence_quote"] = "text that is not in the spec"
    fake_ollama.chat_responses = [json.dumps(bad_quote)]
    wait(ai_client, ai_client.post("/api/ai/jobs", json={"kind": "analysis", "project_id": p["id"]}).json()["id"])
    f = ai_client.get(f"/api/projects/{p['id']}/findings").json()[0]
    assert f["confidence"] == "low" and "not found verbatim" in f["explanation"]


def test_transient_failure_retried(ai_client, fake_ollama):
    select_model(ai_client)
    p = create_project(ai_client)
    fake_ollama.chat_responses = [httpx.Response(503), GOOD]
    j = wait(ai_client, ai_client.post("/api/ai/jobs", json={"kind": "analysis", "project_id": p["id"]}).json()["id"])
    assert j["status"] == "succeeded"


def test_ollama_down_during_job(ai_client, fake_ollama):
    select_model(ai_client)
    p = create_project(ai_client)
    fake_ollama.available = False
    j = wait(ai_client, ai_client.post("/api/ai/jobs", json={"kind": "analysis", "project_id": p["id"]}).json()["id"])
    assert j["status"] == "failed" and j["error_code"] == "unavailable"


def test_optimize_flags_missing_and_rejected(ai_client, fake_ollama):
    select_model(ai_client)
    p = create_project(ai_client)
    ai_client.post(
        f"/api/projects/{p['id']}/requirements", json={"kind": "functional", "text": "Support semicolon delimiters"}
    )
    ai_client.post(
        f"/api/projects/{p['id']}/requirements",
        json={"kind": "functional", "text": "Upload results to S3", "status": "rejected"},
    )
    fake_ollama.chat_responses = ["```markdown\n## Task\nConvert CSV to JSON. Upload results to S3.\n```"]
    j = wait(ai_client, ai_client.post("/api/ai/jobs", json={"kind": "optimize", "project_id": p["id"]}).json()["id"])
    res = j["result"]
    assert res["content"].startswith("## Task")
    assert not res["preservation"][0]["preserved"]
    assert res["rejected_reintroduced"] == ["Upload results to S3"]
    assert len(res["warnings"]) == 2


def test_cancel_job(ai_client, fake_ollama):
    import asyncio

    select_model(ai_client)
    p = create_project(ai_client)

    async def slow(_):
        await asyncio.sleep(5)
        return GOOD

    fake_ollama.chat_responses = [slow]
    jid = ai_client.post("/api/ai/jobs", json={"kind": "analysis", "project_id": p["id"]}).json()["id"]
    time.sleep(0.05)
    dup = ai_client.post("/api/ai/jobs", json={"kind": "analysis", "project_id": p["id"]})
    assert dup.status_code == 409  # duplicate submission prevented
    ai_client.delete(f"/api/ai/jobs/{jid}")
    assert wait(ai_client, jid)["status"] == "cancelled"


def test_ai_evaluation_stored_separately(ai_client, fake_ollama):
    select_model(ai_client)
    p = create_project(ai_client)
    pr = ai_client.post("/api/prompts", json={"project_id": p["id"], "title": "t", "content": "Do it."}).json()
    vid = pr["current_version"]["id"]
    fake_ollama.chat_responses = [
        json.dumps({"score": 40, "summary": "Too vague", "concerns": [{"message": "No scope"}]})
    ]
    j = wait(ai_client, ai_client.post("/api/ai/jobs", json={"kind": "evaluate", "version_id": vid}).json()["id"])
    assert j["status"] == "succeeded"
    evs = ai_client.get(f"/api/prompt-versions/{vid}/evaluations").json()
    assert evs[0]["engine"] == "local_ai" and evs[0]["model"] == "llama3.2:3b"


def test_think_flag_only_for_thinking_models(ai_client, fake_ollama):
    from prompt_studio.providers import ollama

    ollama._CAPABILITIES.clear()
    p = create_project(ai_client)
    ai_client.put(
        "/api/settings", json={"model": "llama3.2:3b", "ollama_url": "http://127.0.0.1:11434", "thinking": True}
    )
    fake_ollama.chat_responses = [GOOD]
    wait(ai_client, ai_client.post("/api/ai/jobs", json={"kind": "analysis", "project_id": p["id"]}).json()["id"])
    assert "think" not in fake_ollama.chat_requests[-1]  # model does not report "thinking"

    ollama._CAPABILITIES.clear()
    fake_ollama.capabilities = ["completion", "thinking"]
    ai_client.put(
        "/api/settings", json={"model": "llama3.2:3b", "ollama_url": "http://127.0.0.1:11434", "thinking": False}
    )
    fake_ollama.chat_responses = [GOOD]
    wait(ai_client, ai_client.post("/api/ai/jobs", json={"kind": "analysis", "project_id": p["id"]}).json()["id"])
    assert fake_ollama.chat_requests[-1]["think"] is False


def test_inline_think_blocks_stripped(ai_client, fake_ollama):
    select_model(ai_client)
    p = create_project(ai_client)
    fake_ollama.chat_responses = ["<think>I should analyse carefully...</think>\n" + GOOD]
    j = wait(ai_client, ai_client.post("/api/ai/jobs", json={"kind": "analysis", "project_id": p["id"]}).json()["id"])
    assert j["status"] == "succeeded" and j["result"]["repaired"] is False
