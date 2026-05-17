"""Tests for audit improvement fixes — middleware pipeline, status endpoint,
Finnhub rate limiter, Hermes retry."""
from __future__ import annotations

import re
import time

import pytest
from fastapi.testclient import TestClient


# ── Middleware pipeline integration ─────────────────────────────────────────


def test_middleware_pipeline_request_id_plus_security_headers(client: TestClient) -> None:
    """Verify that RequestID + SecurityHeaders both appear on the same response."""
    r = client.get("/health")
    assert r.status_code == 200
    assert re.match(r"^[a-f0-9]{32}$", r.headers["x-request-id"])
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "strict-origin" in r.headers.get("referrer-policy", "")


def test_middleware_pipeline_on_authenticated_route(
    client: TestClient, api_key: str
) -> None:
    """Full pipeline on an auth-required route: RequestID + security + JSON body."""
    r = client.get("/api/sources", headers={"X-API-Key": api_key})
    assert r.status_code == 200
    assert "x-request-id" in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"
    body = r.json()
    assert "data" in body
    assert "disclaimer" in body


def test_middleware_pipeline_on_error_route(client: TestClient) -> None:
    """Security headers + request ID must appear even on 401 errors."""
    r = client.get("/api/sources")
    assert r.status_code in (401, 402)
    assert "x-request-id" in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"


def test_middleware_custom_request_id_propagates_through_pipeline(
    client: TestClient, api_key: str
) -> None:
    """A client-provided X-Request-ID must survive the full middleware stack."""
    custom_id = "test-pipeline-id-42"
    r = client.get(
        "/api/sources",
        headers={"X-API-Key": api_key, "X-Request-ID": custom_id},
    )
    assert r.status_code == 200
    assert r.headers["x-request-id"] == custom_id


# ── Public status endpoint ──────────────────────────────────────────────────


def test_status_returns_ok(client: TestClient) -> None:
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("ok", "degraded")
    assert isinstance(data["sources"], dict)
    assert isinstance(data["open_breakers"], list)
    assert isinstance(data["uptime_s"], float)
    assert data["db"] in ("ok", "error")


def test_status_no_auth_required(client: TestClient) -> None:
    """The /api/status endpoint must not require an API key."""
    r = client.get("/api/status")
    assert r.status_code == 200


def test_status_no_disclaimer(client: TestClient) -> None:
    """Status is operational metadata, not financial data — no disclaimer."""
    r = client.get("/api/status")
    assert "disclaimer" not in r.json()


def test_status_degraded_when_db_fails(client: TestClient, monkeypatch) -> None:
    import api.routes_health as rh

    monkeypatch.setattr(rh, "_check_db", lambda: False)
    r = client.get("/api/status")
    data = r.json()
    assert data["status"] == "degraded"
    assert data["db"] == "error"


# ── Finnhub rate limiter ───────────────────────────────────────────────────


def test_finnhub_rate_limiter_rejects_over_55(monkeypatch) -> None:
    import services.oracle.price_cascade as pc

    monkeypatch.setattr(pc, "FINNHUB_API_KEY", "fake-key-for-test")
    original = pc._finnhub_call_timestamps.copy()
    try:
        pc._finnhub_call_timestamps.clear()
        now = time.time()
        pc._finnhub_call_timestamps.extend(now - i * 0.5 for i in range(pc._FINNHUB_RATE_LIMIT))

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            pc.get_stock_price_finnhub("AAPL")
        )
        assert "error" in result
        assert "rate limit" in result["error"].lower()
    finally:
        pc._finnhub_call_timestamps.clear()
        pc._finnhub_call_timestamps.extend(original)


def test_finnhub_rate_limiter_allows_after_window(monkeypatch) -> None:
    import services.oracle.price_cascade as pc

    monkeypatch.setattr(pc, "FINNHUB_API_KEY", "fake-key-for-test")
    original = pc._finnhub_call_timestamps.copy()
    try:
        pc._finnhub_call_timestamps.clear()
        pc._finnhub_call_timestamps.extend(time.time() - 120 for _ in range(100))

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            pc.get_stock_price_finnhub("AAPL")
        )
        assert result.get("error") != "Finnhub rate limit (55/min server-side)"
    finally:
        pc._finnhub_call_timestamps.clear()
        pc._finnhub_call_timestamps.extend(original)
