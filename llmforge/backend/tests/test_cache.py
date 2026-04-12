"""TDD tests for services/cache.py — Response cache with TTL."""

from __future__ import annotations

import time

from services.cache import ResponseCache


class TestResponseCache:
    def test_put_and_get(self) -> None:
        cache = ResponseCache(ttl_seconds=60)
        cache.put("hello", "", None, "world", "local", 10, 5)
        entry = cache.get("hello", "", None)
        assert entry is not None
        assert entry.response == "world"
        assert entry.tier == "local"

    def test_miss_returns_none(self) -> None:
        cache = ResponseCache(ttl_seconds=60)
        assert cache.get("missing", "", None) is None

    def test_expired_returns_none(self) -> None:
        cache = ResponseCache(ttl_seconds=0)  # instant expiry
        cache.put("hello", "", None, "world", "local", 10, 5)
        # Sleep briefly to ensure expiry
        import time
        time.sleep(0.01)
        assert cache.get("hello", "", None) is None

    def test_max_entries_eviction(self) -> None:
        cache = ResponseCache(ttl_seconds=60, max_entries=2)
        cache.put("a", "", None, "1", "local", 1, 1)
        cache.put("b", "", None, "2", "local", 1, 1)
        cache.put("c", "", None, "3", "local", 1, 1)
        assert cache.stats()["entries"] <= 2

    def test_stats(self) -> None:
        cache = ResponseCache(ttl_seconds=60)
        cache.put("x", "", None, "y", "fast", 5, 5)
        cache.get("x", "", None)  # hit
        cache.get("miss", "", None)  # miss
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["entries"] == 1

    def test_clear(self) -> None:
        cache = ResponseCache(ttl_seconds=60)
        cache.put("a", "", None, "b", "local", 1, 1)
        count = cache.clear()
        assert count == 1
        assert cache.stats()["entries"] == 0

    def test_different_tiers_different_keys(self) -> None:
        cache = ResponseCache(ttl_seconds=60)
        cache.put("hello", "", "fast", "response1", "fast", 10, 5)
        cache.put("hello", "", "mid", "response2", "mid", 10, 5)
        assert cache.get("hello", "", "fast").response == "response1"
        assert cache.get("hello", "", "mid").response == "response2"
