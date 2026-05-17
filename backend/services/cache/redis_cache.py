"""MAXIA Oracle — Redis-backed price source cache (V2.1).

Provides a shared L2 cache across uvicorn workers so that simultaneous
requests to the same symbol are served from a single fetch rather than
N parallel upstream calls (one per worker).

Architecture:
    L1 — per-oracle in-memory caches (pyth: 5s, chainlink: 30s) absorb
         intra-worker request bursts. Already present; not replaced.
    L2 — this module: Redis key per symbol, default TTL 5s. Wraps
         collect_sources() so the first worker to fetch a price stores
         the full source list; subsequent workers within the TTL window
         return the cached list instantly.

Failure mode: if Redis is unreachable at startup or during a call,
UnavailablePriceStore is used instead — a no-op that never raises.
This means a Redis outage degrades gracefully to the pre-V2.1 behavior
(individual oracle caches still work; only cross-worker sharing is lost).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Protocol

logger = logging.getLogger("redis_cache")

_REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379")
_DEFAULT_TTL = int(os.getenv("CACHE_TTL_S", "5"))
_KEY_PREFIX = "maxia:oracle:sources:"

# Module-level singleton — initialised lazily on first request.
_price_store: "PriceStore | None" = None


# ── Protocol ─────────────────────────────────────────────────────────────────


class PriceStore(Protocol):
    async def get(self, symbol: str) -> list[dict[str, Any]] | None: ...
    async def set(
        self, symbol: str, sources: list[dict[str, Any]], ttl: int | None = None
    ) -> None: ...
    async def invalidate(self, symbol: str) -> None: ...


# ── Implementations ───────────────────────────────────────────────────────────


class CachedPriceStore:
    """Redis-backed store. One JSON-serialised key per symbol."""

    def __init__(self, client: Any, default_ttl: int = _DEFAULT_TTL) -> None:
        self._client = client
        self._default_ttl = default_ttl

    def _key(self, symbol: str) -> str:
        return f"{_KEY_PREFIX}{symbol.upper()}"

    async def get(self, symbol: str) -> list[dict[str, Any]] | None:
        try:
            raw = await self._client.get(self._key(symbol))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Redis get failed for %s: %s", symbol, exc)
            return None

    async def set(
        self, symbol: str, sources: list[dict[str, Any]], ttl: int | None = None
    ) -> None:
        try:
            await self._client.setex(
                self._key(symbol),
                ttl if ttl is not None else self._default_ttl,
                json.dumps(sources),
            )
        except Exception as exc:
            logger.warning("Redis set failed for %s: %s", symbol, exc)

    async def invalidate(self, symbol: str) -> None:
        try:
            await self._client.delete(self._key(symbol))
        except Exception as exc:
            logger.warning("Redis delete failed for %s: %s", symbol, exc)


class UnavailablePriceStore:
    """No-op store used when Redis is unreachable. Never raises."""

    async def get(self, symbol: str) -> list[dict[str, Any]] | None:
        return None

    async def set(
        self, symbol: str, sources: list[dict[str, Any]], ttl: int | None = None
    ) -> None:
        pass

    async def invalidate(self, symbol: str) -> None:
        pass


# ── Factory ───────────────────────────────────────────────────────────────────


async def get_price_store() -> PriceStore:
    """Return the module-level PriceStore, initialising it on first call."""
    global _price_store
    if _price_store is not None:
        return _price_store

    try:
        from redis.asyncio import from_url as redis_from_url

        client = redis_from_url(
            _REDIS_URL, decode_responses=True, socket_connect_timeout=1
        )
        # Ping to confirm reachability before committing to this store.
        await client.ping()
        _price_store = CachedPriceStore(client, default_ttl=_DEFAULT_TTL)
        logger.info("Redis cache active — %s, TTL=%ds", _REDIS_URL, _DEFAULT_TTL)
    except Exception as exc:
        logger.warning(
            "Redis unavailable (%s) — cache disabled, falling back to no-cache", exc
        )
        _price_store = UnavailablePriceStore()

    return _price_store


# ── Cached wrapper ────────────────────────────────────────────────────────────


async def cached_collect_sources(
    symbol: str,
    ttl: int | None = None,
) -> list[dict[str, Any]]:
    """collect_sources() wrapped with Redis L2 cache.

    Cache miss → calls collect_sources(), stores result, returns it.
    Cache hit  → returns cached source list immediately (no upstream calls).
    Redis down → falls through to collect_sources() transparently.
    """
    from services.oracle.multi_source import collect_sources

    store = await get_price_store()
    cached = await store.get(symbol)
    if cached is not None:
        return cached

    sources = await collect_sources(symbol)
    if sources:
        await store.set(symbol, sources, ttl=ttl)
    return sources
