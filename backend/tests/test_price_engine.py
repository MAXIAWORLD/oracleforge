"""TDD tests for services/price_engine.py — Multi-source price aggregation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.config import Settings
from services.price_engine import PriceEngine, AggregatedPrice
from services.sources import PriceResult


@pytest.fixture
def settings() -> Settings:
    return Settings(
        secret_key="test-secret-key-32-chars-ok!!",
        database_url="sqlite+aiosqlite:///:memory:",
        coingecko_enabled=True,
        pyth_enabled=True,
        chainlink_enabled=False,
        price_cache_ttl=30,
    )


@pytest.fixture
def engine(settings) -> PriceEngine:
    return PriceEngine(settings=settings, http_client=MagicMock())


class TestConfidenceScoring:
    def test_single_source_half_confidence(self) -> None:
        assert PriceEngine._compute_confidence([100.0]) == 0.5

    def test_identical_prices_high_confidence(self) -> None:
        conf = PriceEngine._compute_confidence([100.0, 100.0, 100.0])
        assert conf >= 0.95

    def test_close_prices_good_confidence(self) -> None:
        # <1% deviation
        conf = PriceEngine._compute_confidence([100.0, 100.5, 99.5])
        assert conf >= 0.90

    def test_divergent_prices_low_confidence(self) -> None:
        # Large deviation (>10%)
        conf = PriceEngine._compute_confidence([100.0, 115.0])
        assert conf < 0.60

    def test_moderate_deviation_moderate_confidence(self) -> None:
        # ~1% deviation — still good
        conf = PriceEngine._compute_confidence([100.0, 102.0])
        assert 0.70 < conf <= 0.99


class TestGetPrice:
    @pytest.mark.asyncio
    @patch("services.price_engine.fetch_coingecko")
    @patch("services.price_engine.fetch_pyth")
    async def test_aggregates_sources(self, mock_pyth, mock_cg, engine) -> None:
        mock_cg.return_value = PriceResult(price=100.0, source="coingecko", latency_ms=50)
        mock_pyth.return_value = PriceResult(price=100.5, source="pyth", latency_ms=30)

        result = await engine.get_price("BTC")
        assert result.symbol == "BTC"
        assert 99.0 < result.price_usd < 101.0
        assert result.sources_used == 2
        assert result.confidence > 0.5

    @pytest.mark.asyncio
    @patch("services.price_engine.fetch_coingecko")
    @patch("services.price_engine.fetch_pyth")
    async def test_cache_hit(self, mock_pyth, mock_cg, engine) -> None:
        mock_cg.return_value = PriceResult(price=100.0, source="coingecko", latency_ms=50)
        mock_pyth.return_value = PriceResult(price=100.0, source="pyth", latency_ms=30)

        await engine.get_price("ETH")
        result = await engine.get_price("ETH")
        assert result.cached is True
        # Only called once per source (first call)
        assert mock_cg.call_count == 1

    @pytest.mark.asyncio
    @patch("services.price_engine.fetch_coingecko")
    @patch("services.price_engine.fetch_pyth")
    async def test_handles_source_failure(self, mock_pyth, mock_cg, engine) -> None:
        mock_cg.return_value = PriceResult(source="coingecko", error="timeout")
        mock_pyth.return_value = PriceResult(price=100.0, source="pyth", latency_ms=30)

        result = await engine.get_price("SOL")
        assert result.price_usd > 0
        assert result.sources_used == 1
        assert result.confidence == 0.5  # single source

    @pytest.mark.asyncio
    @patch("services.price_engine.fetch_coingecko")
    @patch("services.price_engine.fetch_pyth")
    async def test_all_sources_fail(self, mock_pyth, mock_cg, engine) -> None:
        mock_cg.return_value = PriceResult(source="coingecko", error="down")
        mock_pyth.return_value = PriceResult(source="pyth", error="down")

        result = await engine.get_price("BTC")
        assert result.price_usd == 0.0
        assert result.confidence == 0.0


class TestBatchPrices:
    @pytest.mark.asyncio
    @patch("services.price_engine.fetch_coingecko")
    @patch("services.price_engine.fetch_pyth")
    async def test_batch(self, mock_pyth, mock_cg, engine) -> None:
        mock_cg.return_value = PriceResult(price=50.0, source="coingecko", latency_ms=50)
        mock_pyth.return_value = PriceResult(price=50.0, source="pyth", latency_ms=30)

        results = await engine.get_batch_prices(["BTC", "ETH"])
        assert len(results) == 2


class TestSourceStatuses:
    def test_returns_all_sources(self, engine) -> None:
        statuses = engine.get_source_statuses()
        names = [s["name"] for s in statuses]
        assert "coingecko" in names
        assert "pyth" in names
        assert "chainlink" in names

    def test_circuit_breaker_in_status(self, engine) -> None:
        statuses = engine.get_source_statuses()
        for s in statuses:
            assert "circuit" in s
            assert "state" in s["circuit"]
