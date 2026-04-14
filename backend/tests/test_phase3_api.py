"""Phase 3 API tests — FastAPI TestClient against an in-process SQLite DB.

Coverage targets from the Phase 3 architecture:
    - /health (unauthenticated)
    - /api/register (IP throttled)
    - /api/sources (auth + rate limit)
    - /api/price/{symbol} (auth + rate limit + validation)
    - /api/prices/batch (auth + rate limit + cost N)
    - Security headers (H9)
    - Disclaimer wrapper on every response
    - safe_error() never leaks internal detail

Fixture strategy: the FastAPI app + SQLite DB are built once at session
scope, and each test truncates the three mutable tables (`api_keys`,
`rate_limit`, `register_limit`) before running. This avoids the fragile
module-reload dance and keeps every test fully isolated.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def session_app(tmp_path_factory: pytest.TempPathFactory):
    """Session-scoped: import main.py exactly once with a fresh DB path."""
    db_dir: Path = tmp_path_factory.mktemp("maxia_oracle_db")
    os.environ["DB_PATH"] = str(db_dir / "test.sqlite")
    import main  # noqa: PLC0415 — intentional late import after env setup
    from core.db import init_db  # noqa: PLC0415

    init_db()
    return main.app


@pytest.fixture
def client(session_app) -> Iterator[TestClient]:
    """Function-scoped: truncate mutable tables, then hand a TestClient over."""
    from core.db import get_db  # noqa: PLC0415

    db = get_db()
    db.execute("DELETE FROM api_keys")
    db.execute("DELETE FROM rate_limit")
    db.execute("DELETE FROM register_limit")

    with TestClient(session_app) as c:
        yield c


@pytest.fixture
def api_key(client: TestClient) -> str:
    """Register a fresh API key and return the raw value."""
    response = client.post("/api/register")
    assert response.status_code == 201, response.text
    return response.json()["data"]["api_key"]


# ── /health ──────────────────────────────────────────────────────────────────


def test_health_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["status"] == "ok"
    assert body["data"]["env"] == "dev"
    assert "disclaimer" in body


def test_security_headers_present(client: TestClient) -> None:
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert r.headers["x-api-version"]
    # HSTS must NOT be set over plain HTTP (TestClient uses http)
    assert "strict-transport-security" not in {k.lower() for k in r.headers}


# ── /api/register ────────────────────────────────────────────────────────────


def test_register_creates_key(client: TestClient) -> None:
    r = client.post("/api/register")
    assert r.status_code == 201
    body = r.json()
    assert body["data"]["api_key"].startswith("mxo_")
    assert body["data"]["tier"] == "free"
    assert body["data"]["daily_limit"] == 100
    assert "disclaimer" in body


def test_register_rate_limit_per_ip(client: TestClient) -> None:
    # First call OK, second from same IP is throttled (REGISTER_LIMIT=1/60s)
    first = client.post("/api/register")
    assert first.status_code == 201
    second = client.post("/api/register")
    assert second.status_code == 429
    assert "retry-after" in {k.lower() for k in second.headers}
    body = second.json()
    assert body["error"] == "registration throttled"
    assert body["retry_after_seconds"] > 0
    assert "disclaimer" in body


# ── /api/price/{symbol} ──────────────────────────────────────────────────────


def test_price_requires_auth(client: TestClient) -> None:
    r = client.get("/api/price/BTC")
    assert r.status_code == 401


def test_price_rejects_invalid_key(client: TestClient) -> None:
    r = client.get("/api/price/BTC", headers={"X-API-Key": "mxo_obviously_fake"})
    assert r.status_code == 401


def test_price_rejects_invalid_symbol(client: TestClient, api_key: str) -> None:
    r = client.get("/api/price/../etc/passwd", headers={"X-API-Key": api_key})
    assert r.status_code == 404  # FastAPI rejects path with slashes before our handler
    r2 = client.get("/api/price/BTC!!", headers={"X-API-Key": api_key})
    assert r2.status_code == 400
    body = r2.json()
    assert body["error"] == "invalid symbol format"


def test_price_returns_multi_source(client: TestClient, api_key: str) -> None:
    r = client.get("/api/price/BTC", headers={"X-API-Key": api_key})
    # 200 if at least one upstream source returned data; 404 if every source
    # was dead (rare, but possible in strict offline CI environments)
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        body = r.json()
        assert body["data"]["symbol"] == "BTC"
        assert body["data"]["price"] > 0
        assert body["data"]["source_count"] >= 1
        assert "divergence_pct" in body["data"]
        assert "disclaimer" in body
        # Rate-limit headers are set on 429 responses (exercised in
        # test_daily_rate_limit_exhausts_to_429). Success responses skip
        # them to avoid the overhead on the hot path.


# ── /api/prices/batch ────────────────────────────────────────────────────────


def test_batch_requires_auth(client: TestClient) -> None:
    r = client.post("/api/prices/batch", json={"symbols": ["BTC"]})
    assert r.status_code == 401


def test_batch_validates_symbols(client: TestClient, api_key: str) -> None:
    r = client.post(
        "/api/prices/batch",
        headers={"X-API-Key": api_key},
        json={"symbols": ["BTC", "ETH", "INVALID@"]},
    )
    assert r.status_code == 422  # Pydantic validation error


def test_batch_returns_prices(client: TestClient, api_key: str) -> None:
    r = client.post(
        "/api/prices/batch",
        headers={"X-API-Key": api_key},
        json={"symbols": ["BTC", "ETH", "SOL"]},
    )
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        body = r.json()
        assert body["data"]["requested"] == 3
        assert "prices" in body["data"]
        assert "disclaimer" in body


def test_batch_caps_at_50(client: TestClient, api_key: str) -> None:
    symbols = [f"SYM{i}" for i in range(51)]
    r = client.post(
        "/api/prices/batch",
        headers={"X-API-Key": api_key},
        json={"symbols": symbols},
    )
    assert r.status_code == 422


# ── /api/sources ─────────────────────────────────────────────────────────────


def test_sources_requires_auth(client: TestClient) -> None:
    r = client.get("/api/sources")
    assert r.status_code == 401


def test_sources_listing(client: TestClient, api_key: str) -> None:
    r = client.get("/api/sources", headers={"X-API-Key": api_key})
    assert r.status_code == 200
    body = r.json()
    names = [s["name"] for s in body["data"]["sources"]]
    assert "pyth_hermes" in names
    assert "chainlink_base" in names
    assert "helius_das" in names
    assert "coinpaprika" in names
    assert "coingecko" in names
    assert "yahoo_finance" in names
    assert "disclaimer" in body


# ── Rate-limit burn-down ────────────────────────────────────────────────────


def test_daily_rate_limit_exhausts_to_429(client: TestClient, api_key: str) -> None:
    """Exhaust the 100-req daily quota and confirm the 101st gets 429."""
    # Use /api/sources (doesn't hit upstreams) to burn tokens cheaply
    for i in range(100):
        r = client.get("/api/sources", headers={"X-API-Key": api_key})
        assert r.status_code == 200, f"request #{i + 1} unexpectedly denied: {r.text}"
    r = client.get("/api/sources", headers={"X-API-Key": api_key})
    assert r.status_code == 429
    body = r.json()
    assert body["error"] == "rate limit exceeded"
    assert body["limit"] == 100
    assert body["retry_after_seconds"] > 0
    assert "disclaimer" in body
    assert r.headers["retry-after"]


# ── safe_error() defense-in-depth ────────────────────────────────────────────


def test_safe_error_never_leaks(client: TestClient) -> None:
    from core.errors import safe_error

    try:
        raise FileNotFoundError("/home/maxia/.env with MY_SECRET=hunter2")
    except FileNotFoundError as e:
        msg = safe_error("op failed", e, None)
    assert "hunter2" not in msg
    assert "/home/maxia" not in msg
    assert "FileNotFoundError" in msg
