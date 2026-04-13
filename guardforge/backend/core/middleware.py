"""Shared security middleware: API key auth, rate limiting, security headers."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


# ── Payload size limit ───────────────────────────────────────────


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with Content-Length above a threshold.

    Prevents memory exhaustion from accidental or malicious large uploads.
    The PII scanner has per-endpoint `max_length` validation on specific
    fields, but this middleware adds a global hard ceiling as a defense
    in depth.
    """

    def __init__(self, app, max_bytes: int = 1_000_000) -> None:
        super().__init__(app)
        self._max = max_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in ("POST", "PUT", "PATCH"):
            cl = request.headers.get("Content-Length")
            if cl and cl.isdigit() and int(cl) > self._max:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Request payload too large. Max {self._max} bytes.",
                    },
                )
        return await call_next(request)


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
    """Adds hardened security headers to every response.

    Headers set:
    - X-Content-Type-Options: prevent MIME type sniffing
    - X-Frame-Options: prevent clickjacking via iframe embedding
    - Referrer-Policy: don't leak URLs to external sites
    - Strict-Transport-Security: force HTTPS (only effective under HTTPS)
    - Content-Security-Policy: restrict inline scripts, fonts, etc.
    - Permissions-Policy: disable sensitive browser APIs by default
    - X-Permitted-Cross-Domain-Policies: no Flash / PDF cross-domain
    """

    def __init__(self, app, enable_hsts: bool = True) -> None:
        super().__init__(app)
        self._enable_hsts = enable_hsts

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        if self._enable_hsts:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Restrictive default CSP — overridable per-route via response.headers
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; frame-ancestors 'none'; base-uri 'self'",
        )
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
        )
        return response


# ── Helper to add all middleware ─────────────────────────────────


def add_security_middleware(
    app: FastAPI,
    secret_key: str,
    rate_limit_max_requests: int = 60,
    rate_limit_window_seconds: int = 60,
    max_payload_bytes: int = 1_000_000,
    enable_hsts: bool = True,
) -> None:
    """Add auth + rate limit + size limit + security headers to a FastAPI app.

    Middleware are added in reverse order of execution: the last one added
    runs first. Order matters for short-circuiting: size check before auth
    before rate limit before headers.
    """
    app.add_middleware(SecurityHeadersMiddleware, enable_hsts=enable_hsts)
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=rate_limit_max_requests,
        window_seconds=rate_limit_window_seconds,
    )
    app.add_middleware(ApiKeyAuthMiddleware, secret_key=secret_key)
    app.add_middleware(PayloadSizeLimitMiddleware, max_bytes=max_payload_bytes)
