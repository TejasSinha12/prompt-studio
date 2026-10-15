"""Local model provider interface."""

from __future__ import annotations

import ipaddress
from typing import Any, Protocol
from urllib.parse import urlparse

from pydantic import BaseModel


class ProviderError(Exception):
    """Error talking to a local model runtime. `code` is safe to show users."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code  # unavailable | timeout | model_missing | http_error | invalid_output | bad_endpoint
        self.message = message


class ProviderStatus(BaseModel):
    provider: str
    endpoint: str
    available: bool
    version: str | None = None
    error: str | None = None
    error_code: str | None = None


class ModelInfo(BaseModel):
    name: str
    size_bytes: int | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    family: str | None = None
    modified_at: str | None = None


class ModelDetails(BaseModel):
    name: str
    context_length: int | None = None
    capabilities: list[str] = []
    parameter_size: str | None = None
    quantization: str | None = None
    family: str | None = None


class LocalModelProvider(Protocol):
    id: str

    async def status(self) -> ProviderStatus: ...
    async def list_models(self) -> list[ModelInfo]: ...
    async def show(self, model: str) -> ModelDetails: ...
    async def chat(
        self,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> str: ...


LOOPBACK_NAMES = {"localhost", "localhost.localdomain"}


def is_loopback_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        return False
    if host in LOOPBACK_NAMES or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_endpoint(url: str, allow_remote: bool) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ProviderError("bad_endpoint", "Endpoint must be an http(s) URL with a host.")
    if parsed.username or parsed.password:
        raise ProviderError("bad_endpoint", "Credentials in the endpoint URL are not allowed.")
    if not allow_remote and not is_loopback_url(url):
        raise ProviderError(
            "bad_endpoint",
            "Endpoint must be a loopback address (127.0.0.1, ::1 or localhost). Enable 'allow remote endpoint' in "
            "Settings to use another host; prompt content would then leave this machine.",
        )
    return url.rstrip("/")
