"""V1.9 — SSE price streaming via Pyth batch polling.

Yields Server-Sent Events with price updates every STREAM_POLL_INTERVAL_S
seconds. Uses price_cascade.get_batch_prices() under the hood (same single
Pyth Hermes call that powers the history sampler).

The stream auto-closes after STREAM_TIMEOUT_S (default 1h).
Does NOT consume daily API quota.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncIterator

from core.config import STREAM_POLL_INTERVAL_S, STREAM_TIMEOUT_S

logger = logging.getLogger("maxia_oracle.stream")


async def price_event_generator(
    symbols: list[str],
) -> AsyncIterator[str]:
    """Async generator yielding SSE-formatted price events."""
    from services.oracle import price_cascade

    start = time.monotonic()

    while True:
        elapsed = time.monotonic() - start
        if elapsed >= STREAM_TIMEOUT_S:
            yield _sse_event({"type": "timeout", "message": "stream timeout reached"})
            return

        try:
            results = await price_cascade.get_batch_prices(symbols)
            event_data = {
                "type": "prices",
                "timestamp": int(time.time()),
                "prices": {
                    sym: {
                        "price": d.get("price"),
                        "source": d.get("source"),
                        "confidence": d.get("confidence"),
                    }
                    for sym, d in results.items()
                    if isinstance(d, dict) and d.get("price")
                },
            }
            yield _sse_event(event_data)
        except Exception:
            logger.warning("Stream poll failed", exc_info=True)
            yield _sse_event({"type": "error", "message": "poll failed, retrying"})

        await asyncio.sleep(STREAM_POLL_INTERVAL_S)


def _sse_event(data: dict) -> str:
    """Format a dict as a Server-Sent Event string."""
    return f"data: {json.dumps(data, separators=(',', ':'))}\n\n"
