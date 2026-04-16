"""V1.4 pre-compute — build the PYTH_SOLANA_FEEDS dict for hardcoding.

Queries Hermes for the feed catalog, derives PDA shard-0 for a curated list
of majors, batch-fetches the accounts, and prints a Python dict snippet
ready to paste into `services/oracle/pyth_solana_oracle.py`.

Only keeps feeds that:
  - exist on-chain (shard 0 sponsored)
  - return account length == 134 bytes
  - have verification_level = Full
  - have age_s < 120 at sampling time

Run: python scratch_precompute_pdas.py > /tmp/pdas.py
"""
from __future__ import annotations

import asyncio
import base64
import struct
import time
from typing import Final

import httpx
from solders.pubkey import Pubkey

PUSH_ORACLE_PROGRAM_ID: Final[Pubkey] = Pubkey.from_string(
    "pythWSnswVUd12oZpeFP8e9CVaEqJg25g1Vtc2biRsT"
)

HERMES_CATALOG_URL: Final[str] = "https://hermes.pyth.network/v2/price_feeds"

SOLANA_RPCS: tuple[str, ...] = (
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
)

# Curated symbols — majors only. Anything exotic/stocks can be added later by
# rerunning this script once the shard-0 sponsorship widens.
WANTED_SYMBOLS: Final[tuple[str, ...]] = (
    # Crypto majors
    "BTC", "ETH", "SOL", "USDT", "USDC", "BNB", "XRP", "ADA", "DOGE", "AVAX",
    "LINK", "MATIC", "POL", "DOT", "LTC", "BCH", "TRX", "NEAR", "ATOM", "ICP",
    # Layer 2 / DeFi
    "ARB", "OP", "APT", "SUI", "TIA", "INJ", "FIL", "UNI", "AAVE", "MKR",
    # Meme/trend (but liquid)
    "PEPE", "WIF", "BONK", "SHIB",
    # Solana eco
    "PYTH", "JTO", "JUP", "RAY",
    # Stablecoins secondary
    "DAI",
    # Stocks majors (try — likely not sponsored shard-0)
    "AAPL", "TSLA", "MSFT", "NVDA", "AMZN", "META", "GOOG",
    # Forex majors
    "EUR", "GBP", "JPY",
)


def derive_pda(shard_id: int, feed_id_hex: str) -> str:
    """Derive the price feed account PDA for shard_id + feed_id."""
    feed_id = bytes.fromhex(feed_id_hex)
    shard = shard_id.to_bytes(2, "little")
    pda, _ = Pubkey.find_program_address([shard, feed_id], PUSH_ORACLE_PROGRAM_ID)
    return str(pda)


def decode_full_or_none(data: bytes) -> dict | None:
    """Decode a PriceUpdateV2 account. Returns None unless verification=Full."""
    if len(data) < 133:
        return None
    vl_variant = data[40]
    if vl_variant != 1:  # not Full
        return None
    off = 41
    feed_id_echo = data[off:off + 32].hex()
    off += 32
    price = struct.unpack("<q", data[off:off + 8])[0]; off += 8
    conf = struct.unpack("<Q", data[off:off + 8])[0]; off += 8
    exponent = struct.unpack("<i", data[off:off + 4])[0]; off += 4
    publish_time = struct.unpack("<q", data[off:off + 8])[0]
    return {
        "feed_id_echo": feed_id_echo,
        "price_scaled": price * (10 ** exponent),
        "publish_time": publish_time,
    }


async def fetch_hermes_catalog(client: httpx.AsyncClient) -> dict[str, str]:
    """Return {SYMBOL: feed_id_hex} for every entry in the Hermes catalog.

    Hermes returns entries like:
      {"id": "<hex>", "attributes": {"base": "BTC", "quote_currency": "USD",
                                     "asset_type": "crypto", ...}}
    We select crypto/equity/fx feeds priced in USD and key by `base`.
    """
    r = await client.get(HERMES_CATALOG_URL, timeout=20.0)
    r.raise_for_status()
    rows = r.json()
    by_symbol: dict[str, str] = {}
    for row in rows:
        attrs = row.get("attributes", {})
        base = (attrs.get("base") or "").strip().upper()
        quote = (attrs.get("quote_currency") or "").strip().upper()
        if not base or quote != "USD":
            continue
        # Prefer the first one we see (Hermes lists the canonical pair first).
        if base not in by_symbol:
            by_symbol[base] = row["id"]
    return by_symbol


async def fetch_account(client: httpx.AsyncClient, rpc: str, pubkey: str) -> bytes | None:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAccountInfo",
        "params": [pubkey, {"encoding": "base64", "commitment": "confirmed"}],
    }
    try:
        r = await client.post(rpc, json=body, timeout=10.0)
        r.raise_for_status()
        data = r.json().get("result", {})
    except Exception:
        return None
    if data is None:
        return None
    value = data.get("value")
    if value is None:
        return None
    d = value.get("data")
    if not (isinstance(d, list) and len(d) == 2 and d[1] == "base64"):
        return None
    return base64.b64decode(d[0])


async def probe_symbol(client: httpx.AsyncClient, symbol: str, feed_hex: str) -> dict | None:
    pda = derive_pda(0, feed_hex)
    data = None
    for rpc in SOLANA_RPCS:
        data = await fetch_account(client, rpc, pda)
        if data is not None:
            break
    if data is None:
        return None
    decoded = decode_full_or_none(data)
    if decoded is None:
        return None
    if decoded["feed_id_echo"] != feed_hex:
        return None
    age_s = int(time.time()) - decoded["publish_time"]
    if age_s > 120:
        return None
    return {
        "symbol": symbol,
        "feed_id": feed_hex,
        "price_account": pda,
        "price": decoded["price_scaled"],
        "age_s": age_s,
    }


async def main() -> None:
    async with httpx.AsyncClient() as client:
        print("# Fetching Hermes catalog...", flush=True)
        catalog = await fetch_hermes_catalog(client)
        print(f"# Hermes reports {len(catalog)} USD-quoted feeds", flush=True)

        print("# Probing WANTED_SYMBOLS on Solana mainnet shard 0...", flush=True)
        tasks = []
        for sym in WANTED_SYMBOLS:
            feed = catalog.get(sym)
            if not feed:
                print(f"#   {sym:6s} -- not in Hermes catalog", flush=True)
                continue
            tasks.append(probe_symbol(client, sym, feed))

        results = await asyncio.gather(*tasks)

        live: list[dict] = [r for r in results if r is not None]
        live.sort(key=lambda r: r["symbol"])
        dead = [
            sym for sym in WANTED_SYMBOLS
            if sym in catalog and not any(r and r["symbol"] == sym for r in results)
        ]

        print(f"\n# Live feeds: {len(live)} / {len([s for s in WANTED_SYMBOLS if s in catalog])}")
        print(f"# Dead (not sponsored shard 0 or stale): {dead}")
        print()
        print("# === Paste into services/oracle/pyth_solana_oracle.py ===")
        print("PYTH_SOLANA_FEEDS: Final[dict[str, dict[str, str]]] = {")
        for r in live:
            print(f'    "{r["symbol"]}": {{')
            print(f'        "feed_id": "{r["feed_id"]}",')
            print(f'        "price_account": "{r["price_account"]}",')
            print(f"    }},  # price={r['price']:.4f} age={r['age_s']}s")
        print("}")


if __name__ == "__main__":
    asyncio.run(main())
