"""Shared security middleware: API key auth, rate limiting, security headers."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


# ── API Key Auth ─────────────────────────────────────────────────

# Paths that don't require auth
_PUBLIC_PATHS = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key header matching SECRET_KEY on all non-public endpoints."""

    def __init__(self, app, secret_key: str) -> None:
        super().__init__(app)
        self._secret = secret_key

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path in _PUBLIC_PATHS or request.method == "OPTIONS":
            return await call_next(request)
        api_key = request.headers.get("X-API-Key", "")
        if api_key != self._secret:
            return JSONResponse(status_code=401, content={"detail": "X-API-Key required"})
        return await call_next(request)


# ── Rate Limiting ────────────────────────────────────────────────


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple sliding window rate limiter per client IP."""

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60) -> None:
        super().__init__(app)
        self._max = max_requests
        self._window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        cutoff = now - self._window
        reqs = [t for t in self._requests[client_ip] if t > cutoff]
        if len(reqs) >= self._max:
            return JSONResponse(status_code=429, content={"detail": "Too many requests"})
        reqs.append(now)
        self._requests[client_ip] = reqs
        return await call_next(request)


# ── Security Headers ─────────────────────────────────────────────


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


# ── Helper to add all middleware ─────────────────────────────────


def add_security_middleware(app: FastAPI, secret_key: str) -> None:
    """Add auth + rate limit + security headers to a FastAPI app."""
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, max_requests=60, window_seconds=60)
    app.add_middleware(ApiKeyAuthMiddleware, secret_key=secret_key)
