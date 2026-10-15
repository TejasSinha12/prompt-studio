"""Security middleware (pure ASGI).

* Host allowlist (DNS-rebinding defence).
* Optional bearer token (PROMPT_STUDIO_API_TOKEN).
* Mutating requests must carry `X-Prompt-Studio: 1`; a present `Origin`
  must be an allowed local origin (CSRF defence). No CORS headers are ever
  emitted, so browsers will not let other origins send the custom header.
* Request body size limit, enforced on Content-Length and while streaming.
* Defensive response headers.
"""

from __future__ import annotations

import hmac
import json
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import Settings

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
LARGE_BODY_SUFFIXES = ("/import",)
SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cache-control", b"no-store"),
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
    (b"cross-origin-resource-policy", b"same-origin"),
]


class BodyTooLarge(Exception):
    pass


def _host_name(host_header: str) -> str:
    host_header = host_header.strip().lower()
    if host_header.startswith("["):
        return host_header[: host_header.find("]") + 1]
    return host_header.rsplit(":", 1)[0] if ":" in host_header else host_header


async def _send_json(send: Send, status: int, code: str, message: str) -> None:
    body = json.dumps({"error": {"code": code, "message": message}}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                *SECURITY_HEADERS,
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class SecurityMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self.allowed_origins = {o.rstrip("/").lower() for o in settings.allowed_origins}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        path: str = scope.get("path", "")
        method: str = scope.get("method", "GET")

        if _host_name(headers.get("host", "")) not in ALLOWED_HOSTS:
            await _send_json(send, 400, "untrusted_host", "Requests must use a loopback host name.")
            return

        token = self.settings.api_token
        if token and path.startswith("/api/") and path != "/api/health":
            auth = headers.get("authorization", "")
            if not hmac.compare_digest(auth.encode(), f"Bearer {token}".encode()):
                await _send_json(send, 401, "unauthorized", "Missing or invalid API token.")
                return

        if method in MUTATING:
            origin = headers.get("origin")
            if origin is not None and origin.rstrip("/").lower() not in self.allowed_origins:
                await _send_json(send, 403, "forbidden_origin", "Cross-origin requests are not allowed.")
                return
            if headers.get("x-prompt-studio") != "1":
                await _send_json(
                    send, 403, "missing_client_header", "Mutating requests must include the X-Prompt-Studio header."
                )
                return

        limit = self.settings.max_import_bytes if path.endswith(LARGE_BODY_SUFFIXES) else self.settings.max_body_bytes
        declared = headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > limit:
                    await _send_json(send, 413, "payload_too_large", f"Request body exceeds {limit} bytes.")
                    return
            except ValueError:
                await _send_json(send, 400, "bad_request", "Invalid Content-Length.")
                return

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise BodyTooLarge
            return message

        async def secure_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                existing = {k.lower() for k, _ in message.get("headers", [])}
                extra: list[Any] = [h for h in SECURITY_HEADERS if h[0] not in existing]
                message = {**message, "headers": [*message.get("headers", []), *extra]}
            await send(message)

        try:
            await self.app(scope, limited_receive, secure_send)
        except BodyTooLarge:
            if not response_started:
                await _send_json(send, 413, "payload_too_large", f"Request body exceeds {limit} bytes.")
