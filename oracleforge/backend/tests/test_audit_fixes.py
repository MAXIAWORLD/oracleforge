"""Tests for audit fixes — H4 (deep health), H6 (request ID), M5 (ankr removal)."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient


# ── H4: Deep health check ───────────────────────────────────────────────────


def test_health_returns_db_status(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["db"] == "ok"
    assert "circuit_breakers" in data
    assert isinstance(data["open_breakers"], list)


def test_health_status_ok_when_healthy(client: TestClient) -> None:
    r = client.get("/health")
    data = r.json()["data"]
    assert data["status"] == "ok"
    assert data["open_breakers"] == []


def test_health_reports_uptime(client: TestClient) -> None:
    r = client.get("/health")
    data = r.json()["data"]
    assert isinstance(data["uptime_s"], float)
    assert data["uptime_s"] >= 0


def test_health_includes_disclaimer(client: TestClient) -> None:
    r = client.get("/health")
    assert "disclaimer" in r.json()


def test_health_degraded_when_db_fails(client: TestClient, monkeypatch) -> None:
    import api.routes_health as rh

    monkeypatch.setattr(rh, "_check_db", lambda: False)
    r = client.get("/health")
    data = r.json()["data"]
    assert data["status"] == "degraded"
    assert data["db"] == "error"


def test_health_degraded_when_breaker_open(client: TestClient, monkeypatch) -> None:
    import api.routes_health as rh

    monkeypatch.setattr(
        rh, "_collect_breaker_states", lambda: {"fake_source": "open"}
    )
    r = client.get("/health")
    data = r.json()["data"]
    assert data["status"] == "degraded"
    assert "fake_source" in data["open_breakers"]


# ── H6: Request ID middleware ────────────────────────────────────────────────


def test_request_id_generated_when_absent(client: TestClient) -> None:
    r = client.get("/health")
    rid = r.headers.get("x-request-id")
    assert rid is not None
    assert len(rid) == 32
    assert re.match(r"^[a-f0-9]{32}$", rid)


def test_request_id_echoed_when_provided(client: TestClient) -> None:
    custom_id = "my-custom-request-id-42"
    r = client.get("/health", headers={"X-Request-ID": custom_id})
    assert r.headers["x-request-id"] == custom_id


def test_request_id_rejected_when_too_long(client: TestClient) -> None:
    long_id = "x" * 100
    r = client.get("/health", headers={"X-Request-ID": long_id})
    rid = r.headers["x-request-id"]
    assert rid != long_id
    assert len(rid) == 32


def test_request_id_on_authenticated_route(client: TestClient, api_key: str) -> None:
    r = client.get("/api/sources", headers={"X-API-Key": api_key})
    assert r.status_code == 200
    assert "x-request-id" in r.headers


# ── M5: ankr Solana RPC removed ─────────────────────────────────────────────


def test_ankr_not_in_solana_rpcs() -> None:
    from core.config import SOLANA_RPC_URLS

    for url in SOLANA_RPC_URLS:
        assert "ankr" not in url, f"ankr RPC should be removed: {url}"
