"""OracleForge — Multi-source Price Engine with confidence scoring.

Core differentiator: cross-verification across sources with confidence scoring.
- Fetches from all enabled sources in parallel
- Computes confidence based on source agreement
- Circuit breaker per source to handle failures gracefully
- TTL-based caching to reduce API calls
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

import httpx

from core.config import Settings
from services.circuit_breaker import CircuitBreaker
from services.sources import (
    PriceResult, fetch_coingecko, fetch_pyth, fetch_chainlink,
    fetch_yahoo, fetch_finnhub,
)

logger = logging.getLogger(__name__)


@dataclass
class AggregatedPrice:
    """Result of multi-source price aggregation."""

    symbol: str
    price_usd: float
    confidence: float
    sources_used: int
    sources_available: int
    latency_ms: int
    source_details: list[dict] = field(default_factory=list)
    cached: bool = False


class PriceEngine:
    """Multi-source price oracle with confidence scoring and circuit breakers."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http_client
        self._cache: dict[str, tuple[AggregatedPrice, float]] = {}  # symbol → (price, timestamp)
        self._breakers: dict[str, CircuitBreaker] = {}

    def _get_breaker(self, source: str) -> CircuitBreaker:
        if source not in self._breakers:
            self._breakers[source] = CircuitBreaker(
                threshold=self._settings.circuit_breaker_threshold,
                ttl=self._settings.circuit_breaker_ttl,
            )
        return self._breakers[source]

    async def get_price(self, symbol: str) -> AggregatedPrice:
        """Fetch price from all enabled sources, cross-verify, return with confidence."""
        symbol = symbol.upper()
        t0 = time.monotonic()

        # Check cache
        if symbol in self._cache:
            cached_price, cached_at = self._cache[symbol]
            ttl = self._settings.price_cache_ttl
            if time.time() - cached_at < ttl:
                return AggregatedPrice(
                    symbol=symbol,
                    price_usd=cached_price.price_usd,
                    confidence=cached_price.confidence,
                    sources_used=cached_price.sources_used,
                    sources_available=cached_price.sources_available,
                    latency_ms=0,
                    source_details=cached_price.source_details,
                    cached=True,
                )

        # Fetch from all sources in parallel
        tasks: list[tuple[str, asyncio.Task]] = []
        if self._settings.coingecko_enabled and not self._get_breaker("coingecko").is_open:
            tasks.append(("coingecko", asyncio.create_task(
                fetch_coingecko(symbol, self._http)
            )))
        if self._settings.pyth_enabled and not self._get_breaker("pyth").is_open:
            tasks.append(("pyth", asyncio.create_task(
                fetch_pyth(symbol, self._http, self._settings.pyth_hermes_url)
            )))
        if self._settings.chainlink_enabled and not self._get_breaker("chainlink").is_open:
            tasks.append(("chainlink", asyncio.create_task(
                fetch_chainlink(symbol, self._http, self._settings.base_rpc_url)
            )))
        if self._settings.yahoo_enabled and not self._get_breaker("yahoo").is_open:
            tasks.append(("yahoo", asyncio.create_task(
                fetch_yahoo(symbol, self._http)
            )))
        if self._settings.finnhub_enabled and self._settings.finnhub_api_key and not self._get_breaker("finnhub").is_open:
            tasks.append(("finnhub", asyncio.create_task(
                fetch_finnhub(symbol, self._http, self._settings.finnhub_api_key)
            )))

        sources_available = len(tasks)
        if sources_available == 0:
            return AggregatedPrice(
                symbol=symbol, price_usd=0.0, confidence=0.0,
                sources_used=0, sources_available=0,
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        # Gather results
        results: list[PriceResult] = []
        for source_name, task in tasks:
            result: PriceResult = await task
            breaker = self._get_breaker(source_name)
            if result.ok:
                breaker.record_success()
                results.append(result)
            else:
                breaker.record_failure(result.error or "unknown")

        if not results:
            return AggregatedPrice(
                symbol=symbol, price_usd=0.0, confidence=0.0,
                sources_used=0, sources_available=sources_available,
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        # Cross-verify and compute confidence
        prices = [r.price for r in results]
        avg_price = sum(prices) / len(prices)
        confidence = self._compute_confidence(prices)

        latency_ms = int((time.monotonic() - t0) * 1000)
        source_details = [
            {"source": r.source, "price": round(r.price, 6), "latency_ms": r.latency_ms}
            for r in results
        ]

        agg = AggregatedPrice(
            symbol=symbol,
            price_usd=round(avg_price, 6),
            confidence=round(confidence, 3),
            sources_used=len(results),
            sources_available=sources_available,
            latency_ms=latency_ms,
            source_details=source_details,
        )

        # Cache
        self._cache[symbol] = (agg, time.time())
        return agg

    async def get_batch_prices(self, symbols: list[str]) -> list[AggregatedPrice]:
        """Fetch prices for multiple symbols in parallel."""
        tasks = [self.get_price(s) for s in symbols]
        return await asyncio.gather(*tasks)

    @staticmethod
    def _compute_confidence(prices: list[float]) -> float:
        """Compute confidence score based on source agreement.

        - 1 source: 0.5 (no cross-verification possible)
        - 2+ sources: based on max deviation from mean
          - <1% deviation: 0.95+ confidence
          - 1-3%: 0.80-0.95
          - 3-5%: 0.60-0.80
          - >5%: below 0.60 (anomaly)
        """
        if len(prices) == 1:
            return 0.5
        avg = sum(prices) / len(prices)
        if avg == 0:
            return 0.0
        max_deviation = max(abs(p - avg) / avg for p in prices)
        if max_deviation < 0.01:
            return min(0.99, 0.95 + (1 - max_deviation / 0.01) * 0.04)
        if max_deviation < 0.03:
            return 0.80 + (0.03 - max_deviation) / 0.02 * 0.15
        if max_deviation < 0.05:
            return 0.60 + (0.05 - max_deviation) / 0.02 * 0.20
        return max(0.1, 0.60 - max_deviation)

    def get_source_statuses(self) -> list[dict]:
        """Return health status of all configured sources."""
        sources = []
        for name, enabled in [
            ("coingecko", self._settings.coingecko_enabled),
            ("pyth", self._settings.pyth_enabled),
            ("chainlink", self._settings.chainlink_enabled),
            ("finnhub", self._settings.finnhub_enabled),
            ("yahoo", self._settings.yahoo_enabled),
        ]:
            breaker = self._get_breaker(name)
            sources.append({
                "name": name,
                "enabled": enabled,
                "healthy": not breaker.is_open,
                "circuit": breaker.get_status(),
            })
        return sources

    def cache_stats(self) -> dict:
        """Return cache statistics."""
        now = time.time()
        active = sum(
            1 for _, ts in self._cache.values()
            if now - ts < self._settings.price_cache_ttl
        )
        return {
            "entries": len(self._cache),
            "active": active,
            "expired": len(self._cache) - active,
        }
