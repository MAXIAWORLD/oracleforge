"""V1.3 — RedStone tests.

Covers:
    1. `services/oracle/redstone_oracle.py` happy path, cache hit, 404
       silent drop, circuit breaker, timeout.
    2. RedStone wiring in `multi_source.collect_sources()` — a fresh
       symbol picks up the 4th source.
    3. `/api/redstone/{symbol}` HTTP route — success, 404, invalid symbol.
    4. MCP `get_redstone_price` tool — validation + dispatch.

A Pyth native Solana on-chain reader was scoped for V1.3 but removed
before ship (2026-04-16) after live audit — the Pyth V2 `PriceAccount`
feeds on Solana mainnet-beta have been decommissioned (status=0, slot
frozen ~23 days). Rescheduled to V1.4 with the `Pyth Solana Receiver`
program's new `PriceUpdateV2` layout.

All tests run offline — monkeypatch the HTTP client so CI never hits
live RedStone endpoints. A separate live harness lives in
`backend/tests/live_v1_3.py`.
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from mcp_server import tools as mcp_tools
from services.oracle import multi_source, redstone_oracle


# ── RedStone module — happy path, cache, errors ────────────────────────────


class _FakeResponse:
    """Minimal stand-in for httpx.Response for the redstone_oracle path."""

    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _FakeClient:
    """Captures the single GET issued by redstone_oracle and returns a canned reply."""

    def __init__(self, response: _FakeResponse | Exception):
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def get(self, url: str, *, params=None, timeout=None, **kwargs):
        self.calls.append({"url": url, "params": dict(params or {})})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture(autouse=True)
def _reset_redstone_state():
    """Reset cache + circuit before every test to isolate them."""
    redstone_oracle._reset_for_tests()
    yield
    redstone_oracle._reset_for_tests()


@pytest.mark.asyncio
async def test_redstone_known_symbol_returns_price(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [
        {"symbol": "BTC", "value": 74123.45, "timestamp": 1_700_000_000_000}
    ]
    fake = _FakeClient(_FakeResponse(200, payload))
    monkeypatch.setattr(redstone_oracle, "get_http_client", lambda: fake)

    result = await redstone_oracle.get_redstone_price("BTC")

    assert result["source"] == "redstone"
    assert result["symbol"] == "BTC"
    assert result["price"] == 74123.45
    assert result["publish_time"] == 1_700_000_000
    assert isinstance(result["age_s"], int)
    assert fake.calls[0]["params"]["symbol"] == "BTC"
    assert fake.calls[0]["params"]["provider"] == redstone_oracle.REDSTONE_PROVIDER


@pytest.mark.asyncio
async def test_redstone_cache_hit_avoids_second_http_call(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [{"symbol": "ETH", "value": 2500.0, "timestamp": 1_700_000_000_000}]
    fake = _FakeClient(_FakeResponse(200, payload))
    monkeypatch.setattr(redstone_oracle, "get_http_client", lambda: fake)

    await redstone_oracle.get_redstone_price("ETH")
    await redstone_oracle.get_redstone_price("ETH")

    assert len(fake.calls) == 1
    assert redstone_oracle.get_metrics()["cache_hits"] == 1


@pytest.mark.asyncio
async def test_redstone_unknown_symbol_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(_FakeResponse(404, {}))
    monkeypatch.setattr(redstone_oracle, "get_http_client", lambda: fake)

    result = await redstone_oracle.get_redstone_price("ZZZZZ")

    assert result["error"] == "symbol not found on redstone"
    # 404 must NOT trigger the circuit breaker.
    assert redstone_oracle.get_metrics()["circuit"]["failures"] == 0


@pytest.mark.asyncio
async def test_redstone_stale_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    old_ts = 1  # unix seconds — decades old
    payload = [{"symbol": "SOL", "value": 150.0, "timestamp": old_ts * 1000}]
    fake = _FakeClient(_FakeResponse(200, payload))
    monkeypatch.setattr(redstone_oracle, "get_http_client", lambda: fake)

    result = await redstone_oracle.get_redstone_price("SOL")

    assert result["stale"] is True
    assert result["age_s"] > redstone_oracle._STALE_AFTER_S


@pytest.mark.asyncio
async def test_redstone_timeout_records_circuit_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(httpx.TimeoutException("slow"))
    monkeypatch.setattr(redstone_oracle, "get_http_client", lambda: fake)

    result = await redstone_oracle.get_redstone_price("BTC")

    assert result["error"] == "redstone timeout"
    assert redstone_oracle.get_metrics()["circuit"]["failures"] == 1


@pytest.mark.asyncio
async def test_redstone_circuit_opens_after_five_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeClient(httpx.TimeoutException("slow"))
    monkeypatch.setattr(redstone_oracle, "get_http_client", lambda: fake)

    for _ in range(redstone_oracle._CB_MAX_FAILURES):
        await redstone_oracle.get_redstone_price("BTC")

    metrics = redstone_oracle.get_metrics()
    assert metrics["circuit"]["state"] == "open"
    assert metrics["circuit_breaks"] == 1

    # The next call fails fast without touching the (dead) network client.
    fake.calls.clear()
    result = await redstone_oracle.get_redstone_price("BTC")
    assert result["error"] == "redstone circuit open"
    assert fake.calls == []


@pytest.mark.asyncio
async def test_redstone_rejects_malformed_symbol() -> None:
    result = await redstone_oracle.get_redstone_price("bad symbol!")
    assert result["error"] == "invalid symbol format"


@pytest.mark.asyncio
async def test_redstone_rejects_non_positive_price(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [{"symbol": "BTC", "value": 0.0, "timestamp": 1_700_000_000_000}]
    fake = _FakeClient(_FakeResponse(200, payload))
    monkeypatch.setattr(redstone_oracle, "get_http_client", lambda: fake)

    result = await redstone_oracle.get_redstone_price("BTC")

    assert result["error"] == "redstone returned non-positive price"


# ── multi_source wiring ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collect_sources_includes_redstone(monkeypatch: pytest.MonkeyPatch) -> None:
    """collect_sources() must surface a 5th entry when RedStone answers."""

    async def fake_redstone(symbol: str) -> dict[str, Any]:
        return {
            "price": 74100.0,
            "age_s": 3,
            "stale": False,
            "source": "redstone",
            "symbol": symbol,
        }

    async def _none_async(*_a, **_kw):
        return {"error": "skip"}

    async def _none_price_oracle(*_a, **_kw):
        return {}

    monkeypatch.setattr(redstone_oracle, "get_redstone_price", fake_redstone)
    monkeypatch.setattr(
        multi_source.pyth_oracle, "get_pyth_price", _none_async
    )
    monkeypatch.setattr(
        multi_source.chainlink_oracle, "get_chainlink_price", _none_async
    )
    monkeypatch.setattr(
        multi_source.price_oracle, "get_prices", _none_price_oracle
    )

    sources = await multi_source.collect_sources("BTC")

    assert any(s["name"] == "redstone" for s in sources), sources


# ── /api/redstone/{symbol} HTTP route ───────────────────────────────────────


def test_route_redstone_returns_price(
    client: TestClient, api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_price(symbol: str) -> dict:
        return {
            "price": 74200.1,
            "publish_time": 1_700_000_000,
            "age_s": 4,
            "stale": False,
            "source": "redstone",
            "symbol": symbol,
            "provider": redstone_oracle.REDSTONE_PROVIDER,
        }

    monkeypatch.setattr(redstone_oracle, "get_redstone_price", fake_price)

    r = client.get("/api/redstone/BTC", headers={"X-API-Key": api_key})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"]["source"] == "redstone"
    assert body["data"]["price"] == 74200.1


def test_route_redstone_404_on_unknown(
    client: TestClient, api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_price(symbol: str) -> dict:
        return {
            "error": "symbol not found on redstone",
            "source": "redstone",
            "symbol": symbol,
        }

    monkeypatch.setattr(redstone_oracle, "get_redstone_price", fake_price)
    r = client.get("/api/redstone/NOPE", headers={"X-API-Key": api_key})
    assert r.status_code == 404


def test_route_redstone_rejects_bad_symbol(
    client: TestClient, api_key: str
) -> None:
    r = client.get("/api/redstone/bad-symbol", headers={"X-API-Key": api_key})
    assert r.status_code == 400


# ── MCP tool get_redstone_price ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mcp_redstone_rejects_bad_symbol() -> None:
    result = await mcp_tools.get_redstone_price("bad symbol!")
    assert result["error"] == "invalid symbol format"


@pytest.mark.asyncio
async def test_mcp_redstone_dispatches(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_price(symbol: str) -> dict:
        captured["symbol"] = symbol
        return {
            "price": 100.0,
            "publish_time": 0,
            "age_s": 0,
            "stale": False,
            "source": "redstone",
            "symbol": symbol,
        }

    monkeypatch.setattr(redstone_oracle, "get_redstone_price", fake_price)
    result = await mcp_tools.get_redstone_price("AAPL")
    assert captured["symbol"] == "AAPL"
    assert "error" not in result
    assert result["data"]["source"] == "redstone"


