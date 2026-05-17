"""MAXIA Oracle — request ID propagation middleware (audit fix H6).

Assigns a unique identifier to every HTTP request for log correlation.
If the client sends an X-Request-ID header, it is reused (≤64 chars,
ASCII printable). Otherwise a UUID4 hex string is generated.

Implemented as a pure ASGI middleware (not BaseHTTPMiddleware) to avoid
known buffering issues on SSE/MCP streaming responses.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Final

from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER: Final[str] = "x-request-id"
_MAX_LEN: Final[int] = 64

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def _extract_or_generate(scope: Scope) -> str:
    headers = dict(scope.get("headers", []))
    raw = headers.get(
        REQUEST_ID_HEADER.encode(), b""
    ).decode("ascii", errors="ignore").strip()
    if raw and len(raw) <= _MAX_LEN and raw.isprintable():
        return raw
    return uuid.uuid4().hex


class RequestIDMiddleware:
    """Pure ASGI middleware — propagates X-Request-ID on every request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        rid = _extract_or_generate(scope)
        request_id_var.set(rid)
        scope.setdefault("state", {})["request_id"] = rid

        async def send_with_rid(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", rid.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_rid)
