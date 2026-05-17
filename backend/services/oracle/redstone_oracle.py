"""MAXIA Oracle — RedStone public REST price reader (V1.3, 4th upstream).

RedStone publishes 400+ assets (crypto majors + long-tail + forex + equities)
through a public JSON REST API gated only by a provider tag. V1.3 adds it
as a 4th independent upstream alongside Pyth (Hermes + Solana on-chain),
Chainlink (Base/Ethereum/Arbitrum) and the price_oracle aggregator.

Design decisions (from docs/v1.3_redstone_eliza_pyth_solana.md):
    R1  endpoint: https://api.redstone.finance/prices?symbol=<SYM>
                  &provider=redstone-primary-prod&limit=1
    R2  no feed dict — we attempt every symbol. 404 / empty reply is silent-dropped.
    R3  cache TTL 10s.
    R4  shape parity with chainlink_oracle: price, publish_time, age_s,
        stale, source='redstone', symbol. Stale if age_s > 300 (5 min).
    R5  dedicated /api/redstone/{symbol} route exists upstream.

Failures never raise — the function returns {"error": str, "source":
"redstone"} so collect_sources() drops the entry silently.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Final

import httpx

from core.errors import safe_error
from core.http_client import get_http_client

logger = logging.getLogger("redstone_oracle")

# ── Constants ───────────────────────────────────────────────────────────────

REDSTONE_URL: Final[str] = "https://api.redstone.finance/prices"
# The public gateway accepts "redstone" (the canonical primary provider) —
# other provider names exist (redstone-rapid, redstone-stocks) but coverage
# on the canonical one is the widest. Confirmed live 2026-04-16.
REDSTONE_PROVIDER: Final[str] = "redstone"
REDSTONE_TIMEOUT_S: Final[float] = 8.0

_CACHE_TTL_S: Final[int] = 10
_CACHE_MAX: Final[int] = 200
_STALE_AFTER_S: Final[int] = 300  # RedStone publish ~10s; 5min = dead feed

# ── Cache (keyed by symbol, uppercase) ──────────────────────────────────────

_cache: dict[str, dict[str, Any]] = {}

# ── Circuit breaker ─────────────────────────────────────────────────────────

_CB_MAX_FAILURES: Final[int] = 5
_CB_COOLDOWN_S: Final[int] = 60
_cb_failures: int = 0
_cb_open_until: float = 0.0

# ── Metrics ─────────────────────────────────────────────────────────────────

_metrics: dict[str, Any] = {
    "total_requests": 0,
    "successful": 0,
    "errors": 0,
    "cache_hits": 0,
    "symbols_not_found": 0,
    "circuit_breaks": 0,
}


def _circuit_is_open() -> bool:
    """True iff the circuit breaker is currently tripped."""
    if _cb_failures < _CB_MAX_FAILURES:
        return False
    return time.time() < _cb_open_until


def _record_success() -> None:
    global _cb_failures
    _cb_failures = 0


def _record_failure() -> None:
    global _cb_failures, _cb_open_until
    _cb_failures += 1
    if _cb_failures >= _CB_MAX_FAILURES:
        _cb_open_until = time.time() + _CB_COOLDOWN_S
        _metrics["circuit_breaks"] += 1
        logger.warning(
            "[redstone] circuit OPEN after %d failures, cooldown %ds",
            _cb_failures, _CB_COOLDOWN_S,
        )


# ── Input validation ────────────────────────────────────────────────────────

_SYMBOL_MAX_LEN: Final[int] = 10


def _sanitize_symbol(symbol: str) -> str | None:
    """Return a canonical uppercase ticker, or None if malformed."""
    if not isinstance(symbol, str):
        return None
    cleaned = symbol.strip().upper()
    if not cleaned or len(cleaned) > _SYMBOL_MAX_LEN:
        return None
    # Same charset as the rest of the oracle surface: [A-Z0-9]{1,10}.
    if not all(c.isalnum() for c in cleaned):
        return None
    return cleaned


# ── Public API ──────────────────────────────────────────────────────────────


async def get_redstone_price(symbol: str) -> dict[str, Any]:
    """Fetch a single price from the RedStone public REST API.

    Returns:
        On success: {"price": float, "publish_time": int, "age_s": int,
                     "stale": bool, "source": "redstone", "symbol": str,
                     "provider": REDSTONE_PROVIDER}
        On failure: {"error": str, "source": "redstone", "symbol": str}

    Never raises. Unknown symbols return an `error` so collect_sources()
    can drop them silently without polluting the aggregated median.
    """
    cleaned = _sanitize_symbol(symbol)
    if cleaned is None:
        return {
            "error": "invalid symbol format",
            "source": "redstone",
            "symbol": str(symbol)[:32],
        }

    _metrics["total_requests"] += 1
    now = time.time()

    # 1. Cache hit short-circuit.
    cached = _cache.get(cleaned)
    if cached and now - cached["ts"] < _CACHE_TTL_S:
        _metrics["cache_hits"] += 1
        return cached["data"]

    # 2. Circuit breaker — fail fast without touching the network.
    if _circuit_is_open():
        return {
            "error": "redstone circuit open",
            "source": "redstone",
            "symbol": cleaned,
        }

    # 3. Live fetch.
    try:
        client = get_http_client()
        resp = await client.get(
            REDSTONE_URL,
            params={
                "symbol": cleaned,
                "provider": REDSTONE_PROVIDER,
                "limit": 1,
            },
            timeout=REDSTONE_TIMEOUT_S,
        )
    except httpx.TimeoutException:
        _metrics["errors"] += 1
        _record_failure()
        return {"error": "redstone timeout", "source": "redstone", "symbol": cleaned}
    except Exception as exc:  # noqa: BLE001 — isolate transport errors
        _metrics["errors"] += 1
        _record_failure()
        return {
            "error": safe_error("redstone fetch failed", exc, logger),
            "source": "redstone",
            "symbol": cleaned,
        }

    if resp.status_code == 404:
        _metrics["symbols_not_found"] += 1
        # NOT a circuit failure — the server answered correctly that the
        # symbol is unknown. Don't poison the breaker with legitimate 404s.
        return {
            "error": "symbol not found on redstone",
            "source": "redstone",
            "symbol": cleaned,
        }

    if resp.status_code != 200:
        _metrics["errors"] += 1
        _record_failure()
        return {
            "error": f"redstone HTTP {resp.status_code}",
            "source": "redstone",
            "symbol": cleaned,
        }

    try:
        payload = resp.json()
    except ValueError as exc:
        _metrics["errors"] += 1
        _record_failure()
        return {
            "error": safe_error("redstone JSON decode failed", exc, logger),
            "source": "redstone",
            "symbol": cleaned,
        }

    # RedStone returns either a list of entries (when limit>=1) or an object
    # keyed by symbol. Normalize.
    entry: dict[str, Any] | None = None
    if isinstance(payload, list):
        if payload:
            entry = payload[0] if isinstance(payload[0], dict) else None
    elif isinstance(payload, dict):
        raw = payload.get(cleaned)
        if isinstance(raw, dict):
            entry = raw
        elif isinstance(raw, list) and raw and isinstance(raw[0], dict):
            entry = raw[0]
        elif payload.get("symbol") == cleaned:
            entry = payload

    if not entry:
        _metrics["symbols_not_found"] += 1
        return {
            "error": "symbol not found on redstone",
            "source": "redstone",
            "symbol": cleaned,
        }

    raw_price = entry.get("value") if "value" in entry else entry.get("price")
    timestamp_raw = entry.get("timestamp") or entry.get("timestampMilliseconds")

    if raw_price is None or timestamp_raw is None:
        _metrics["errors"] += 1
        _record_failure()
        return {
            "error": "redstone payload missing price or timestamp",
            "source": "redstone",
            "symbol": cleaned,
        }

    try:
        price = float(raw_price)
        timestamp_ms = int(timestamp_raw)
    except (TypeError, ValueError):
        _metrics["errors"] += 1
        _record_failure()
        return {
            "error": "redstone payload malformed price or timestamp",
            "source": "redstone",
            "symbol": cleaned,
        }

    if price <= 0:
        _metrics["errors"] += 1
        return {
            "error": "redstone returned non-positive price",
            "source": "redstone",
            "symbol": cleaned,
        }

    # RedStone timestamps are in milliseconds since epoch.
    publish_time = timestamp_ms // 1000 if timestamp_ms > 10**12 else timestamp_ms
    age_s = max(0, int(now) - publish_time)
    stale = age_s > _STALE_AFTER_S

    result: dict[str, Any] = {
        "price": round(price, 6),
        "publish_time": publish_time,
        "age_s": age_s,
        "stale": stale,
        "source": "redstone",
        "symbol": cleaned,
        "provider": REDSTONE_PROVIDER,
    }

    # LRU-ish eviction: drop the oldest entry if full.
    if len(_cache) >= _CACHE_MAX:
        oldest = next(iter(_cache))
        _cache.pop(oldest, None)
    _cache[cleaned] = {"data": result, "ts": now}

    _metrics["successful"] += 1
    _record_success()
    return result


def get_metrics() -> dict[str, Any]:
    """Return a snapshot of the module's counters + circuit-breaker state."""
    return {
        **_metrics,
        "circuit": {
            "state": "open" if _circuit_is_open() else "closed",
            "failures": _cb_failures,
            "max_failures": _CB_MAX_FAILURES,
            "cooldown_s": _CB_COOLDOWN_S,
        },
        "cache_size": len(_cache),
    }


def _reset_for_tests() -> None:
    """Clear cache + circuit breaker + metrics. Test-only helper."""
    global _cb_failures, _cb_open_until
    _cache.clear()
    _cb_failures = 0
    _cb_open_until = 0.0
    for key in list(_metrics.keys()):
        _metrics[key] = 0


logger.info(
    "redstone_oracle initialised — endpoint=%s provider=%s",
    REDSTONE_URL, REDSTONE_PROVIDER,
)
