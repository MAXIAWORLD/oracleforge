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

import pytest
from fastapi.testclient import TestClient

# Shared `session_app`, `client`, `api_key` fixtures live in conftest.py.


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
    # Phase 4: with no X-API-Key and no X-Payment, the x402 middleware emits
    # a 402 Payment Required challenge (payment discovery) instead of a raw
    # 401. Agents can use the challenge to pay on Base mainnet; humans
    # using the free tier must provide X-API-Key.
    r = client.get("/api/price/BTC")
    assert r.status_code == 402
    body = r.json()
    assert body["x402Version"] == 2
    assert isinstance(body["accepts"], list)
    # The accepts list is only populated when X402_TREASURY_ADDRESS_BASE is
    # configured. In test mode (dev, no env var), it is empty but the
    # challenge shape is still valid.
    assert r.headers.get("X-Payment-Required") == "true"


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
    # Phase 4: same discovery behavior as /api/price/{symbol}.
    r = client.post("/api/prices/batch", json={"symbols": ["BTC"]})
    assert r.status_code == 402
    body = r.json()
    assert body["x402Version"] == 2
    assert isinstance(body["accepts"], list)


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


def test_batch_rejected_does_not_drain_quota(client: TestClient, api_key: str) -> None:
    """A batch that exceeds the daily quota must NOT consume remaining requests.

    Regression test for the bug where _enforce_rate_limit incremented the
    counter N times before checking if the last increment was allowed, causing
    rejected batch requests to drain the user's remaining quota.

    Setup: exhaust 99 of 100 daily requests, then attempt a batch of 10.
    The batch must be rejected (99+10 > 100) AND the user must still have
    1 request remaining (not 0).
    """
    from core.db import get_db  # noqa: PLC0415
    from core.rate_limit import DAILY_LIMIT  # noqa: PLC0415

    # Manually set counter to DAILY_LIMIT - 1 (99 used, 1 remaining)
    from core.auth import hash_key  # noqa: PLC0415
    from core.rate_limit import DAILY_WINDOW_S, _compute_window_start  # noqa: PLC0415
    import time  # noqa: PLC0415

    db = get_db()
    key_hash = hash_key(api_key)
    window_start = _compute_window_start(int(time.time()), DAILY_WINDOW_S)
    db.execute(
        "INSERT OR REPLACE INTO rate_limit (key_hash, window_start, count) VALUES (?, ?, ?)",
        (key_hash, window_start, DAILY_LIMIT - 1),
    )

    # Batch of 10 symbols — would need 10 slots, only 1 remains → must reject
    symbols = [f"SY{i:02d}" for i in range(10)]
    r = client.post(
        "/api/prices/batch",
        headers={"X-API-Key": api_key},
        json={"symbols": symbols},
    )
    assert r.status_code == 429, "batch should be rejected when quota insufficient"

    # Verify the counter was NOT incremented by the rejected batch
    row = db.execute(
        "SELECT count FROM rate_limit WHERE key_hash = ? AND window_start = ?",
        (key_hash, window_start),
    ).fetchone()
    assert row is not None
    assert row[0] == DAILY_LIMIT - 1, (
        f"counter should remain at {DAILY_LIMIT - 1} after rejected batch, got {row[0]}"
    )

    # The 1 remaining request must still work
    r2 = client.post(
        "/api/prices/batch",
        headers={"X-API-Key": api_key},
        json={"symbols": ["BTC"]},
    )
    assert r2.status_code in (200, 404), (
        f"single-slot batch should succeed (1 remaining), got {r2.status_code}"
    )


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


# ── /api/symbols ─────────────────────────────────────────────────────────────


def test_symbols_requires_auth(client: TestClient) -> None:
    r = client.get("/api/symbols")
    assert r.status_code == 401


def test_symbols_returns_grouped_list(client: TestClient, api_key: str) -> None:
    r = client.get("/api/symbols", headers={"X-API-Key": api_key})
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["total_symbols"] > 0
    assert "BTC" in body["data"]["all_symbols"]
    assert "pyth_crypto" in body["data"]["by_source"]
    assert "pyth_equity" in body["data"]["by_source"]
    assert "chainlink_base" in body["data"]["by_source"]
    assert "price_oracle" in body["data"]["by_source"]
    assert "disclaimer" in body


# ── /api/chainlink/{symbol} ──────────────────────────────────────────────────


def test_chainlink_requires_auth(client: TestClient) -> None:
    # /api/chainlink/* is not in X402_PRICE_MAP, so the x402 middleware
    # passes the request through and the require_access dependency
    # raises 401 directly (no 402 challenge unlike /api/price/*).
    r = client.get("/api/chainlink/BTC")
    assert r.status_code == 401


def test_chainlink_rejects_invalid_symbol(client: TestClient, api_key: str) -> None:
    r = client.get("/api/chainlink/BTC!!", headers={"X-API-Key": api_key})
    assert r.status_code == 400
    assert r.json()["error"] == "invalid symbol format"


def test_chainlink_rejects_unsupported_symbol(
    client: TestClient, api_key: str
) -> None:
    r = client.get(
        "/api/chainlink/DOGE99",
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 404
    body = r.json()
    assert body["error"] == "symbol has no Chainlink feed on requested chain"
    assert body["symbol"] == "DOGE99"
    assert body["chain"] == "base"
    assert isinstance(body["supported"], list)
    assert "BTC" in body["supported"]


def test_chainlink_returns_price(client: TestClient, api_key: str) -> None:
    r = client.get("/api/chainlink/BTC", headers={"X-API-Key": api_key})
    # 200 when the Base RPC answers, 502 when every RPC endpoint is down
    # (possible in a strict offline CI environment).
    assert r.status_code in (200, 502)
    if r.status_code == 200:
        body = r.json()
        assert body["data"]["source"] == "chainlink_base"
        assert body["data"]["price"] > 0
        assert "contract" in body["data"]
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


def test_422_validation_error_has_disclaimer(client: TestClient, api_key: str) -> None:
    """Pydantic validation errors (422) must include the disclaimer field.

    FastAPI's default 422 handler bypasses our wrap_error() helper, exposing
    raw {"detail": [...]} responses without the disclaimer. A custom handler
    must be registered to inject it.
    """
    r = client.post(
        "/api/prices/batch",
        headers={"X-API-Key": api_key},
        json={"symbols": []},
    )
    assert r.status_code == 422
    body = r.json()
    assert "disclaimer" in body, (
        "422 validation errors must include 'disclaimer' field"
    )


def test_safe_error_never_leaks(client: TestClient) -> None:
    from core.errors import safe_error

    try:
        raise FileNotFoundError("/home/maxia/.env with MY_SECRET=hunter2")
    except FileNotFoundError as e:
        msg = safe_error("op failed", e, None)
    assert "hunter2" not in msg
    assert "/home/maxia" not in msg
    assert "FileNotFoundError" in msg
