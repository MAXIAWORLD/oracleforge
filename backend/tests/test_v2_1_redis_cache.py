"""V2.1 — Redis cache tests (fakeredis, no real Redis needed).

Tests are RED until services/cache/redis_cache.py is created and
multi_source.collect_sources() is wrapped with the cache.
"""

from __future__ import annotations

import asyncio

import pytest


# ── Unit tests — CachedPriceStore ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_miss_returns_none():
    """On a cold cache, get() must return None."""
    from fakeredis.aioredis import FakeRedis
    from services.cache.redis_cache import CachedPriceStore

    client = FakeRedis()
    store = CachedPriceStore(client, default_ttl=5)
    result = await store.get("BTC")
    assert result is None


@pytest.mark.asyncio
async def test_cache_set_then_get():
    """set() followed by get() must return the stored value."""
    from fakeredis.aioredis import FakeRedis
    from services.cache.redis_cache import CachedPriceStore

    client = FakeRedis()
    store = CachedPriceStore(client, default_ttl=5)
    sources = [{"name": "pyth", "price": 100.0, "age_s": 1, "stale": False}]
    await store.set("BTC", sources)
    result = await store.get("BTC")
    assert result is not None
    assert result[0]["price"] == 100.0
    assert result[0]["name"] == "pyth"


@pytest.mark.asyncio
async def test_cache_ttl_expiry():
    """Entries must expire after the configured TTL."""
    from fakeredis.aioredis import FakeRedis
    from services.cache.redis_cache import CachedPriceStore

    client = FakeRedis()
    store = CachedPriceStore(client, default_ttl=1)  # 1s TTL
    sources = [{"name": "pyth", "price": 50000.0, "age_s": 0}]
    await store.set("BTC", sources, ttl=1)

    await asyncio.sleep(1.1)
    result = await store.get("BTC")
    assert result is None, "Entry must expire after TTL"


@pytest.mark.asyncio
async def test_cache_set_custom_ttl():
    """set() with explicit ttl must override the default."""
    from fakeredis.aioredis import FakeRedis
    from services.cache.redis_cache import CachedPriceStore

    client = FakeRedis()
    store = CachedPriceStore(client, default_ttl=60)
    sources = [{"name": "chainlink_base", "price": 3000.0}]
    await store.set("ETH", sources, ttl=2)
    await asyncio.sleep(2.1)
    result = await store.get("ETH")
    assert result is None, "Custom TTL must be respected"


@pytest.mark.asyncio
async def test_cache_different_symbols_isolated():
    """Cached entries for different symbols must not interfere."""
    from fakeredis.aioredis import FakeRedis
    from services.cache.redis_cache import CachedPriceStore

    client = FakeRedis()
    store = CachedPriceStore(client, default_ttl=30)
    await store.set("BTC", [{"name": "pyth", "price": 50000.0}])
    await store.set("ETH", [{"name": "pyth", "price": 3000.0}])

    btc = await store.get("BTC")
    eth = await store.get("ETH")
    assert btc is not None and btc[0]["price"] == 50000.0
    assert eth is not None and eth[0]["price"] == 3000.0


@pytest.mark.asyncio
async def test_cache_invalidate():
    """invalidate() must remove the cached entry."""
    from fakeredis.aioredis import FakeRedis
    from services.cache.redis_cache import CachedPriceStore

    client = FakeRedis()
    store = CachedPriceStore(client, default_ttl=60)
    await store.set("SOL", [{"name": "pyth", "price": 140.0}])
    await store.invalidate("SOL")
    result = await store.get("SOL")
    assert result is None


# ── Fallback: Redis down → in-memory ────────────────────────────────────────


@pytest.mark.asyncio
async def test_unavailable_store_returns_none_on_get():
    """If Redis is unavailable, get() must return None (no crash)."""
    from services.cache.redis_cache import UnavailablePriceStore

    store = UnavailablePriceStore()
    result = await store.get("BTC")
    assert result is None


@pytest.mark.asyncio
async def test_unavailable_store_set_is_noop():
    """If Redis is unavailable, set() must be a no-op (no crash)."""
    from services.cache.redis_cache import UnavailablePriceStore

    store = UnavailablePriceStore()
    await store.set("BTC", [{"name": "pyth", "price": 50000.0}])
    result = await store.get("BTC")
    assert result is None


# ── get_price_store() factory ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_price_store_returns_store():
    """get_price_store() must return a working store."""
    import os

    os.environ["REDIS_URL"] = (
        "redis://127.0.0.1:9999"  # non-existent — fallback expected
    )

    from services.cache import redis_cache

    # Force re-init
    redis_cache._price_store = None

    store = await redis_cache.get_price_store()
    # Whether Redis or UnavailablePriceStore, get() must not crash
    result = await store.get("BTC")
    assert result is None  # Cold cache either way

    redis_cache._price_store = None  # cleanup
