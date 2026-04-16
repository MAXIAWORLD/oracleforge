"""Unit tests for `MaxiaOracleClient` using `httpx.MockTransport`.

No backend process needed. Every request is intercepted and answered
from a local dict of fixtures, which means these tests run in under a
second and do not depend on the network.
"""
from __future__ import annotations

import json
from typing import Any, Callable

import httpx
import pytest

from maxia_oracle import (
    MaxiaOracleAuthError,
    MaxiaOracleClient,
    MaxiaOracleRateLimitError,
    MaxiaOracleTransportError,
    MaxiaOracleUpstreamError,
    MaxiaOracleValidationError,
)

DISCLAIMER = "Data feed only. Not investment advice. No custody. No KYC."


def _ok(body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json=body)


def _created(body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(201, json=body)


def _err(status: int, body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(status, json=body)


def _mock(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def _client_with(handler: Callable[[httpx.Request], httpx.Response], *, api_key: str | None = "mxo_fake_test_key") -> MaxiaOracleClient:
    return MaxiaOracleClient(
        api_key=api_key,
        base_url="http://test.invalid",
        transport=_mock(handler),
    )


# ── register / health (no auth) ─────────────────────────────────────────────


def test_register_returns_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/register"
        assert "X-API-Key" not in request.headers
        return _created(
            {"data": {"api_key": "mxo_new_test_key", "tier": "free", "daily_limit": 100}, "disclaimer": DISCLAIMER}
        )

    with _client_with(handler, api_key=None) as c:
        result = c.register()
    assert result["data"]["api_key"] == "mxo_new_test_key"
    assert result["data"]["daily_limit"] == 100


def test_health_does_not_require_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        assert "X-API-Key" not in request.headers
        return _ok({"data": {"status": "ok", "env": "dev"}, "disclaimer": DISCLAIMER})

    with _client_with(handler, api_key=None) as c:
        result = c.health()
    assert result["data"]["status"] == "ok"


# ── price ───────────────────────────────────────────────────────────────────


def test_price_sends_api_key_and_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/price/BTC"
        assert request.headers["X-API-Key"] == "mxo_fake_test_key"
        return _ok(
            {
                "data": {
                    "symbol": "BTC",
                    "price": 74000.5,
                    "sources": [{"name": "pyth", "price": 74000.5}],
                    "source_count": 1,
                    "divergence_pct": 0.0,
                },
                "disclaimer": DISCLAIMER,
            }
        )

    with _client_with(handler) as c:
        result = c.price("btc")  # lowercase normalized
    assert result["data"]["symbol"] == "BTC"
    assert result["data"]["price"] == 74000.5


def test_price_rejects_bad_symbol_locally() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("request should never leave the client")

    with _client_with(handler) as c:
        with pytest.raises(MaxiaOracleValidationError):
            c.price("not-a-symbol")


def test_price_upstream_error_raises_typed_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _err(
            404,
            {"error": "no live price available", "symbol": "FAKE"},
        )

    with _client_with(handler) as c:
        with pytest.raises(MaxiaOracleUpstreamError):
            c.price("FAKE")


def test_auth_error_raises_typed_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _err(401, {"error": "invalid or inactive API key"})

    with _client_with(handler) as c:
        with pytest.raises(MaxiaOracleAuthError):
            c.price("BTC")


def test_rate_limit_error_exposes_retry_after() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _err(
            429,
            {
                "error": "rate limit exceeded",
                "limit": 100,
                "retry_after_seconds": 3600,
            },
        )

    with _client_with(handler) as c:
        with pytest.raises(MaxiaOracleRateLimitError) as exc_info:
            c.price("BTC")
    assert exc_info.value.retry_after_seconds == 3600
    assert exc_info.value.limit == 100


def test_missing_api_key_raises_auth_error_locally() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("request should never leave the client")

    with _client_with(handler, api_key=None) as c:
        with pytest.raises(MaxiaOracleAuthError):
            c.price("BTC")


# ── prices_batch ────────────────────────────────────────────────────────────


def test_prices_batch_validates_inputs_locally() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("request should never leave the client")

    with _client_with(handler) as c:
        with pytest.raises(MaxiaOracleValidationError):
            c.prices_batch([])
        with pytest.raises(MaxiaOracleValidationError):
            c.prices_batch("BTC")  # type: ignore[arg-type]
        with pytest.raises(MaxiaOracleValidationError):
            c.prices_batch([f"SYM{i}" for i in range(51)])


def test_prices_batch_sends_cleaned_symbols() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return _ok({"data": {"requested": 2, "count": 2, "prices": {"BTC": 1, "ETH": 2}}, "disclaimer": DISCLAIMER})

    with _client_with(handler) as c:
        c.prices_batch(["btc", "eth"])
    assert seen["body"]["symbols"] == ["BTC", "ETH"]


# ── sources / cache_stats / list_symbols / chainlink / confidence ──────────


def test_sources_returns_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/sources"
        return _ok({"data": {"sources": [{"name": "pyth_hermes"}]}, "disclaimer": DISCLAIMER})

    with _client_with(handler) as c:
        result = c.sources()
    assert result["data"]["sources"][0]["name"] == "pyth_hermes"


def test_cache_stats_returns_metrics() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/cache/stats"
        return _ok({"data": {"hit_rate": 0.8}, "disclaimer": DISCLAIMER})

    with _client_with(handler) as c:
        result = c.cache_stats()
    assert result["data"]["hit_rate"] == 0.8


def test_list_symbols_returns_grouped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/symbols"
        return _ok(
            {
                "data": {
                    "total_symbols": 3,
                    "all_symbols": ["BTC", "ETH", "SOL"],
                    "by_source": {"pyth_crypto": ["BTC", "ETH", "SOL"]},
                },
                "disclaimer": DISCLAIMER,
            }
        )

    with _client_with(handler) as c:
        result = c.list_symbols()
    assert result["data"]["total_symbols"] == 3
    assert "BTC" in result["data"]["all_symbols"]


def test_chainlink_onchain_calls_right_path() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["chain"] = request.url.params.get("chain", "")
        return _ok(
            {"data": {"source": "chainlink_base", "price": 74000.0, "contract": "0xabc", "chain": "base"}, "disclaimer": DISCLAIMER}
        )

    with _client_with(handler) as c:
        result = c.chainlink_onchain("BTC")
    assert captured["path"] == "/api/chainlink/BTC"
    assert captured["chain"] == "base"
    assert result["data"]["source"] == "chainlink_base"


def test_chainlink_onchain_propagates_chain_ethereum() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["chain"] = request.url.params.get("chain", "")
        return _ok(
            {
                "data": {
                    "source": "chainlink_ethereum",
                    "price": 73900.0,
                    "contract": "0xeth",
                    "chain": "ethereum",
                },
                "disclaimer": DISCLAIMER,
            }
        )

    with _client_with(handler) as c:
        result = c.chainlink_onchain("BTC", chain="ethereum")
    assert captured["path"] == "/api/chainlink/BTC"
    assert captured["chain"] == "ethereum"
    assert result["data"]["chain"] == "ethereum"


def test_chainlink_onchain_rejects_invalid_chain() -> None:
    import pytest

    from maxia_oracle.exceptions import MaxiaOracleValidationError

    with _client_with(lambda _r: _ok({"data": {}, "disclaimer": DISCLAIMER})) as c:
        with pytest.raises(MaxiaOracleValidationError):
            c.chainlink_onchain("BTC", chain="solana")


def test_confidence_extracts_divergence_from_price_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/price/ETH"
        return _ok(
            {
                "data": {
                    "symbol": "ETH",
                    "price": 3500.0,
                    "sources": [{"name": "pyth", "price": 3500.0}],
                    "source_count": 2,
                    "divergence_pct": 0.12,
                },
                "disclaimer": DISCLAIMER,
            }
        )

    with _client_with(handler) as c:
        result = c.confidence("eth")
    assert result["data"]["symbol"] == "ETH"
    assert result["data"]["source_count"] == 2
    assert result["data"]["divergence_pct"] == 0.12
    # The per-source breakdown is NOT leaked by confidence()
    assert "sources" not in result["data"]
    assert "price" not in result["data"]


# ── transport errors ────────────────────────────────────────────────────────


def test_transport_error_on_connection_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with _client_with(handler) as c:
        with pytest.raises(MaxiaOracleTransportError):
            c.health()


def test_transport_error_on_non_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    with _client_with(handler) as c:
        with pytest.raises(MaxiaOracleTransportError):
            c.health()
