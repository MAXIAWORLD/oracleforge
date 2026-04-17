"""GET /health — liveness probe with degradation detection.

Reports DB connectivity and circuit-breaker state without hitting any
upstream API (that would turn a free endpoint into a DoS vector).
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter

from core.config import ENV
from core.disclaimer import wrap_with_disclaimer

router = APIRouter(tags=["health"])
logger = logging.getLogger("maxia_oracle.health")

_START_TS = time.time()


def _check_db() -> bool:
    try:
        from core.db import get_db
        get_db().execute("SELECT 1").fetchone()
        return True
    except Exception:
        logger.warning("DB health check failed", exc_info=True)
        return False


def _collect_breaker_states() -> dict[str, str]:
    states: dict[str, str] = {}
    try:
        from services.oracle import price_oracle
        for cb in (
            price_oracle._cb_helius,
            price_oracle._cb_coinpaprika,
            price_oracle._cb_coingecko,
            price_oracle._cb_yahoo,
        ):
            states[cb.name] = cb.get_status()["state"]
    except Exception:
        logger.warning("Failed to collect price_oracle breakers", exc_info=True)
    try:
        from services.oracle import redstone_oracle
        states["redstone"] = redstone_oracle.get_metrics()["circuit"]["state"]
    except Exception:
        logger.warning("Failed to collect redstone breaker", exc_info=True)
    try:
        from services.oracle import pyth_solana_oracle
        states["pyth_solana"] = pyth_solana_oracle.get_metrics()["circuit"]["state"]
    except Exception:
        logger.warning("Failed to collect pyth_solana breaker", exc_info=True)
    try:
        from services.oracle import uniswap_v3_oracle
        circuit = uniswap_v3_oracle.get_metrics()["circuit"]
        for chain, info in circuit.items():
            states[f"uniswap_v3_{chain}"] = info["state"]
    except Exception:
        logger.warning("Failed to collect uniswap_v3 breakers", exc_info=True)
    return states


@router.get("/api/status")
async def status() -> dict:
    """Public service status — per-source health without auth."""
    breakers = _collect_breaker_states()
    sources = {}
    for name, state in breakers.items():
        sources[name] = "down" if state == "open" else "available"
    open_list = [n for n, s in breakers.items() if s == "open"]
    db_ok = _check_db()
    return {
        "status": "degraded" if open_list or not db_ok else "ok",
        "uptime_s": round(time.time() - _START_TS, 1),
        "sources": sources,
        "open_breakers": open_list,
        "db": "ok" if db_ok else "error",
    }


@router.get("/health")
async def health() -> dict:
    """Liveness probe with DB and circuit-breaker degradation reporting."""
    db_ok = _check_db()
    breakers = _collect_breaker_states()
    open_breakers = [n for n, s in breakers.items() if s == "open"]
    degraded = bool(open_breakers) or not db_ok

    return wrap_with_disclaimer(
        {
            "status": "degraded" if degraded else "ok",
            "env": ENV,
            "uptime_s": round(time.time() - _START_TS, 1),
            "db": "ok" if db_ok else "error",
            "circuit_breakers": breakers,
            "open_breakers": open_breakers,
        }
    )
