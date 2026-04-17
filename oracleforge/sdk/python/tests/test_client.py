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


def test_redstone_hits_expected_path() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return _ok(
            {
                "data": {
                    "source": "redstone",
                    "symbol": "BTC",
                    "price": 74200.1,
                    "publish_time": 1_700_000_000,
                    "age_s": 4,
                    "stale": False,
                    "provider": "redstone-primary-prod",
                },
                "disclaimer": DISCLAIMER,
            }
        )

    with _client_with(handler) as c:
        result = c.redstone("BTC")
    assert captured["path"] == "/api/redstone/BTC"
    assert result["data"]["source"] == "redstone"


def test_pyth_solana_hits_expected_path() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return _ok(
            {
                "data": {
                    "source": "pyth_solana",
                    "symbol": "BTC",
                    "price": 75000.0,
                    "conf": 12.3,
                    "confidence_pct": 0.02,
                    "publish_time": 1_776_000_000,
                    "age_s": 5,
                    "stale": False,
                    "price_account": "4cSM2e6rvbGQUFiJbqytoVMi5GgghSMr8LwVrT9VPSPo",
                    "posted_slot": 413_000_000,
                    "exponent": -8,
                    "feed_id": "e62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
                },
                "disclaimer": DISCLAIMER,
            }
        )

    with _client_with(handler) as c:
        result = c.pyth_solana("BTC")
    assert captured["path"] == "/api/pyth/solana/BTC"
    assert result["data"]["source"] == "pyth_solana"
    assert result["data"]["price"] == 75000.0


def test_pyth_solana_404_raises_upstream_error() -> None:
    import pytest

    from maxia_oracle.exceptions import MaxiaOracleUpstreamError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "error": "symbol not supported on Pyth Solana shard 0",
                "symbol": "ZZZZ",
                "supported": ["BTC", "ETH"],
            },
        )

    with _client_with(handler) as c:
        with pytest.raises(MaxiaOracleUpstreamError, match="not supported"):
            c.pyth_solana("ZZZZ")


def test_pyth_solana_rejects_invalid_symbol_client_side() -> None:
    import pytest

    from maxia_oracle.exceptions import MaxiaOracleValidationError

    with _client_with(lambda _r: _ok({"data": {}, "disclaimer": DISCLAIMER})) as c:
        with pytest.raises(MaxiaOracleValidationError):
            c.pyth_solana("bad-sym!")


def test_twap_hits_expected_path_and_propagates_chain_window() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["chain"] = request.url.params.get("chain", "")
        captured["window"] = request.url.params.get("window", "")
        return _ok(
            {
                "data": {
                    "source": "uniswap_v3",
                    "symbol": "ETH",
                    "chain": "ethereum",
                    "price": 2341.0,
                    "avg_tick": 198735,
                    "window_s": 3600,
                    "tick_cumulatives": [1, 2],
                    "pool": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
                    "fee_bps": 5,
                    "token0": "USDC",
                    "token1": "WETH",
                },
                "disclaimer": DISCLAIMER,
            }
        )

    with _client_with(handler) as c:
        result = c.twap("ETH", chain="ethereum", window_s=3600)
    assert captured["path"] == "/api/twap/ETH"
    assert captured["chain"] == "ethereum"
    assert captured["window"] == "3600"
    assert result["data"]["source"] == "uniswap_v3"


def test_twap_rejects_bad_chain_locally() -> None:
    import pytest

    from maxia_oracle.exceptions import MaxiaOracleValidationError

    with _client_with(lambda _r: _ok({"data": {}, "disclaimer": DISCLAIMER})) as c:
        with pytest.raises(MaxiaOracleValidationError):
            c.twap("ETH", chain="solana")


def test_twap_rejects_window_out_of_range_locally() -> None:
    import pytest

    from maxia_oracle.exceptions import MaxiaOracleValidationError

    with _client_with(lambda _r: _ok({"data": {}, "disclaimer": DISCLAIMER})) as c:
        with pytest.raises(MaxiaOracleValidationError):
            c.twap("ETH", chain="ethereum", window_s=5)
        with pytest.raises(MaxiaOracleValidationError):
            c.twap("ETH", chain="ethereum", window_s=10**9)


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


