"""LLMForge — In-memory response cache with TTL.

Simple hash-based cache to avoid redundant LLM calls.
Configurable TTL and max entries. Thread-safe via dict ordering.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field


@dataclass
class CacheEntry:
    response: str
    tier: str
    created_at: float
    tokens_in: int
    tokens_out: int


class ResponseCache:
    """LRU-style response cache with TTL expiration."""

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 1000) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._store: dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _key(prompt: str, system: str, tier: str | None) -> str:
        raw = f"{tier or 'auto'}:{system}:{prompt}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def get(self, prompt: str, system: str, tier: str | None) -> CacheEntry | None:
        key = self._key(prompt, system, tier)
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if time.time() - entry.created_at > self._ttl:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry

    def put(
        self,
        prompt: str,
        system: str,
        tier: str | None,
        response: str,
        tier_used: str,
        tokens_in: int,
        tokens_out: int,
    ) -> None:
        key = self._key(prompt, system, tier)
        self._store[key] = CacheEntry(
            response=response,
            tier=tier_used,
            created_at=time.time(),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
        # Evict oldest if over max
        while len(self._store) > self._max:
            oldest = next(iter(self._store))
            del self._store[oldest]

    def stats(self) -> dict:
        now = time.time()
        active = sum(1 for e in self._store.values() if now - e.created_at <= self._ttl)
        return {
            "entries": len(self._store),
            "active": active,
            "expired": len(self._store) - active,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / max(1, self._hits + self._misses), 3),
        }

    def clear(self) -> int:
        count = len(self._store)
        self._store.clear()
        return count
