import asyncio
import json

import httpx
import pytest

from prompt_studio.providers.base import ProviderError
from prompt_studio.providers.openai_compatible import OpenAICompatibleProvider


def make(handler):
    return OpenAICompatibleProvider("http://127.0.0.1:1234/v1", max_retries=1, transport=httpx.MockTransport(handler))


def test_status_and_models():
    def h(req):
        assert "authorization" not in req.headers  # never sends credentials
        return httpx.Response(200, json={"data": [{"id": "qwen3-8b", "owned_by": "lmstudio"}, {"id": "a-model"}]})

    p = make(h)
    assert p.base_url == "http://127.0.0.1:1234"
    assert asyncio.run(p.status()).available
    assert [m.name for m in asyncio.run(p.list_models())] == ["a-model", "qwen3-8b"]


def test_chat_uses_json_schema_and_strips_thinking():
    seen = []

    def h(req):
        body = json.loads(req.content)
        seen.append(body)
        return httpx.Response(200, json={"choices": [{"message": {"content": '<think>hmm</think>{"ok": true}'}}]})

    out = asyncio.run(make(h).chat("m", "sys", "user", schema={"type": "object"}, options={"temperature": 0.1}))
    assert out == '{"ok": true}'
    assert seen[0]["response_format"]["type"] == "json_schema" and seen[0]["temperature"] == 0.1


def test_schema_unsupported_falls_back_to_prompt():
    calls = []

    def h(req):
        body = json.loads(req.content)
        calls.append(body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": "response_format not supported"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    assert asyncio.run(make(h).chat("m", "sys", "u", schema={"type": "object"})) == "{}"
    assert len(calls) == 2 and "JSON schema" in calls[1]["messages"][0]["content"]


def test_unavailable_and_retry():
    attempts = []

    def down(req):
        attempts.append(1)
        raise httpx.ConnectError("refused", request=req)

    st = asyncio.run(make(down).status())
    assert not st.available and st.error_code == "unavailable"
    with pytest.raises(ProviderError) as e:
        asyncio.run(make(down).chat("m", "s", "u"))
    assert e.value.code == "unavailable" and len(attempts) == 3  # status (no retry) + chat with 1 retry


def test_settings_switch_provider_and_validate_endpoint(client):
    r = client.put(
        "/api/settings", json={"provider": "openai_compatible", "openai_compatible_url": "http://8.8.8.8:1234"}
    )
    assert r.status_code == 400
    r = client.put(
        "/api/settings", json={"provider": "openai_compatible", "openai_compatible_url": "http://127.0.0.1:9"}
    )
    assert r.status_code == 200
    m = client.get("/api/models").json()
    assert m["provider"] == "openai_compatible" and m["available"] is False
