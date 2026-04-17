"""Tests for V1.6 — Agent Intelligence Layer (confidence score, anomaly, context)."""
from __future__ import annotations

import importlib
import re
from unittest.mock import AsyncMock, patch

import pytest

from services.oracle.intelligence import (
    build_price_context,
    classify_agreement,
    compute_confidence_score,
    detect_anomaly,
)


# ── compute_confidence_score ─────────────────────────────────────────────────

class TestConfidenceScore:
    def test_no_sources_returns_zero(self):
        assert compute_confidence_score([], 0.0) == 0

    def test_single_source_fresh(self):
        sources = [{"price": 100.0, "age_s": 2, "confidence_pct": 0.5}]
        score = compute_confidence_score(sources, 0.0)
        assert 15 <= score <= 75

    def test_four_sources_low_divergence_fresh(self):
        sources = [
            {"price": 100.0, "age_s": 1, "confidence_pct": 0.3},
            {"price": 100.1, "age_s": 3, "confidence_pct": None},
            {"price": 100.05, "age_s": 2, "confidence_pct": 0.5},
            {"price": 100.02, "age_s": None},
        ]
        score = compute_confidence_score(sources, 0.1)
        assert score >= 80

    def test_two_sources_high_divergence_stale(self):
        sources = [
            {"price": 100.0, "age_s": 700},
            {"price": 105.0, "age_s": 800},
        ]
        score = compute_confidence_score(sources, 5.0)
        assert score <= 30

    def test_score_bounds(self):
        sources = [{"price": 1.0}]
        score = compute_confidence_score(sources, 0.0)
        assert 0 <= score <= 100

    def test_no_age_no_confidence_still_works(self):
        sources = [{"price": 50.0}, {"price": 50.1}]
        score = compute_confidence_score(sources, 0.2)
        assert 0 < score <= 100

    def test_perfect_score(self):
        sources = [
            {"price": 100.0, "age_s": 1, "confidence_pct": 0.1},
            {"price": 100.0, "age_s": 2, "confidence_pct": 0.2},
            {"price": 100.0, "age_s": 1, "confidence_pct": 0.3},
            {"price": 100.0, "age_s": 3, "confidence_pct": 0.4},
        ]
        score = compute_confidence_score(sources, 0.0)
        assert score == 100


# ── detect_anomaly ───────────────────────────────────────────────────────────

class TestDetectAnomaly:
    def test_no_anomaly_when_twap_insufficient(self):
        sources = [{"price": 100.0, "name": "src1"}]
        result = detect_anomaly("BTC", 100.0, sources)
        assert result["anomaly"] is False
        assert result["reasons"] == []

    def test_anomaly_on_source_outlier(self):
        sources = [
            {"price": 100.0, "name": "src1"},
            {"price": 115.0, "name": "src2"},  # 15% off median
        ]
        result = detect_anomaly("BTC", 100.0, sources)
        assert result["anomaly"] is True
        assert len(result["source_outliers"]) == 1
        assert result["source_outliers"][0]["source"] == "src2"

    def test_no_outlier_within_threshold(self):
        sources = [
            {"price": 100.0, "name": "src1"},
            {"price": 105.0, "name": "src2"},  # 5% — under 10% threshold
        ]
        result = detect_anomaly("BTC", 100.0, sources)
        outlier_triggered = any("src2" in r for r in result["reasons"])
        assert not outlier_triggered

    @patch("services.oracle.intelligence.pyth_oracle.check_twap_deviation")
    def test_anomaly_on_twap_deviation(self, mock_twap):
        mock_twap.return_value = {
            "ok": False,
            "twap": 100.0,
            "spot": 106.0,
            "deviation_pct": 6.0,
        }
        sources = [{"price": 106.0, "name": "src1"}]
        result = detect_anomaly("BTC", 106.0, sources)
        assert result["anomaly"] is True
        assert result["twap_deviation_pct"] == 6.0

    def test_twap_fields_always_present(self):
        sources = [{"price": 100.0, "name": "src1"}]
        result = detect_anomaly("BTC", 100.0, sources)
        assert "twap_5min" in result
        assert "twap_deviation_pct" in result
        assert "source_outliers" in result


# ── classify_agreement ───────────────────────────────────────────────────────

class TestClassifyAgreement:
    def test_single_source(self):
        assert classify_agreement(0.0, 1) == "single_source"

    def test_strong(self):
        assert classify_agreement(0.05, 3) == "strong"

    def test_good(self):
        assert classify_agreement(0.3, 3) == "good"

    def test_moderate(self):
        assert classify_agreement(1.5, 4) == "moderate"

    def test_weak(self):
        assert classify_agreement(3.0, 2) == "weak"


# ── build_price_context (integration) ────────────────────────────────────────

