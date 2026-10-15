"""Provider for local servers that implement the OpenAI-compatible HTTP API
(LM Studio, llama.cpp `llama-server`, vLLM, LocalAI, ...).

Only `/v1/models` and `/v1/chat/completions` are used. No API key or
Authorization header is ever sent: this provider is meant for local servers.
Structured output is requested with `response_format` (json_schema); servers
that reject it get one retry without it, and the result is still validated
against the schema by the caller.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from .base import ModelDetails, ModelInfo, ProviderError, ProviderStatus
from .ollama import strip_thinking

_RETRYABLE_STATUS = {502, 503, 504}


class OpenAICompatibleProvider:
    id = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 120.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        if self.base_url.endswith("/v1"):
            self.base_url = self.base_url[:-3]
        self.timeout = httpx.Timeout(timeout_seconds, connect=3.0)
        self.max_retries = max(0, min(max_retries, 5))
        self._transport = transport

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        timeout: httpx.Timeout | None = None,
        retries: int | None = None,
    ) -> httpx.Response:
        attempts = (self.max_retries if retries is None else retries) + 1
        last: ProviderError | None = None
        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=timeout or self.timeout,
                    transport=self._transport,
                    follow_redirects=False,
                    trust_env=False,
                ) as client:
                    resp = await client.request(method, path, json=json_body)
                if resp.status_code in _RETRYABLE_STATUS:
                    last = ProviderError("http_error", f"Local server returned HTTP {resp.status_code}.")
                elif resp.status_code == 404 and path.endswith("/chat/completions"):
                    raise ProviderError("model_missing", "Model not found on the local server.")
                else:
                    return resp
            except httpx.ConnectError:
                last = ProviderError("unavailable", f"Could not connect to the local server at {self.base_url}.")
            except httpx.TimeoutException:
                raise ProviderError(
                    "timeout", "The local model did not respond within the configured timeout."
                ) from None
            except httpx.HTTPError as e:
                last = ProviderError("unavailable", f"Connection to the local server failed ({type(e).__name__}).")
            if attempt < attempts - 1:
                await asyncio.sleep(min(0.25 * 2**attempt, 2.0))
        assert last is not None
        raise last

    async def _models_json(self) -> list[dict[str, Any]]:
        resp = await self._request("GET", "/v1/models", timeout=httpx.Timeout(5.0, connect=3.0), retries=0)
        if resp.status_code >= 400:
            raise ProviderError("http_error", f"Local server returned HTTP {resp.status_code} for /v1/models.")
        try:
            data = resp.json().get("data", [])
            return [m for m in data if isinstance(m, dict) and m.get("id")]
        except (ValueError, AttributeError) as e:
            raise ProviderError(
                "invalid_output", "Unexpected /v1/models format; is this an OpenAI-compatible server?"
            ) from e

    async def status(self) -> ProviderStatus:
        try:
            await self._models_json()
            return ProviderStatus(provider=self.id, endpoint=self.base_url, available=True)
        except ProviderError as e:
            return ProviderStatus(
                provider=self.id, endpoint=self.base_url, available=False, error=e.message, error_code=e.code
            )

    async def list_models(self) -> list[ModelInfo]:
        return sorted(
            (ModelInfo(name=str(m["id"]), family=m.get("owned_by")) for m in await self._models_json()),
            key=lambda m: m.name,
        )

    async def show(self, model: str) -> ModelDetails:
        # The OpenAI-compatible API exposes no model metadata (context length, capabilities).
        if model not in {m.name for m in await self.list_models()}:
            raise ProviderError("model_missing", "Model not found on the local server.")
        return ModelDetails(name=model)

    async def chat(
        self,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        opts = options or {}
        body: dict[str, Any] = {
            "model": model,
            "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if "temperature" in opts:
            body["temperature"] = opts["temperature"]
        if schema is not None:
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "result", "schema": schema}}
        resp = await self._request("POST", "/v1/chat/completions", json_body=body)
        if resp.status_code == 400 and schema is not None:
            # Server does not support json_schema response_format: describe the schema in the prompt instead.
            body.pop("response_format")
            body["messages"][0]["content"] = (
                system + "\n\nRespond with ONLY a JSON object matching this JSON schema:\n" + json.dumps(schema)
            )
            resp = await self._request("POST", "/v1/chat/completions", json_body=body)
        if resp.status_code >= 400:
            raise ProviderError("http_error", f"Local server returned HTTP {resp.status_code}.")
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise ProviderError("invalid_output", "Local server response did not contain a message.") from e
        if not isinstance(content, str):
            raise ProviderError("invalid_output", "Local server message content was not text.")
        return strip_thinking(content)
