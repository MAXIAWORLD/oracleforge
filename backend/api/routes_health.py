"""GET /health — unauthenticated liveness probe.

Returns a JSON status object wrapped with the mandatory disclaimer. Does NOT
exercise upstream oracles on every hit (that would turn a free health-check
endpoint into a DoS vector against Pyth/Chainlink/CoinPaprika). Use
/api/sources for a deeper health view that consumes rate-limit budget.
"""
from __future__ import annotations

import time

from fastapi import APIRouter

from core.config import ENV
from core.disclaimer import wrap_with_disclaimer

router = APIRouter(tags=["health"])

_START_TS = time.time()


@router.get("/health")
async def health() -> dict:
    """Lightweight liveness probe — always responds OK when the process is up."""
    return wrap_with_disclaimer(
        {
            "status": "ok",
            "env": ENV,
            "uptime_s": round(time.time() - _START_TS, 1),
        }
    )
