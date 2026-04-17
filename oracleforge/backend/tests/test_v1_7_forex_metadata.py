"""Tests for V1.7 — Forex dispatch + Asset metadata."""
from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Forex dispatch ─────────────────────────────────────────────────────────────

class TestForexDispatch:
    """V1.7 — /api/price/EUR and /api/price/GBP route to Pyth Solana."""

    def test_eur_dispatches_to_pyth_solana(self, client, api_key):
        mock_result = {
            "price": 1.085,
            "conf": 0.0002,
            "confidence_pct": 0.018,
            "publish_time": 1713400000,
            "age_s": 3,
            "stale": False,
            "source": "pyth_solana",
            "symbol": "EUR",
            "price_account": "Fu76ChamBDjE8UuGLV6GP2AcPPSU6gjhkNhAyuoPm7ny",
            "posted_slot": 300000000,
            "exponent": -8,
            "feed_id": "a995d00bb36a63cef7fd2c287dc105fc8f3d93779f062f09551b0af3e81ec30b",
        }
        with patch(
            "services.oracle.pyth_solana_oracle.get_pyth_solana_price",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_pyth:
            resp = client.get(
                "/api/price/EUR", headers={"X-API-Key": api_key}
            )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["asset_class"] == "forex"
        assert data["source"] == "pyth_solana"
        assert data["price"] == 1.085
        mock_pyth.assert_called_once_with("EUR")

    def test_gbp_dispatches_to_pyth_solana(self, client, api_key):
        mock_result = {
            "price": 1.265,
            "source": "pyth_solana",
            "symbol": "GBP",
            "age_s": 2,
            "stale": False,
        }
        with patch(
            "services.oracle.pyth_solana_oracle.get_pyth_solana_price",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.get(
                "/api/price/GBP", headers={"X-API-Key": api_key}
            )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["asset_class"] == "forex"
        assert data["symbol"] == "GBP"

    def test_eur_lowercase_is_uppercased(self, client, api_key):
        mock_result = {
            "price": 1.085,
            "source": "pyth_solana",
            "symbol": "EUR",
            "age_s": 3,
            "stale": False,
        }
        with patch(
            "services.oracle.pyth_solana_oracle.get_pyth_solana_price",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.get(
                "/api/price/eur", headers={"X-API-Key": api_key}
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["asset_class"] == "forex"

    def test_forex_error_returns_502(self, client, api_key):
        with patch(
            "services.oracle.pyth_solana_oracle.get_pyth_solana_price",
            new_callable=AsyncMock,
            return_value={"error": "RPC pool exhausted"},
        ):
            resp = client.get(
                "/api/price/EUR", headers={"X-API-Key": api_key}
            )
        assert resp.status_code == 502
        assert "forex price fetch failed" in resp.json()["error"]

    def test_btc_does_not_dispatch_to_forex(self, client, api_key):
        with patch(
            "services.oracle.multi_source.collect_sources",
            new_callable=AsyncMock,
            return_value=[
                {"name": "pyth_crypto", "price": 74000.0, "age_s": 1},
                {"name": "chainlink_base", "price": 74100.0, "age_s": 5},
            ],
        ):
            resp = client.get(
                "/api/price/BTC", headers={"X-API-Key": api_key}
            )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["asset_class"] == "crypto"

    def test_crypto_response_has_asset_class_crypto(self, client, api_key):
        with patch(
            "services.oracle.multi_source.collect_sources",
            new_callable=AsyncMock,
            return_value=[
                {"name": "pyth_crypto", "price": 2400.0, "age_s": 2},
            ],
        ):
            resp = client.get(
                "/api/price/ETH", headers={"X-API-Key": api_key}
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["asset_class"] == "crypto"


# ── Asset metadata ────────────────────────────────────────────────────────────

class TestMetadata:
    """V1.7 — GET /api/metadata/{symbol}."""

    def test_btc_metadata_success(self, client, api_key):
        mock_result = {
            "symbol": "BTC",
            "name": "Bitcoin",
            "market_cap_usd": 1480000000000,
            "volume_24h_usd": 28500000000,
            "price_change_24h_pct": -2.3,
            "circulating_supply": 19640000,
            "total_supply": 21000000,
            "max_supply": 21000000,
            "market_cap_rank": 1,
            "ath_usd": 108786,
            "atl_usd": 67.81,
            "last_updated": "2026-04-17T10:00:00.000Z",
            "source": "coingecko",
        }
        with patch(
            "services.oracle.metadata.get_metadata",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.get(
                "/api/metadata/BTC", headers={"X-API-Key": api_key}
            )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["symbol"] == "BTC"
        assert data["name"] == "Bitcoin"
        assert data["market_cap_usd"] == 1480000000000
        assert data["source"] == "coingecko"
        assert "disclaimer" in resp.json()

    def test_unknown_symbol_returns_404(self, client, api_key):
        resp = client.get(
            "/api/metadata/ZZZZZZ", headers={"X-API-Key": api_key}
        )
        assert resp.status_code == 404
        assert "no metadata available" in resp.json()["error"]

    def test_invalid_symbol_returns_400(self, client, api_key):
        resp = client.get(
            "/api/metadata/bad!sym", headers={"X-API-Key": api_key}
        )
        assert resp.status_code == 400

    def test_metadata_error_returns_502(self, client, api_key):
        with patch(
            "services.oracle.metadata.get_metadata",
            new_callable=AsyncMock,
            return_value={"error": "CoinGecko returned 429"},
        ):
            resp = client.get(
                "/api/metadata/BTC", headers={"X-API-Key": api_key}
            )
        assert resp.status_code == 502
        assert "metadata fetch failed" in resp.json()["error"]

    def test_metadata_requires_auth(self, client):
        resp = client.get("/api/metadata/BTC")
        assert resp.status_code == 401

    def test_sol_has_metadata(self, client, api_key):
        mock_result = {
            "symbol": "SOL",
            "name": "Solana",
            "market_cap_usd": 35000000000,
            "volume_24h_usd": 1200000000,
            "price_change_24h_pct": 1.5,
            "circulating_supply": 420000000,
            "total_supply": None,
            "max_supply": None,
            "market_cap_rank": 5,
            "ath_usd": 260.06,
            "atl_usd": 0.50,
            "last_updated": "2026-04-17T10:00:00.000Z",
            "source": "coingecko",
        }
        with patch(
            "services.oracle.metadata.get_metadata",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.get(
                "/api/metadata/SOL", headers={"X-API-Key": api_key}
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Solana"


# ── metadata module unit tests ────────────────────────────────────────────────

class TestMetadataModule:
    """Unit tests for services/oracle/metadata.py."""

    def test_has_metadata_true_for_btc(self):
        from services.oracle.metadata import has_metadata
        assert has_metadata("BTC") is True

    def test_has_metadata_false_for_forex(self):
        from services.oracle.metadata import has_metadata
        assert has_metadata("EUR") is False
        assert has_metadata("GBP") is False

    def test_has_metadata_false_for_unknown(self):
        from services.oracle.metadata import has_metadata
        assert has_metadata("ZZZZZ") is False

    def test_supported_symbols_is_sorted(self):
        from services.oracle.metadata import supported_symbols
        syms = supported_symbols()
        assert syms == sorted(syms)
        assert len(syms) > 50

    def test_circuit_breaker_status_shape(self):
        from services.oracle.metadata import get_circuit_breaker_status
        status = get_circuit_breaker_status()
        assert status["name"] == "coingecko_metadata"
        assert status["state"] in ("open", "closed")
        assert "failures" in status
        assert "max" in status

    @pytest.mark.asyncio
    async def test_get_metadata_unknown_symbol(self):
        from services.oracle.metadata import get_metadata
        result = await get_metadata("ZZZZZ")
        assert "error" in result
        assert "no CoinGecko mapping" in result["error"]


# ── MCP tool V1.7 ────────────────────────────────────────────────────────────

class TestMCPToolMetadata:
    """V1.7 — get_asset_metadata MCP tool."""

    def test_tool_registered(self):
        from mcp_server.server import _TOOL_DISPATCH
        assert "get_asset_metadata" in _TOOL_DISPATCH

    def test_tool_definition_exists(self):
        from mcp_server.server import _TOOL_DEFINITIONS
        names = [t.name for t in _TOOL_DEFINITIONS]
        assert "get_asset_metadata" in names

    def test_tool_count_is_13(self):
        from mcp_server.server import _TOOL_DEFINITIONS
        assert len(_TOOL_DEFINITIONS) == 13

    @pytest.mark.asyncio
    async def test_tool_invalid_symbol(self):
        from mcp_server.tools import get_asset_metadata
        result = await get_asset_metadata("bad!sym")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_tool_unknown_symbol(self):
        from mcp_server.tools import get_asset_metadata
        result = await get_asset_metadata("ZZZZZ")
        assert "error" in result
        assert "no metadata" in result["error"]

    @pytest.mark.asyncio
    async def test_tool_success(self):
        from mcp_server.tools import get_asset_metadata
        mock_result = {
            "symbol": "ETH",
            "name": "Ethereum",
            "market_cap_usd": 300000000000,
            "source": "coingecko",
        }
        with patch(
            "services.oracle.metadata.get_metadata",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await get_asset_metadata("ETH")
        assert "data" in result
        assert result["data"]["name"] == "Ethereum"
        assert "disclaimer" in result


# ── MCP forex dispatch in get_price ──────────────────────────────────────────

class TestMCPForexDispatch:
    """V1.7 — get_price MCP tool dispatches forex to Pyth Solana."""

    @pytest.mark.asyncio
    async def test_mcp_get_price_eur_dispatches_forex(self):
        from mcp_server.tools import get_price
        mock_result = {
            "price": 1.085,
            "source": "pyth_solana",
            "symbol": "EUR",
            "age_s": 3,
            "stale": False,
        }
        with patch(
            "services.oracle.pyth_solana_oracle.get_pyth_solana_price",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_pyth:
            result = await get_price("EUR")
        assert "data" in result
        assert result["data"]["asset_class"] == "forex"
        mock_pyth.assert_called_once_with("EUR")

    @pytest.mark.asyncio
    async def test_mcp_get_price_btc_not_forex(self):
        from mcp_server.tools import get_price
        with patch(
            "services.oracle.multi_source.collect_sources",
            new_callable=AsyncMock,
            return_value=[
                {"name": "pyth_crypto", "price": 74000.0, "age_s": 1},
            ],
        ):
            result = await get_price("BTC")
        assert "data" in result
        assert result["data"]["asset_class"] == "crypto"


# ── Server version bump ──────────────────────────────────────────────────────

class TestVersionBump:
    def test_server_version_is_0_1_7(self):
        from mcp_server.server import SERVER_VERSION
        assert SERVER_VERSION == "0.1.7"
