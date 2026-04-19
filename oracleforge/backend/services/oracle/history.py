"""V1.8 — Historical price sampling and query service.

Background sampler: runs every HISTORY_SAMPLE_INTERVAL_S seconds (default
300 = 5 min), fetches batch prices via price_cascade.get_batch_prices()
(single Pyth Hermes call for ~79 symbols), and inserts snapshots into the
price_snapshots table. Purges data older than HISTORY_RETENTION_DAYS daily.

Query: returns downsampled history for a symbol+range+interval combo.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Final

from core.config import HISTORY_RETENTION_DAYS, HISTORY_SAMPLE_INTERVAL_S
from core.db import (
    get_db,
    insert_price_snapshots,
    oldest_snapshot_ts,
    purge_old_snapshots,
    query_price_history,
)

logger = logging.getLogger("maxia_oracle.history")

VALID_RANGES: Final[dict[str, int]] = {
    "24h": 86400,
    "7d": 7 * 86400,
    "30d": 30 * 86400,
}

VALID_INTERVALS: Final[dict[str, int]] = {
    "5m": 300,
    "1h": 3600,
    "1d": 86400,
}

DEFAULT_INTERVAL: Final[dict[str, str]] = {
    "24h": "5m",
    "7d": "1h",
    "30d": "1d",
}

# Whitelist of valid range+interval combinations. Excluded combos:
#   24h+1d  → bucket size = total range → at most 1 point, useless
#   30d+5m  → up to 8 640 points → too expensive to serve
VALID_COMBINATIONS: Final[frozenset[tuple[str, str]]] = frozenset({
    ("24h", "5m"),
    ("24h", "1h"),
    ("7d", "5m"),
    ("7d", "1h"),
    ("7d", "1d"),
    ("30d", "1h"),
    ("30d", "1d"),
})

_sampler_task: asyncio.Task[None] | None = None
_PURGE_EVERY_CYCLES: Final[int] = 288  # ~24h at 5min interval


async def _sample_once() -> tuple[int, dict]:
    """Fetch batch prices and insert snapshots. Returns (count_inserted, results)."""
    from services.oracle import price_cascade
    from services.oracle.pyth_oracle import ALL_FEEDS

    symbols = sorted(ALL_FEEDS.keys())
    if not symbols:
        return 0, {}

    results = await price_cascade.get_batch_prices(symbols)
    rows: list[tuple[str, float, int]] = []
    for sym, data in results.items():
        price = data.get("price") if isinstance(data, dict) else None
        if price and price > 0:
            rows.append((sym, float(price), 1))

    if rows:
        db = get_db()
        insert_price_snapshots(db, rows)
    return len(rows), results


async def _sampler_loop() -> None:
    """Background loop: sample prices every HISTORY_SAMPLE_INTERVAL_S."""
    cycle = 0
    while True:
        try:
            count, results = await _sample_once()
            if count > 0:
                logger.debug("Sampled %d price snapshots", count)

            if results:
                from services.oracle.alerts import check_and_fire_alerts
                await check_and_fire_alerts(results)

            cycle += 1
            if cycle >= _PURGE_EVERY_CYCLES:
                cycle = 0
                db = get_db()
                deleted = purge_old_snapshots(db, HISTORY_RETENTION_DAYS)
                if deleted > 0:
                    logger.info("Purged %d old snapshots (>%dd)", deleted, HISTORY_RETENTION_DAYS)
        except Exception:
            logger.warning("History sampler cycle failed", exc_info=True)

        await asyncio.sleep(HISTORY_SAMPLE_INTERVAL_S)


def start_sampler() -> None:
    """Start the background sampler task. Idempotent."""
    global _sampler_task
    if _sampler_task is not None and not _sampler_task.done():
        return
    _sampler_task = asyncio.create_task(_sampler_loop())
    logger.info(
        "History sampler started (interval=%ds, retention=%dd)",
        HISTORY_SAMPLE_INTERVAL_S,
        HISTORY_RETENTION_DAYS,
    )


def stop_sampler() -> None:
    """Cancel the background sampler task."""
    global _sampler_task
    if _sampler_task is not None and not _sampler_task.done():
        _sampler_task.cancel()
        _sampler_task = None
        logger.info("History sampler stopped")


def get_history(
    symbol: str,
    range_key: str = "24h",
    interval_key: str | None = None,
) -> dict[str, Any] | None:
    """Query historical prices for a symbol.

    Returns None if range/interval are invalid.
    """
    if range_key not in VALID_RANGES:
        return None
    if interval_key is None:
        interval_key = DEFAULT_INTERVAL[range_key]
    if interval_key not in VALID_INTERVALS:
        return None
    if (range_key, interval_key) not in VALID_COMBINATIONS:
        return None

    since = int(time.time()) - VALID_RANGES[range_key]
    bucket_s = VALID_INTERVALS[interval_key]
    db = get_db()
    datapoints = query_price_history(db, symbol, since, bucket_s)
    oldest = oldest_snapshot_ts(db, symbol)

    count = len(datapoints)
    note: str | None = (
        "No historical data yet. The sampler collects prices every 5 minutes "
        "and builds up history over time. Try again after the first sampling cycle."
        if count == 0
        else None
    )
    return {
        "symbol": symbol,
        "range": range_key,
        "interval": interval_key,
        "datapoints": datapoints,
        "count": count,
        "oldest_available": oldest,
        "note": note,
    }
