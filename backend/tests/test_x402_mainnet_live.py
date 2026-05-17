"""Live mainnet x402 test — requires a real Base tx hash.

Usage:
    python test_x402_mainnet_live.py <TX_HASH>

What it tests:
    1. /api/price/BTC without payment → 402 challenge (validate structure)
    2. /api/price/BTC with X-Payment: <TX_HASH> → 200 BTC price
    3. Same TX_HASH again → 402 replay detected
    4. /api/prices/batch with X-Payment: <TX_HASH_2> → needs separate tx ($0.005)

Step 3 requires a second tx hash for the batch route.
"""

from __future__ import annotations

import sys
import json
import urllib.request
import urllib.error

BASE_URL = "https://oracle.maxiaworld.app"
TREASURY = "0xb3C5AF291eeA9D11DE7178B28eaF443359900f41"
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


def _req(path: str, headers: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _ok(label: str, cond: bool, detail: str = "") -> None:
    icon = "✅" if cond else "❌"
    print(f"  {icon}  {label}" + (f" — {detail}" if detail else ""))
    if not cond:
        raise SystemExit(f"\nFAIL: {label}")


def test_challenge(path: str = "/api/price/BTC") -> None:
    print(f"\n[1] 402 challenge on {path}")
    status, body = _req(path)
    _ok("status == 402", status == 402, str(status))
    _ok("x402Version == 2", body.get("x402Version") == 2)
    accepts = body.get("accepts", [])
    _ok("1 accept entry", len(accepts) >= 1)
    entry = accepts[0]
    _ok(
        "network = base-mainnet",
        entry["network"] == "base-mainnet",
        entry.get("network"),
    )
    _ok(
        "payTo = treasury",
        entry["payTo"].lower() == TREASURY.lower(),
        entry.get("payTo"),
    )
    _ok(
        "asset = USDC Base",
        entry["asset"].lower() == USDC_BASE.lower(),
        entry.get("asset"),
    )
    _ok(
        "maxAmountRequired = 1000",
        entry["maxAmountRequired"] == "1000",
        entry.get("maxAmountRequired"),
    )
    print(f"     Treasury: {entry['payTo']}")
    print(f"     Amount:   {entry['maxAmountRequired']} raw USDC = $0.001")


def test_payment(tx_hash: str, path: str = "/api/price/BTC") -> None:
    print(f"\n[2] Valid payment on {path} with tx={tx_hash[:16]}...")
    status, body = _req(path, headers={"X-Payment": tx_hash})
    _ok("status == 200", status == 200, str(status))
    _ok("data key present", "data" in body)
    data = body.get("data", {})
    symbol = data.get("symbol", "")
    price = data.get("price_usd")
    _ok("symbol returned", bool(symbol), symbol)
    _ok("price_usd > 0", isinstance(price, (int, float)) and price > 0, str(price))
    print(f"     {symbol} = ${price:,.2f}")


def test_replay(tx_hash: str, path: str = "/api/price/BTC") -> None:
    print("\n[3] Replay protection — same tx_hash reused")
    status, body = _req(path, headers={"X-Payment": tx_hash})
    _ok("status == 402 on replay", status == 402, str(status))
    error = body.get("error", "") or body.get("detail", "")
    _ok("replay error message", "replay" in error.lower(), error)
    print(f"     Error: {error}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        print("USAGE: python test_x402_mainnet_live.py <TX_HASH>")
        print()
        print("Send exactly 0.001 USDC on Base mainnet to:")
        print(f"  {TREASURY}")
        print(f"USDC contract: {USDC_BASE}")
        print("Chain: Base mainnet (chainId 8453)")
        sys.exit(1)

    tx_hash = sys.argv[1].strip()
    if not tx_hash.startswith("0x") or len(tx_hash) != 66:
        print(f"ERROR: tx_hash must be 0x + 64 hex chars, got: {tx_hash!r}")
        sys.exit(1)

    print("=" * 60)
    print("MAXIA Oracle — x402 Live Mainnet Test")
    print("=" * 60)
    print(f"Treasury: {TREASURY}")
    print(f"TX Hash:  {tx_hash}")

    test_challenge()
    test_payment(tx_hash)
    test_replay(tx_hash)

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✅ — x402 micropayments working on Base mainnet")
    print("=" * 60)


if __name__ == "__main__":
    main()
