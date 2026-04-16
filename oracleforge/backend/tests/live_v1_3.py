"""V1.3 live harness — NOT run by CI.

Hits the real RedStone REST endpoint. Intended to be run manually on a
machine with outbound HTTPS to https://api.redstone.finance.

Run from backend/ with the venv active:

    PYTHONPATH=. python tests/live_v1_3.py

Exits non-zero on any failure and prints a 1-line summary per feed.

(A Pyth native Solana probe was part of this harness in an earlier draft
but was removed when the feature was dropped from V1.3 — see
docs/v1.3_redstone_eliza_pyth_solana.md for the rescheduling note.)
"""
from __future__ import annotations

import asyncio
import os
import sys


# Required env setup for core.config at import.
os.environ.setdefault("ENV", "dev")


async def _main() -> int:
    from services.oracle import redstone_oracle

    failures = 0

    print("=== RedStone live ===")
    for sym in ("BTC", "ETH", "SOL", "AAPL"):
        result = await redstone_oracle.get_redstone_price(sym)
        if "error" in result:
            print(f"  [FAIL] {sym}: {result['error']}")
            failures += 1
            continue
        price = result["price"]
        age = result["age_s"]
        stale = result["stale"]
        print(f"  [OK]   {sym}: ${price} (age {age}s, stale={stale})")

    print()
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