# ── price_context ───────────────────────────────────────────────────────────


def test_price_context_hits_correct_path() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        assert request.headers["X-API-Key"] == "mxo_fake_test_key"
        return _ok(
            {
                "data": {
                    "symbol": "BTC",
                    "price": 74000.0,
                    "confidence_score": 92,
                    "anomaly": False,
                    "anomaly_reasons": [],
                    "sources_agreement": "strong",
                    "source_count": 4,
                    "divergence_pct": 0.05,
                    "freshest_age_s": 2,
                    "twap_5min": 73950.0,
                    "twap_deviation_pct": 0.07,
                    "source_outliers": [],
                    "sources": [],
                },
                "disclaimer": DISCLAIMER,
            }
        )

    with _client_with(handler) as c:
        result = c.price_context("btc")  # lowercase normalised
    assert captured["path"] == "/api/price/BTC/context"
    assert captured["method"] == "GET"
    assert result["data"]["symbol"] == "BTC"
    assert result["data"]["confidence_score"] == 92
    assert result["data"]["anomaly"] is False


def test_price_context_rejects_invalid_symbol_locally() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("request should never leave the client")

    with _client_with(handler) as c:
        with pytest.raises(MaxiaOracleValidationError):
            c.price_context("bad-sym!")


# ── metadata ─────────────────────────────────────────────────────────────────


def test_metadata_hits_correct_path_and_parses_response() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        return _ok(
            {
                "data": {
                    "symbol": "ETH",
                    "market_cap": 420_000_000_000,
                    "volume_24h": 18_000_000_000,
                    "circulating_supply": 120_000_000,
                    "total_supply": 120_000_000,
                    "max_supply": None,
                    "market_cap_rank": 2,
                    "ath": 4878.26,
                    "atl": 0.432979,
                    "price_change_24h_pct": -1.34,
                },
                "disclaimer": DISCLAIMER,
            }
        )

    with _client_with(handler) as c:
        result = c.metadata("eth")  # lowercase normalised
    assert captured["path"] == "/api/metadata/ETH"
    assert captured["method"] == "GET"
    assert result["data"]["symbol"] == "ETH"
    assert result["data"]["market_cap_rank"] == 2


def test_metadata_rejects_invalid_symbol_locally() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("request should never leave the client")

    with _client_with(handler) as c:
        with pytest.raises(MaxiaOracleValidationError):
            c.metadata("not valid!")


# ── price_history ────────────────────────────────────────────────────────────


def test_price_history_hits_correct_path_with_default_range() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        captured["range"] = request.url.params.get("range", "")
        captured["interval"] = request.url.params.get("interval", "")
        return _ok(
            {
                "data": {
                    "symbol": "BTC",
                    "range": "24h",
                    "interval": "5m",
                    "count": 288,
                    "oldest_available": "2026-04-16T00:00:00Z",
                    "datapoints": [
                        {"timestamp": 1_776_000_000, "price": 74000.0, "samples": 1}
                    ],
                },
                "disclaimer": DISCLAIMER,
            }
        )

    with _client_with(handler) as c:
        result = c.price_history("BTC")
    assert captured["path"] == "/api/price/BTC/history"
    assert captured["method"] == "GET"
    assert captured["range"] == "24h"
    assert captured["interval"] == ""  # not sent when None
    assert result["data"]["count"] == 288
    assert len(result["data"]["datapoints"]) == 1


def test_price_history_propagates_range_and_interval() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["range"] = request.url.params.get("range", "")
        captured["interval"] = request.url.params.get("interval", "")
        return _ok(
            {
                "data": {
                    "symbol": "ETH",
                    "range": "7d",
                    "interval": "1h",
                    "count": 168,
                    "oldest_available": "2026-04-10T00:00:00Z",
                    "datapoints": [],
                },
                "disclaimer": DISCLAIMER,
            }
        )

    with _client_with(handler) as c:
        c.price_history("ETH", range_="7d", interval="1h")
    assert captured["range"] == "7d"
    assert captured["interval"] == "1h"


