"""Vérifie les feed IDs Pyth Hermes pour les nouveaux tokens."""
import asyncio
import httpx

SYMBOLS = [
    # Tier 1
    "BNB", "ADA", "DOGE", "DOT", "LTC", "TRX",
    # Tier 2
    "NEAR", "SUI", "APT", "INJ", "SEI",
    # Tier 3 AI
    "RENDER", "FET", "TAO", "OCEAN",
    # Tier 4
    "DAI", "WSTETH",
]


async def main():
    async with httpx.AsyncClient(timeout=15) as client:
        for sym in SYMBOLS:
            r = await client.get(
                "https://hermes.pyth.network/v2/price_feeds",
                params={"query": sym, "asset_type": "crypto"},
            )
            data = r.json()
            usd = [
                f for f in data
                if f.get("attributes", {}).get("quote_currency", "") == "USD"
                and f.get("attributes", {}).get("base", "").upper() == sym.upper()
            ]
            if usd:
                f = usd[0]
                print(f"{sym}: {f['id']}")
            elif data:
                f = data[0]
                base = f.get("attributes", {}).get("base", "?")
                print(f"{sym} (first match, base={base}): {f['id']}")
            else:
                print(f"{sym}: NOT FOUND")


asyncio.run(main())
