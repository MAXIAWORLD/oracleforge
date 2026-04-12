"""OracleForge — Price source implementations.

Each source fetches price data independently. The PriceEngine cross-verifies.
Sources: CoinGecko, Pyth, Chainlink, Finnhub, Yahoo.
"""

from __future__ import annotations

import logging
import time

import httpx

from core.config import Settings

logger = logging.getLogger(__name__)


class PriceResult:
    """Result from a single source fetch."""

    __slots__ = ("price", "source", "latency_ms", "error")

    def __init__(
        self,
        price: float = 0.0,
        source: str = "",
        latency_ms: int = 0,
        error: str | None = None,
    ) -> None:
        self.price = price
        self.source = source
        self.latency_ms = latency_ms
        self.error = error

    @property
    def ok(self) -> bool:
        return self.error is None and self.price > 0


# ── CoinGecko ────────────────────────────────────────────────────

# CoinGecko symbol mapping (common crypto)
_CG_IDS: dict[str, str] = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin",
    "XRP": "ripple", "ADA": "cardano", "DOGE": "dogecoin", "DOT": "polkadot",
    "AVAX": "avalanche-2", "MATIC": "matic-network", "LINK": "chainlink",
    "UNI": "uniswap", "ATOM": "cosmos", "LTC": "litecoin", "NEAR": "near",
    "APT": "aptos", "SUI": "sui", "ARB": "arbitrum", "OP": "optimism",
    "USDT": "tether", "USDC": "usd-coin",
}


async def fetch_coingecko(
    symbol: str, http: httpx.AsyncClient
) -> PriceResult:
    """Fetch price from CoinGecko free API."""
    cg_id = _CG_IDS.get(symbol.upper())
    if not cg_id:
        return PriceResult(source="coingecko", error=f"Unknown symbol: {symbol}")
    t0 = time.monotonic()
    try:
        resp = await http.get(
            f"https://api.coingecko.com/api/v3/simple/price",
            params={"ids": cg_id, "vs_currencies": "usd"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        price = data.get(cg_id, {}).get("usd", 0.0)
        ms = int((time.monotonic() - t0) * 1000)
        if price > 0:
            return PriceResult(price=price, source="coingecko", latency_ms=ms)
        return PriceResult(source="coingecko", latency_ms=ms, error="No price data")
    except Exception as e:
        ms = int((time.monotonic() - t0) * 1000)
        return PriceResult(source="coingecko", latency_ms=ms, error=str(e))


# ── Pyth Network ────────────────────────────────────────────────

# Pyth feed IDs (Hermes API)
_PYTH_FEEDS: dict[str, str] = {
    "BTC": "0xe62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
    "ETH": "0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
    "SOL": "0xef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4cfac8c280b56d",
    "BNB": "0x2f95862b045670cd22bee3114c39763a4a08beeb663b145d283c31d7d1101c4f",
    "XRP": "0xec5d399846a9209f3fe5881d70aae9268c94339ff9817e8d18ff19fa05eea1c8",
    "DOGE": "0xdcef50dd0a4cd2dcc17e45df1676dcb336a11a61c69df7a0299b0150c672d25c",
    "AVAX": "0x93da3352f9f1d105fdfe4971cfa80e9dd777bfc5d0f683ebb6e1571f5d38a28b",
    "LINK": "0x8ac0c70fff57e9aefdf5edf44b51d62c2d433653cbb2cf5cc06bb115af04d221",
}


async def fetch_pyth(
    symbol: str, http: httpx.AsyncClient, hermes_url: str
) -> PriceResult:
    """Fetch price from Pyth Hermes API."""
    feed_id = _PYTH_FEEDS.get(symbol.upper())
    if not feed_id:
        return PriceResult(source="pyth", error=f"No Pyth feed for: {symbol}")
    t0 = time.monotonic()
    try:
        resp = await http.get(
            f"{hermes_url}/v2/updates/price/latest",
            params={"ids[]": feed_id},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        parsed = data.get("parsed", [])
        if parsed:
            p = parsed[0].get("price", {})
            raw_price = int(p.get("price", "0"))
            expo = int(p.get("expo", 0))
            price = raw_price * (10 ** expo)
            ms = int((time.monotonic() - t0) * 1000)
            if price > 0:
                return PriceResult(price=price, source="pyth", latency_ms=ms)
        ms = int((time.monotonic() - t0) * 1000)
        return PriceResult(source="pyth", latency_ms=ms, error="No price data")
    except Exception as e:
        ms = int((time.monotonic() - t0) * 1000)
        return PriceResult(source="pyth", latency_ms=ms, error=str(e))


# ── Chainlink (on-chain via RPC) ────────────────────────────────

_CHAINLINK_FEEDS: dict[str, dict] = {
    "ETH": {
        "address": "0x71041dddad3595F9CEd3DcCFBe3D1F4b0a16Bb70",
        "decimals": 8,
        "description": "ETH / USD",
    },
    "BTC": {
        "address": "0x64c911996D3c6aC71f9b455B1E8E7266BcbD848F",
        "decimals": 8,
        "description": "BTC / USD",
    },
}


async def fetch_chainlink(
    symbol: str, http: httpx.AsyncClient, rpc_url: str
) -> PriceResult:
    """Fetch price from Chainlink via Base RPC eth_call."""
    feed = _CHAINLINK_FEEDS.get(symbol.upper())
    if not feed:
        return PriceResult(source="chainlink", error=f"No Chainlink feed for: {symbol}")
    t0 = time.monotonic()
    try:
        # latestRoundData() selector = 0xfeaf968c
        resp = await http.post(
            rpc_url,
            json={
                "jsonrpc": "2.0", "id": 1, "method": "eth_call",
                "params": [{"to": feed["address"], "data": "0xfeaf968c"}, "latest"],
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        result = resp.json().get("result", "0x")
        if len(result) < 66:
            raise ValueError("Invalid response length")
        # Decode answer (2nd word, 32 bytes at offset 32)
        answer_hex = result[66:130]
        answer = int(answer_hex, 16)
        # Handle signed int (if top bit set)
        if answer > 2**255:
            answer -= 2**256
        price = answer / (10 ** feed["decimals"])
        ms = int((time.monotonic() - t0) * 1000)
        if price > 0:
            return PriceResult(price=price, source="chainlink", latency_ms=ms)
        return PriceResult(source="chainlink", latency_ms=ms, error="Zero price")
    except Exception as e:
        ms = int((time.monotonic() - t0) * 1000)
        return PriceResult(source="chainlink", latency_ms=ms, error=str(e))