class TestBuildPriceContext:
    @pytest.mark.asyncio
    async def test_returns_none_no_sources(self):
        with patch(
            "services.oracle.intelligence.collect_sources",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await build_price_context("ZZZZ")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_full_context(self):
        fake_sources = [
            {"price": 75000.0, "age_s": 2, "confidence_pct": 0.1, "name": "pyth_crypto"},
            {"price": 75010.0, "age_s": 5, "confidence_pct": None, "name": "chainlink_base"},
            {"price": 74990.0, "age_s": None, "name": "price_oracle"},
        ]
        with patch(
            "services.oracle.intelligence.collect_sources",
            new_callable=AsyncMock,
            return_value=fake_sources,
        ):
            ctx = await build_price_context("BTC")

        assert ctx is not None
        assert ctx["symbol"] == "BTC"
        assert ctx["price"] > 0
        assert 0 <= ctx["confidence_score"] <= 100
        assert isinstance(ctx["anomaly"], bool)
        assert ctx["sources_agreement"] in ("strong", "good", "moderate", "weak", "single_source")
        assert ctx["source_count"] == 3
        assert "divergence_pct" in ctx
        assert "twap_5min" in ctx
        assert "twap_deviation_pct" in ctx
        assert "sources" in ctx
        assert "anomaly_reasons" in ctx

    @pytest.mark.asyncio
    async def test_context_freshest_age(self):
        fake_sources = [
            {"price": 100.0, "age_s": 10, "name": "a"},
            {"price": 100.0, "age_s": 2, "name": "b"},
        ]
        with patch(
            "services.oracle.intelligence.collect_sources",
            new_callable=AsyncMock,
            return_value=fake_sources,
        ):
            ctx = await build_price_context("ETH")
        assert ctx["freshest_age_s"] == 2


# ── Route /api/price/{symbol}/context (integration via TestClient) ───────────

class TestContextRoute:
    @pytest.fixture(autouse=True)
    def _setup(self, client, api_key):
        self.client = client
        self.api_key = api_key

    def test_context_invalid_symbol(self):
        resp = self.client.get(
            "/api/price/!!!/context",
            headers={"X-API-Key": self.api_key},
        )
        assert resp.status_code == 400

    def test_context_404_no_sources(self):
        with patch(
            "services.oracle.intelligence.collect_sources",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = self.client.get(
                "/api/price/ZZZZ/context",
                headers={"X-API-Key": self.api_key},
            )
        assert resp.status_code == 404

    def test_context_success_shape(self):
        fake_sources = [
            {"price": 75000.0, "age_s": 2, "confidence_pct": 0.1, "name": "pyth_crypto"},
            {"price": 75010.0, "age_s": 5, "confidence_pct": None, "name": "chainlink_base"},
        ]
        with patch(
            "services.oracle.intelligence.collect_sources",
            new_callable=AsyncMock,
            return_value=fake_sources,
        ):
            resp = self.client.get(
                "/api/price/BTC/context",
                headers={"X-API-Key": self.api_key},
            )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["symbol"] == "BTC"
        assert 0 <= data["confidence_score"] <= 100
        assert isinstance(data["anomaly"], bool)
        assert data["sources_agreement"] in ("strong", "good", "moderate", "weak", "single_source")


# ── Route /api/price/{symbol} enrichment (V1.6 fields) ──────────────────────

class TestPriceRouteEnriched:
    @pytest.fixture(autouse=True)
    def _setup(self, client, api_key):
        self.client = client
        self.api_key = api_key

    def test_price_includes_confidence_and_anomaly(self):
        fake_sources = [
            {"price": 75000.0, "age_s": 2, "confidence_pct": 0.1, "name": "pyth_crypto"},
            {"price": 75010.0, "age_s": 5, "confidence_pct": None, "name": "chainlink_base"},
        ]
        with patch(
            "api.routes_price.collect_sources",
            new_callable=AsyncMock,
            return_value=fake_sources,
        ):
            resp = self.client.get(
                "/api/price/BTC",
                headers={"X-API-Key": self.api_key},
            )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "confidence_score" in data
        assert "anomaly" in data
        assert "sources_agreement" in data


# ── MCP tool get_price_context ───────────────────────────────────────────────

class TestMCPPriceContext:
    @pytest.mark.asyncio
    async def test_mcp_tool_invalid_symbol(self):
        from mcp_server.tools import get_price_context
        result = await get_price_context("!!!")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_mcp_tool_success(self):
        from mcp_server.tools import get_price_context
        fake_sources = [
            {"price": 75000.0, "age_s": 2, "confidence_pct": 0.1, "name": "pyth_crypto"},
            {"price": 75010.0, "age_s": 5, "confidence_pct": None, "name": "chainlink_base"},
        ]
        with patch(
            "services.oracle.intelligence.collect_sources",
            new_callable=AsyncMock,
            return_value=fake_sources,
        ):
            result = await get_price_context("BTC")
        assert "data" in result
        assert result["data"]["confidence_score"] >= 0

    @pytest.mark.asyncio
    async def test_mcp_tool_no_sources(self):
        from mcp_server.tools import get_price_context
        with patch(
            "services.oracle.intelligence.collect_sources",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await get_price_context("ZZZZ")
        assert "error" in result


# ── MCP server tool list includes get_price_context ──────────────────────────

class TestMCPServerToolList:
    def test_tool_registered(self):
        from mcp_server.server import _TOOL_DEFINITIONS
        names = [t.name for t in _TOOL_DEFINITIONS]
        assert "get_price_context" in names

    def test_tool_dispatch_exists(self):
        from mcp_server.server import _TOOL_DISPATCH
        assert "get_price_context" in _TOOL_DISPATCH

    def test_total_tool_count(self):
        from mcp_server.server import _TOOL_DEFINITIONS
        assert len(_TOOL_DEFINITIONS) == 13
