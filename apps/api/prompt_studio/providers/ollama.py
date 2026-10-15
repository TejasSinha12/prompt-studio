"""Ollama provider (HTTP API on a local endpoint).

API used: GET /api/version, GET /api/tags, POST /api/show, POST /api/chat
(non-streaming, optional `format` JSON schema for structured output).
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

from .base import ModelDetails, ModelInfo, ProviderError, ProviderStatus

log = logging.getLogger(__name__)

_RETRYABLE_STATUS = {502, 503, 504}
_THINK_RE = re.compile(r"<think>.*?(</think>|$)", re.S)
# (endpoint, model) -> capabilities reported by /api/show. Avoids a lookup per request.
_CAPABILITIES: dict[tuple[str, str], list[str]] = {}


def strip_thinking(text: str) -> str:
    """Remove inline reasoning blocks some models emit even when thinking is disabled."""
    return _THINK_RE.sub("", text).strip()


class OllamaProvider:
    id = "ollama"

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 120.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
        think: bool | None = None,
    ) -> None:
        # None: never send the flag. True/False: sent only to models reporting the "thinking" capability.
        self.think = think
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds, connect=3.0)
        self.max_retries = max(0, min(max_retries, 5))
        self._transport = transport

    def _client(self, timeout: httpx.Timeout | None = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout or self.timeout,
            transport=self._transport,
            follow_redirects=False,
            trust_env=False,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        timeout: httpx.Timeout | None = None,
        retries: int | None = None,
    ) -> httpx.Response:
        attempts = (self.max_retries if retries is None else retries) + 1
        last: ProviderError | None = None
        for attempt in range(attempts):
            try:
                async with self._client(timeout) as client:
                    resp = await client.request(method, path, json=json)
                if resp.status_code in _RETRYABLE_STATUS:
                    last = ProviderError("http_error", f"Ollama returned HTTP {resp.status_code}.")
                elif resp.status_code == 404 and path in {"/api/chat", "/api/show"}:
                    raise ProviderError("model_missing", _error_text(resp) or "Model not found in Ollama.")
                elif resp.status_code >= 400:
                    raise ProviderError("http_error", f"Ollama returned HTTP {resp.status_code}: {_error_text(resp)}")
                else:
                    return resp
            except httpx.ConnectError:
                last = ProviderError("unavailable", f"Could not connect to Ollama at {self.base_url}. Is it running?")
            except httpx.TimeoutException:
                # Read timeouts are not retried: the model is likely slow, retrying multiplies the wait.
                raise ProviderError(
                    "timeout", "The local model did not respond within the configured timeout."
                ) from None
            except httpx.HTTPError as e:
                last = ProviderError("unavailable", f"Connection to Ollama failed ({type(e).__name__}).")
            if attempt < attempts - 1:
                await asyncio.sleep(min(0.25 * 2**attempt, 2.0))
        assert last is not None
        raise last

    async def status(self) -> ProviderStatus:
        try:
            resp = await self._request("GET", "/api/version", timeout=httpx.Timeout(3.0), retries=0)
            version = resp.json().get("version")
            return ProviderStatus(provider=self.id, endpoint=self.base_url, available=True, version=version)
        except ProviderError as e:
            return ProviderStatus(
                provider=self.id, endpoint=self.base_url, available=False, error=e.message, error_code=e.code
            )
        except ValueError:
            return ProviderStatus(
                provider=self.id,
                endpoint=self.base_url,
                available=False,
                error="Endpoint did not return valid JSON; is this an Ollama server?",
                error_code="http_error",
            )

    async def list_models(self) -> list[ModelInfo]:
        resp = await self._request("GET", "/api/tags", timeout=httpx.Timeout(10.0, connect=3.0), retries=0)
        try:
            data = resp.json()
            out = []
            for m in data.get("models", []):
                d = m.get("details") or {}
                out.append(
                    ModelInfo(
                        name=str(m.get("name") or m.get("model")),
                        size_bytes=m.get("size"),
                        parameter_size=d.get("parameter_size"),
                        quantization=d.get("quantization_level"),
                        family=d.get("family"),
                        modified_at=m.get("modified_at"),
                    )
                )
            return sorted(out, key=lambda x: x.name)
        except (ValueError, TypeError, AttributeError) as e:
            raise ProviderError("invalid_output", "Unexpected model list format from Ollama.") from e

    async def show(self, model: str) -> ModelDetails:
        resp = await self._request(
            "POST", "/api/show", json={"model": model}, timeout=httpx.Timeout(10.0, connect=3.0), retries=0
        )
        try:
            data = resp.json()
            info = data.get("model_info") or {}
            ctx = next((v for k, v in info.items() if k.endswith(".context_length") and isinstance(v, int)), None)
            d = data.get("details") or {}
            return ModelDetails(
                name=model,
                context_length=ctx,
                capabilities=list(data.get("capabilities") or []),
                parameter_size=d.get("parameter_size"),
                quantization=d.get("quantization_level"),
                family=d.get("family"),
            )
        except (ValueError, TypeError, AttributeError) as e:
            raise ProviderError("invalid_output", "Unexpected model details format from Ollama.") from e

    async def chat(
        self,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        body: dict[str, Any] = {
            "model": model,
            "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": options or {},
        }
        if schema is not None:
            body["format"] = schema
        if self.think is not None and "thinking" in await self._capabilities(model):
            body["think"] = self.think
        resp = await self._request("POST", "/api/chat", json=body)
        try:
            content = resp.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as e:
            raise ProviderError("invalid_output", "Ollama response did not contain a message.") from e
        if not isinstance(content, str):
            raise ProviderError("invalid_output", "Ollama message content was not text.")
        return strip_thinking(content)

    async def _capabilities(self, model: str) -> list[str]:
        key = (self.base_url, model)
        if key not in _CAPABILITIES:
            try:
                _CAPABILITIES[key] = (await self.show(model)).capabilities
            except ProviderError as e:
                if e.code == "model_missing":
                    raise
                return []  # unknown: do not send the flag, and retry the lookup next time
        return _CAPABILITIES[key]


def _error_text(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("error", ""))[:300]
    except ValueError:
        return ""