def test_price_history_rejects_invalid_symbol_locally() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("request should never leave the client")

    with _client_with(handler) as c:
        with pytest.raises(MaxiaOracleValidationError):
            c.price_history("bad-sym!")


# ── create_alert ─────────────────────────────────────────────────────────────


def test_create_alert_posts_correct_payload_and_parses_response() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/alerts"
        seen["body"] = json.loads(request.content)
        return _created(
            {
                "data": {
                    "id": 42,
                    "symbol": "BTC",
                    "condition": "above",
                    "threshold": 80000.0,
                    "active": True,
                    "callback_url": "https://example.com/hook",
                },
                "disclaimer": DISCLAIMER,
            }
        )

    with _client_with(handler) as c:
        result = c.create_alert(
            symbol="btc",
            condition="above",
            threshold=80000.0,
            callback_url="https://example.com/hook",
        )
    assert seen["body"]["symbol"] == "BTC"
    assert seen["body"]["condition"] == "above"
    assert seen["body"]["threshold"] == 80000.0
    assert seen["body"]["callback_url"] == "https://example.com/hook"
    assert result["data"]["id"] == 42
    assert result["data"]["active"] is True


def test_create_alert_rejects_invalid_condition_locally() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("request should never leave the client")

    with _client_with(handler) as c:
        with pytest.raises(MaxiaOracleValidationError):
            c.create_alert("BTC", condition="equal", threshold=80000.0, callback_url="https://example.com/hook")


def test_create_alert_rejects_non_positive_threshold_locally() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("request should never leave the client")

    with _client_with(handler) as c:
        with pytest.raises(MaxiaOracleValidationError):
            c.create_alert("BTC", condition="above", threshold=-1.0, callback_url="https://example.com/hook")
        with pytest.raises(MaxiaOracleValidationError):
            c.create_alert("BTC", condition="below", threshold=0.0, callback_url="https://example.com/hook")


def test_create_alert_rejects_invalid_symbol_locally() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("request should never leave the client")

    with _client_with(handler) as c:
        with pytest.raises(MaxiaOracleValidationError):
            c.create_alert("bad-sym!", condition="above", threshold=1.0, callback_url="https://example.com/hook")


# ── list_alerts ──────────────────────────────────────────────────────────────


def test_list_alerts_hits_correct_path_and_returns_list() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        assert request.headers["X-API-Key"] == "mxo_fake_test_key"
        return _ok(
            {
                "data": {
                    "alerts": [
                        {
                            "id": 1,
                            "symbol": "BTC",
                            "condition": "above",
                            "threshold": 80000.0,
                            "active": True,
                        }
                    ],
                    "count": 1,
                },
                "disclaimer": DISCLAIMER,
            }
        )

    with _client_with(handler) as c:
        result = c.list_alerts()
    assert captured["path"] == "/api/alerts"
    assert captured["method"] == "GET"
    assert result["data"]["count"] == 1
    assert result["data"]["alerts"][0]["id"] == 1


def test_list_alerts_returns_empty_list_gracefully() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok({"data": {"alerts": [], "count": 0}, "disclaimer": DISCLAIMER})

    with _client_with(handler) as c:
        result = c.list_alerts()
    assert result["data"]["count"] == 0
    assert result["data"]["alerts"] == []


# ── delete_alert ─────────────────────────────────────────────────────────────


def test_delete_alert_sends_delete_to_correct_path() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["method"] = request.method
        assert request.headers["X-API-Key"] == "mxo_fake_test_key"
        return _ok(
            {
                "data": {"id": 42, "deleted": True},
                "disclaimer": DISCLAIMER,
            }
        )

    with _client_with(handler) as c:
        result = c.delete_alert(42)
    assert captured["path"] == "/api/alerts/42"
    assert captured["method"] == "DELETE"
    assert result["data"]["deleted"] is True


def test_delete_alert_rejects_non_integer_id_locally() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("request should never leave the client")

    with _client_with(handler) as c:
        with pytest.raises(MaxiaOracleValidationError):
            c.delete_alert("42")  # type: ignore[arg-type]
        with pytest.raises(MaxiaOracleValidationError):
            c.delete_alert(True)  # type: ignore[arg-type]  # bool subclass of int


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
