"""Phase 1 live smoke test — hits every source with BTC, ETH, SOL.

Run from backend/ with the venv activated:
    python -m tests.live_phase1

This is NOT a pytest test — it is a one-shot live validation that the 3
extracted oracle modules reach their upstream sources end-to-end. It is
gated behind manual invocation because it hits real network APIs and
should not run in CI.

Pass criteria (Phase 1 checkpoint):
    - Pyth Hermes returns a live price for BTC, ETH, SOL within sanity bounds
    - Chainlink Base returns a live price for ETH, BTC, USDC
    - price_oracle.get_prices() returns at least one non-empty source
      (Helius DAS if key set; otherwise CoinPaprika or CoinGecko)
    - No import errors, no unhandled exceptions
"""
from __future__ import annotations

import asyncio
import sys
import time
from typing import Any

# Sanity bounds for 2026 — reject clearly-wrong values from broken sources.
# These are deliberately wide to avoid false failures in volatile markets.
SANITY_BOUNDS: dict[str, tuple[float, float]] = {
    "BTC": (10_000.0, 500_000.0),
    "ETH": (500.0, 20_000.0),
    "SOL": (20.0, 1_000.0),
    "USDC": (0.95, 1.05),
}

GREEN = "\x1b[32m"
RED = "\x1b[31m"
YELLOW = "\x1b[33m"
CYAN = "\x1b[36m"
RESET = "\x1b[0m"


def _check_sanity(symbol: str, price: float) -> tuple[bool, str]:
    lo, hi = SANITY_BOUNDS.get(symbol, (0.0, float("inf")))
    if price <= 0:
        return False, f"price <= 0"
    if price < lo or price > hi:
        return False, f"out of sanity bounds [{lo}, {hi}]"
    return True, ""


def _log(status: str, label: str, detail: str = "") -> None:
    colors = {"PASS": GREEN, "FAIL": RED, "SKIP": YELLOW, "INFO": CYAN}
    c = colors.get(status, "")
    print(f"  {c}[{status:4}]{RESET} {label}{(' — ' + detail) if detail else ''}")


async def test_pyth() -> int:
    """Exercise pyth_oracle.get_pyth_price for BTC, ETH, SOL."""
    print(f"\n{CYAN}== Pyth Hermes =={RESET}")
    from services.oracle.pyth_oracle import CRYPTO_FEEDS, get_pyth_price

    failures = 0
    for sym in ("BTC", "ETH", "SOL"):
        feed_id = CRYPTO_FEEDS.get(sym)
        if not feed_id:
            _log("SKIP", sym, "no feed id")
            continue
        t0 = time.time()
        result: dict[str, Any] = await get_pyth_price(feed_id)
        elapsed_ms = round((time.time() - t0) * 1000, 1)
        if "error" in result:
            _log("FAIL", sym, f"{result['error']} ({elapsed_ms}ms)")
            failures += 1
            continue
        price = result.get("price", 0.0)
        ok, reason = _check_sanity(sym, price)
        if not ok:
            _log("FAIL", sym, f"price={price} — {reason}")
            failures += 1
            continue
        conf_pct = result.get("confidence_pct", 0)
        age_s = result.get("age_s", 0)
        _log("PASS", sym, f"${price:,.2f} conf={conf_pct}% age={age_s}s lat={elapsed_ms}ms")
    return failures


async def test_chainlink() -> int:
    """Exercise chainlink_oracle.get_chainlink_price for ETH, BTC, USDC."""
    print(f"\n{CYAN}== Chainlink (Base mainnet) =={RESET}")
    from services.oracle.chainlink_oracle import get_chainlink_price

    failures = 0
    for sym in ("ETH", "BTC", "USDC"):
        t0 = time.time()
        result: dict[str, Any] = await get_chainlink_price(sym)
        elapsed_ms = round((time.time() - t0) * 1000, 1)
        if "error" in result:
            _log("FAIL", sym, f"{result['error']} ({elapsed_ms}ms)")
            failures += 1
            continue
        price = result.get("price", 0.0)
        ok, reason = _check_sanity(sym, price)
        if not ok:
            _log("FAIL", sym, f"price={price} — {reason}")
            failures += 1
            continue
        age_s = result.get("age_s", 0)
        round_id = result.get("round_id", "?")
        _log(
            "PASS",
            sym,
            f"${price:,.2f} age={age_s}s round={round_id} lat={elapsed_ms}ms",
        )
    return failures


async def test_price_oracle_batch() -> int:
    """Exercise price_oracle.get_prices() — hits Helius, CoinPaprika, CoinGecko."""
    print(f"\n{CYAN}== price_oracle.get_prices() =={RESET}")
    from services.oracle.price_oracle import close_http_pool, get_prices

    t0 = time.time()
    try:
        prices = await get_prices(["BTC", "ETH", "SOL", "USDC"])
    finally:
        await close_http_pool()
    elapsed_ms = round((time.time() - t0) * 1000, 1)

    failures = 0
    sources_seen: set[str] = set()
    for sym in ("BTC", "ETH", "SOL", "USDC"):
        entry = prices.get(sym)
        if not entry:
            _log("FAIL", sym, "no entry returned")
            failures += 1
            continue
        price = entry.get("price", 0.0)
        source = entry.get("source", "?")
        sources_seen.add(source)
        ok, reason = _check_sanity(sym, price)
        if not ok:
            _log("FAIL", sym, f"source={source} price={price} — {reason}")
            failures += 1
            continue
        _log("PASS", sym, f"${price:,.4f} source={source}")

    _log("INFO", "sources_seen", ", ".join(sorted(sources_seen)) or "(none)")
    _log("INFO", "total_latency", f"{elapsed_ms}ms")
    return failures


async def test_pyth_batch() -> int:
    """Exercise pyth_oracle.get_batch_prices() — single HTTP call for 3 feeds."""
    print(f"\n{CYAN}== Pyth batch (BTC+ETH+SOL in one call) =={RESET}")
    from services.oracle.pyth_oracle import get_batch_prices

    t0 = time.time()
    results = await get_batch_prices(["BTC", "ETH", "SOL"])
    elapsed_ms = round((time.time() - t0) * 1000, 1)

    failures = 0
    for sym in ("BTC", "ETH", "SOL"):
        entry = results.get(sym)
        if not entry:
            _log("FAIL", sym, "no entry in batch")
            failures += 1
            continue
        price = entry.get("price", 0.0)
        ok, reason = _check_sanity(sym, price)
        if not ok:
            _log("FAIL", sym, f"price={price} — {reason}")
            failures += 1
            continue
        _log("PASS", sym, f"${price:,.2f} source={entry.get('source')}")
    _log("INFO", "batch_latency", f"{elapsed_ms}ms for 3 feeds")
    return failures


async def main() -> int:
    print(f"{CYAN}=== MAXIA Oracle — Phase 1 live smoke test ==={RESET}")
    print(f"Started at {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    failures = 0
    failures += await test_pyth()
    failures += await test_chainlink()
    failures += await test_pyth_batch()
    failures += await test_price_oracle_batch()

    print()
    if failures == 0:
        print(f"{GREEN}=== ALL CHECKS PASSED ==={RESET}")
        return 0
    print(f"{RED}=== {failures} CHECK(S) FAILED ==={RESET}")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
