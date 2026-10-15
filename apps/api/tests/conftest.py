"""Shared fixtures: isolated data dir per test, client on a loopback host, mock Ollama."""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

HEADERS = {"X-Prompt-Studio": "1"}


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPT_STUDIO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROMPT_STUDIO_OLLAMA_URL", "http://127.0.0.1:9")  # closed port: Ollama unavailable
    monkeypatch.delenv("PROMPT_STUDIO_API_TOKEN", raising=False)
    from prompt_studio import db
    from prompt_studio.config import get_settings

    get_settings.cache_clear()
    db.dispose_engine()
    yield tmp_path / "data"
    db.dispose_engine()
    get_settings.cache_clear()


class FakeOllama:
    """Programmable stand-in for the Ollama HTTP API, used via httpx.MockTransport."""

    def __init__(self) -> None:
        self.available = True
        self.models = [
            {
                "name": "llama3.2:3b",
                "size": 2_000_000_000,
                "details": {"parameter_size": "3.2B", "quantization_level": "Q4_K_M", "family": "llama"},
            }
        ]
        self.chat_responses: list[Any] = []  # str content, or callable(request_json) -> str, or Exception
        self.chat_requests: list[dict] = []
        self.capabilities = ["completion"]

    async def handler(self, request: httpx.Request) -> httpx.Response:
        if not self.available:
            raise httpx.ConnectError("refused", request=request)
        path = request.url.path
        if path == "/api/version":
            return httpx.Response(200, json={"version": "0.12.0"})
        if path == "/api/tags":
            return httpx.Response(200, json={"models": self.models})
        if path == "/api/show":
            return httpx.Response(
                200,
                json={
                    "model_info": {"llama.context_length": 131072},
                    "capabilities": self.capabilities,
                    "details": {"family": "llama"},
                },
            )
        if path == "/api/chat":
            body = json.loads(request.content)
            self.chat_requests.append(body)
            nxt = self.chat_responses.pop(0) if self.chat_responses else "{}"
            if isinstance(nxt, Exception):
                raise nxt
            if callable(nxt):
                nxt = nxt(body)
                if inspect.isawaitable(nxt):
                    nxt = await nxt
            if isinstance(nxt, httpx.Response):
                return nxt
            return httpx.Response(200, json={"message": {"role": "assistant", "content": nxt}})
        return httpx.Response(404, json={"error": "not found"})


@pytest.fixture
def fake_ollama() -> FakeOllama:
    return FakeOllama()


@pytest.fixture
def make_client(data_dir, fake_ollama) -> Callable[..., TestClient]:
    from prompt_studio.main import create_app
    from prompt_studio.providers.ollama import OllamaProvider

    clients: list[TestClient] = []

    def factory(use_fake: bool = True) -> TestClient:
        pf = None
        if use_fake:
            transport = httpx.MockTransport(fake_ollama.handler)
            pf = lambda s: OllamaProvider(  # noqa: E731
                s.ollama_url, s.timeout_seconds, s.max_retries, transport=transport, think=s.thinking
            )
        c = TestClient(create_app(pf), base_url="http://127.0.0.1:8000", headers=HEADERS)
        c.__enter__()
        clients.append(c)
        return c

    yield factory
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client(use_fake=False)


@pytest.fixture
def ai_client(make_client) -> TestClient:
    return make_client(use_fake=True)


def create_project(client: TestClient, **kw) -> dict:
    body = {
        "name": "CSV tool",
        "original_idea": "Build a command line tool that converts CSV files to JSON for "
        "analysts. It should be fast and user-friendly.",
        "config": {"task_category": "feature"},
    } | kw
    r = client.post("/api/projects", json=body)
    assert r.status_code == 201, r.text
    return r.json()
