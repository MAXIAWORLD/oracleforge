"""TDD — Phase 4: Auth middleware (401, 429, security headers).

Ces tests sont ROUGES si le middleware ne couvre pas ces cas.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.config import Settings
from core.middleware import (
    ApiKeyAuthMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def settings() -> Settings:
    return Settings(
        secret_key="test-secret-key-32-chars-ok!!",
        database_url="sqlite+aiosqlite:///:memory:",
        debug=True,
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    """FastAPI minimal avec les trois middlewares de sécurité."""
    _app = FastAPI()
    _app.add_middleware(SecurityHeadersMiddleware)
    _app.add_middleware(RateLimitMiddleware, max_requests=5, window_seconds=60)
    _app.add_middleware(ApiKeyAuthMiddleware, secret_key=settings.secret_key)

    @_app.get("/test")
    async def endpoint():
        return {"ok": True}

    @_app.get("/health")
    async def health():
        return {"status": "ok"}

    return _app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def valid_headers(settings: Settings) -> dict[str, str]:
    return {"X-API-Key": settings.secret_key}


# ── Tests : authentification ──────────────────────────────────────


def test_request_without_api_key_returns_401(client):
    """Requête sans X-API-Key → 401 Unauthorized."""
    resp = client.get("/test")
    assert resp.status_code == 401


def test_request_with_wrong_api_key_returns_401(client):
    """X-API-Key incorrecte → 401 Unauthorized."""
    resp = client.get("/test", headers={"X-API-Key": "definitely-wrong"})
    assert resp.status_code == 401


def test_request_with_valid_api_key_returns_200(client, valid_headers):
    """X-API-Key correcte → 200 OK."""
    resp = client.get("/test", headers=valid_headers)
    assert resp.status_code == 200


def test_401_response_has_json_detail(client):
    """La réponse 401 contient un champ detail."""
    resp = client.get("/test")
    assert resp.headers.get("content-type", "").startswith("application/json")
    body = resp.json()
    assert "detail" in body


def test_health_endpoint_does_not_require_auth(settings):
    """Le endpoint /health est exempt d'auth (PUBLIC_PATHS dans ApiKeyAuthMiddleware)."""
    _app = FastAPI()
    _app.add_middleware(ApiKeyAuthMiddleware, secret_key=settings.secret_key)

    @_app.get("/health")
    async def health():
        return {"status": "ok"}

    c = TestClient(_app, raise_server_exceptions=False)
    resp = c.get("/health")
    assert resp.status_code == 200


# ── Tests : rate limiting ────────────────────────────────────────


def test_rate_limit_returns_429_after_threshold(client, valid_headers):
    """La 6ème requête dans la même fenêtre → 429 Too Many Requests."""
    # max_requests=5 dans le fixture app
    for i in range(5):
        resp = client.get("/health", headers=valid_headers)
        assert resp.status_code == 200, f"Request {i + 1} should pass"

    resp = client.get("/health", headers=valid_headers)
    assert resp.status_code == 429


def test_rate_limit_applies_per_ip(settings):
    """Chaque IP a son propre compteur (deux IPs différentes ne se bloquent pas)."""
    _app = FastAPI()
    _app.add_middleware(RateLimitMiddleware, max_requests=2, window_seconds=60)
    _app.add_middleware(ApiKeyAuthMiddleware, secret_key=settings.secret_key)

    @_app.get("/test")
    async def endpoint():
        return {"ok": True}

    c = TestClient(_app, raise_server_exceptions=False)
    headers = {"X-API-Key": settings.secret_key}

    # 2 requêtes depuis 127.0.0.1 → OK
    for _ in range(2):
        resp = c.get("/test", headers=headers)
        assert resp.status_code == 200

    # 3ème depuis la même IP → 429
    resp = c.get("/test", headers=headers)
    assert resp.status_code == 429


# ── Tests : security headers ──────────────────────────────────────


def test_security_headers_present_on_response(client, valid_headers):
    """Les headers de sécurité sont présents sur toutes les réponses."""
    resp = client.get("/test", headers=valid_headers)
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"


def test_cors_headers_absent_without_origin(client, valid_headers):
    """Sans header Origin, pas de CORS leak."""
    resp = client.get("/test", headers=valid_headers)
    assert "Access-Control-Allow-Origin" not in resp.headers
