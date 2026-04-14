"""MAXIA Oracle — HTTP security headers middleware (Phase 3).

Addresses V12 audit vulnerability H9 ("no security headers"). Injects a
conservative set of defense-in-depth headers on every response. Headers are
chosen for an API that returns JSON (no HTML, no embedded iframes, no
third-party script sources).

Rationale per header:
    X-Content-Type-Options: nosniff
        Stops browsers from MIME-sniffing a JSON response as HTML and
        executing it. Always safe to set.

    X-Frame-Options: DENY
        The API is not rendered in a frame, ever. Blocks clickjacking
        vectors at the browser level in case a subpath ever returns HTML.

    Referrer-Policy: strict-origin-when-cross-origin
        When a browser follows a link from an API response it will not
        leak paths or query strings to a third-party origin.

    Content-Security-Policy: default-src 'none'; frame-ancestors 'none'
        API-only: no scripts, no styles, no media, no frames. If a
        JSON blob ever ends up rendered as HTML by accident, nothing loads.

    Strict-Transport-Security: max-age=31536000; includeSubDomains
        Only set when the upstream proxy indicates the request arrived over
        HTTPS (X-Forwarded-Proto == "https"). Setting HSTS over plain HTTP
        is a footgun because it makes a later HTTPS mistake unrecoverable.

    X-API-Version
        Not a security header, but cheap to set here so clients can pin
        to an API version without parsing the JSON body.

Phase 9 may revisit this list as we receive pen-test reports.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

_BASE_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}

_HSTS_HEADER = ("Strict-Transport-Security", "max-age=31536000; includeSubDomains")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that injects defense-in-depth headers on every response."""

    def __init__(self, app: ASGIApp, api_version: str) -> None:
        super().__init__(app)
        self._api_version = api_version

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        for name, value in _BASE_HEADERS.items():
            response.headers.setdefault(name, value)
        response.headers.setdefault("X-API-Version", self._api_version)

        # Only assert HSTS when the request actually arrived over HTTPS.
        forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
        scheme = request.url.scheme.lower() if request.url else ""
        if forwarded_proto == "https" or scheme == "https":
            response.headers.setdefault(*_HSTS_HEADER)
        return response
