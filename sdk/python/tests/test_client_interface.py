"""TDD — RED phase: SDK must return unwrapped data (no ['data'] nesting).

All methods should return the inner data dict directly so callers write:
    client.price("BTC")["price"]          # NOT ["data"]["price"]
    client.register()["api_key"]          # NOT ["data"]["api_key"]
    client.health()["status"]             # NOT ["data"]["status"]
"""
from __future__ import annotations

import json
from typing import Any, Callable

import httpx
import pytest

from maxia_oracle import MaxiaOracleClient, MaxiaOracleAuthError

DISCLAIMER = "Data feed only. Not investment advice. No custody. No KYC."


def _ok(body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json=body)


def _created(body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(201, json=body)


def _client_with(handler: Callable[[httpx.Request], httpx.Response], *, api_key: str | None = "mxo_fake") -> MaxiaOracleClient:
    return MaxiaOracleClient(
        api_key=api_key,
        base_url="http://test.invalid",
        transport=httpx.MockTransport(handler),
    )


def test_price_returns_data_directly() -> None:
    """price() should return the inner data dict, not the wrapper."""
    def handler(req: httpx.Request) -> httpx.Response:
        return _ok({
            "data": {"symbol": "BTC", "price": 74000.5, "source_count": 7, "divergence_pct": 0.3},
            "disclaimer": DISCLAIMER,
        })
    with _client_with(handler) as c:
        result = c.price("BTC")
    assert result["price"] == 74000.5, f"Expected price at top level, got: {list(result.keys())}"
    assert result["symbol"] == "BTC"
    assert "data" not in result, "Should NOT have nested 'data' key"
    assert "disclaimer" not in result, "disclaimer should not be in result"


def test_register_returns_data_directly() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return _created({
            "data": {"api_key": "mxo_new", "tier": "free", "daily_limit": 100},
            "disclaimer": DISCLAIMER,
        })
    with _client_with(handler, api_key=None) as c:
        result = c.register()
    assert result["api_key"] == "mxo_new", f"Expected api_key at top level, got: {list(result.keys())}"
    assert result["daily_limit"] == 100
    assert "data" not in result


def test_health_returns_data_directly() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return _ok({"data": {"status": "ok", "env": "prod"}, "disclaimer": DISCLAIMER})
    with _client_with(handler, api_key=None) as c:
        result = c.health()
    assert result["status"] == "ok", f"Expected status at top level, got: {list(result.keys())}"
    assert "data" not in result


def test_prices_batch_returns_data_directly() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return _ok({"data": {"count": 2, "prices": {"BTC": 74000, "ETH": 3500}}, "disclaimer": DISCLAIMER})
    with _client_with(handler) as c:
        result = c.prices_batch(["BTC", "ETH"])
    assert result["count"] == 2, f"Expected count at top level, got: {list(result.keys())}"
    assert "data" not in result


def test_sources_returns_data_directly() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return _ok({"data": {"sources": [{"name": "pyth"}]}, "disclaimer": DISCLAIMER})
    with _client_with(handler) as c:
        result = c.sources()
    assert result["sources"][0]["name"] == "pyth"
    assert "data" not in result


def test_list_symbols_returns_data_directly() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return _ok({"data": {"total_symbols": 42, "all_symbols": ["BTC"], "by_source": {}}, "disclaimer": DISCLAIMER})
    with _client_with(handler) as c:
        result = c.list_symbols()
    assert result["total_symbols"] == 42
    assert "data" not in result


def test_cache_stats_returns_data_directly() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return _ok({"data": {"hit_rate": 0.85}, "disclaimer": DISCLAIMER})
    with _client_with(handler) as c:
        result = c.cache_stats()
    assert result["hit_rate"] == 0.85
    assert "data" not in result


def test_chainlink_returns_data_directly() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return _ok({"data": {"source": "chainlink_base", "price": 74000.0}, "disclaimer": DISCLAIMER})
    with _client_with(handler) as c:
        result = c.chainlink_onchain("BTC")
    assert result["price"] == 74000.0
    assert "data" not in result


def test_confidence_returns_flat_dict() -> None:
    """confidence() builds from price() — must also return flat dict."""
    def handler(req: httpx.Request) -> httpx.Response:
        return _ok({"data": {
            "symbol": "ETH", "price": 3500.0, "source_count": 5, "divergence_pct": 0.12,
            "sources": [{"name": "pyth", "price": 3500.0}],
        }, "disclaimer": DISCLAIMER})
    with _client_with(handler) as c:
        result = c.confidence("ETH")
    assert result["symbol"] == "ETH"
    assert result["source_count"] == 5
    assert result["divergence_pct"] == 0.12
    assert "data" not in result
    assert "price" not in result, "confidence() must NOT leak full price"
    assert "sources" not in result, "confidence() must NOT leak sources"
