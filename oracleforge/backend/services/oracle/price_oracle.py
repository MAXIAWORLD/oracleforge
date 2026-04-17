"""MAXIA Oracle — Multi-source live prices (Helius DAS + CoinPaprika + CoinGecko + Yahoo).

Extracted from MAXIA V12/backend/trading/price_oracle.py on 2026-04-14.

Surgeries applied vs the V12 original:
    A. 10 xStocks (Backed Finance tokenized securities) removed from TOKEN_MINTS.
       Equities are now sourced exclusively through pyth_oracle.EQUITY_FEEDS
       (Pyth Hermes direct) + Yahoo Finance / Finnhub as fallback — never
       through tokenized-security mints on Solana.
    B. Hardcoded FALLBACK_PRICES dict (~90 stale March-2026 values) removed.
       When every live source fails, callers receive an explicit error rather
       than a stale/wrong price. refresh_fallback_prices() was removed along
       with the dict. All lazy imports of FALLBACK_PRICES from pyth_oracle
       were updated accordingly.

Strategy (crypto cascade):
    1. Helius DAS getAsset   — parallel batches, ~1s for ~60 tokens
    2. CoinPaprika           — free, generous rate limit
    3. CoinGecko             — multi-chain tokens
    4. (no static fallback — see Surgery B)

Strategy (equity cascade — see get_stock_prices):
    1. Pyth Hermes           — 11 direct feeds via pyth_oracle.EQUITY_FEEDS
    2. Yahoo Finance         — v8 spark + v7 quote fallback
    3. Finnhub               — 60 req/min free tier
    4. (no static fallback)
"""
import asyncio
import logging
import time

import httpx

from core.config import HELIUS_API_KEY, get_rpc_url

logger = logging.getLogger(__name__)


# ── Circuit Breaker ──

class CircuitBreaker:
    """Coupe les appels apres N echecs consecutifs. Retry apres cooldown."""

    def __init__(self, name: str, max_failures: int = 3, cooldown_s: int = 60):
        self.name = name
        self.max_failures = max_failures
        self.cooldown_s = cooldown_s
        self._failures = 0
        self._open_until = 0  # timestamp

    @property
    def is_open(self) -> bool:
        if self._failures < self.max_failures:
            return False
        if time.time() > self._open_until:
            # Half-open: allow one retry
            self._failures = self.max_failures - 1
            return False
        return True

    def record_success(self):
        self._failures = 0

    def record_failure(self):
        self._failures += 1
        if self._failures >= self.max_failures:
            self._open_until = time.time() + self.cooldown_s
            logger.warning(f"[CircuitBreaker] {self.name} OPEN — {self._failures} failures, retry in {self.cooldown_s}s")

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "state": "open" if self.is_open else "closed",
            "failures": self._failures,
            "max": self.max_failures,
        }


_cb_helius = CircuitBreaker("helius", max_failures=3, cooldown_s=60)
_cb_coinpaprika = CircuitBreaker("coinpaprika", max_failures=3, cooldown_s=120)
_cb_coingecko = CircuitBreaker("coingecko", max_failures=3, cooldown_s=120)
_cb_yahoo = CircuitBreaker("yahoo", max_failures=3, cooldown_s=120)

# ── Shared HTTP client — singleton from core.http_client (Phase 4 Step 5) ──
# The old per-module pool has been replaced with the process-wide singleton.
# `close_http_pool` is kept for backwards compat with main.py and simply
# forwards to `core.http_client.close_http_client()`.
from core.http_client import close_http_client as _close_shared_http
from core.http_client import get_http_client as _get_shared_http


async def _get_http() -> httpx.AsyncClient:
    """Return the shared process-wide AsyncClient."""
    return _get_shared_http()


async def close_http_pool() -> None:
    """Close the shared HTTP client (delegates to core.http_client)."""
    await _close_shared_http()

# Token mints pour getAsset
TOKEN_MINTS = {
    # Crypto
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    "RENDER": "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof",
    "HNT": "hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux",
    "TRUMP": "6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN",
    "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
    "W": "85VBFQZC9TZkfaptBWjvUw7YbZjy52A6mjtPGjstQAmQ",
    "ETH": "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",
    "BTC": "3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh",
    "ORCA": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
    # V12: Tokens additionnels
    "JTO": "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL",
    "TNSR": "TNSRxcUxoT9xBG3de7PiJyTDYu7kskLqcpddxnEJAS6",
    "MEW": "MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5",
    "POPCAT": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
    "MOBILE": "mb1eu7TzEc71KxDpsmsKoucSSuuoGLv1drys1oP2jh6",
    "MNDE": "MNDEFzGvMt87ueuHvVU9VcTqsAP5b3fTGPsHuuPA5ey",
    "MSOL": "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",
    "JITOSOL": "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn",
    "BSOL": "bSo13r4TkiE4KumL71LsHTPpL2euBYLFx6h9HP3piy1",
    "DRIFT": "DriFtupJYLTosbwoN8koMbEYSx54aFAVLddWsbksjwg7",
    "KMNO": "KMNo3nJsBXfcpJTVhZcXLW7RmTwTt4GVFE7suUBo9sS",
    "PENGU": "2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv",
    "AI16Z": "HeLp6NuQkmYB4pYWo2zYs22mESHXPQYzXbB8n4V98jwC",
    "FARTCOIN": "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
    "GRASS": "Grass7B4RdKfBCjTKgSqnXkqjwiGvQyFbuSCUJr3XXjs",
    "ZEUS": "ZEUS1aR7aX8DFFJf5QjWj2ftDDdNTroMNGo8YoQm3Gq",
    "NOSOL": "nosXBVoaCTtYdLvKY6Csb4AC8JCdQKKAaWYtx2ZMoo7",
    "SAMO": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
    "STEP": "StepAscQoEioFxxWGnh2sLBDFp9d8rvKz2Yp39iDpyT",
    "BOME": "ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82",
    "SLERF": "7BgBvyjrZX1YKz4oh9mjb8ZScatkkwb8DzFx7LoiVkM3",
    "MPLX": "METAewgxyPbgwsseH8T16a39CQ5VyVxZi9zXiDPY18m",
    "INF": "5oVNBeEEQvYi1cX3ir8Dx5n1P7pdxydbGF2X4TxVusJm",
    "PNUT": "2qEHjDLDLbuBgRYvsxhc5D6uDWAivNFZGan56P1tpump",
    "GOAT": "CzLSujWBLFsSjncfkh59rUFqvafWcY5tzedWJSuypump",
    # V12: Tokens multi-chain (pas de Solana mint, prix via CoinGecko)
    "LINK": "chainlink",
    "UNI": "uniswap",
    "AAVE": "aave",
    "LDO": "lido-dao",
    "VIRTUAL": "virtual-protocol",
    # V12.1: Tokens multi-chain ajoutes (prix via CoinGecko/Pyth)
    "XRP": "ripple", "AVAX": "avalanche-2", "MATIC": "matic-network",
    "TAO": "bittensor", "AKT": "akash-network", "AIOZ": "aioz-network",
    "ARB": "arbitrum", "OP": "optimism", "TIA": "celestia",
    "INJ": "injective-protocol", "STX": "blockstack", "SUI": "sui",
    "APT": "aptos", "SEI": "sei-network", "NEAR": "near",
    "FIL": "filecoin", "AR": "arweave", "ONDO": "ondo-finance",
    "OLAS": "autonolas",
    "FET": "artificial-superintelligence-alliance",
    "PEPE": "pepe",
    "DOGE": "dogecoin",
    "SHIB": "shiba-inu",
    # Surgery A (2026-04-14): 10 xStocks Backed Finance mints removed.
    # Equities are sourced from pyth_oracle.EQUITY_FEEDS (Pyth Hermes direct) +
    # Yahoo/Finnhub only — never from tokenized-security mints on Solana.
}

# Surgery B (2026-04-14): hardcoded FALLBACK_PRICES dict removed.
# When every live source fails, callers receive an explicit error instead of
# a stale March-2026 value. See header docstring for rationale.

_price_cache: dict = {}
_cache_ts: float = 0
_CACHE_TTL = 60  # 1 minute (etait 30s — reduire les appels API)

# Stock prices cache (separate, longer TTL)
_stock_cache: dict = {}
_stock_cache_ts: float = 0
_STOCK_CACHE_TTL = 180  # 3 minutes (etait 2 — Yahoo rate limit)

# Per-symbol cache pour eviter les refetch inutiles
_symbol_cache: dict = {}  # {symbol: {"price": ..., "ts": ..., "source": ...}}
_SYMBOL_CACHE_TTL = 45  # secondes — cache individuel par symbole
_SYMBOL_CACHE_MAX = 200  # Max symbols cached

# Stats compteur (pour monitoring)
_cache_stats = {"hits": 0, "misses": 0}

logger.info("Initialise — Helius DAS API + Yahoo Finance + CoinGecko + fallback (cache 60s)")


async def _fetch_yahoo_stock_prices() -> dict:
    """Fetch real-time stock prices from Yahoo Finance (free, no API key)."""
    if _cb_yahoo.is_open:
        return {}
    stocks = ["AAPL", "TSLA", "NVDA", "GOOGL", "MSFT", "AMZN", "META", "MSTR", "SPY", "QQQ",
               "COIN", "AMD", "NFLX", "PLTR", "PYPL", "INTC", "DIS", "V", "MA", "UBER", "CRM", "SQ", "SHOP"]
    prices = {}
    try:
        # Use dedicated client for Yahoo (avoids shared pool issues)
        # Yahoo v8 limits to 20 symbols per request — batch if needed
        async with httpx.AsyncClient(timeout=15) as client:
            for batch_start in range(0, len(stocks), 20):
                batch = stocks[batch_start:batch_start + 20]
                symbols = ",".join(batch)
                url = f"https://query1.finance.yahoo.com/v8/finance/spark?symbols={symbols}&range=1d&interval=1d"
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    raw = resp.json()
                    # v8 may wrap in {"spark": {}} or return flat dict
                    data = raw
                    if "spark" in raw:
                        # Error case: {"spark": {"result": null, "error": {...}}}
                        if raw["spark"].get("result") is None:
                            continue
                    # Flat dict: {"AAPL": {...}, "TSLA": {...}}
                    for sym, info in data.items():
                        if sym == "spark":
                            continue
                        try:
                            close = info.get("close", [])
                            prev = info.get("previousClose") or info.get("chartPreviousClose", 0)
                            price = close[-1] if close else info.get("regularMarketPrice", 0)
                            if price and price > 0:
                                change_pct = ((price - prev) / prev * 100) if prev else 0
                                prices[sym] = {"price": round(price, 2), "change": round(change_pct, 2), "source": "yahoo"}
                        except Exception as e:
                            logger.debug("Yahoo stock parse error for %s: %s", sym, e)
    except Exception as e:
        logger.error(f"Yahoo Finance error: {e}", exc_info=True)

    # Fallback: try v7 quote API if v8 fails
    if not prices:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                symbols = ",".join(stocks)
                url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbols}"
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    for q in data.get("quoteResponse", {}).get("result", []):
                        sym = q.get("symbol", "")
                        price = q.get("regularMarketPrice", 0)
                        change = q.get("regularMarketChangePercent", 0)
                        if sym and price:
                            prices[sym] = {"price": round(price, 2), "change": round(change, 2), "source": "yahoo_v7"}
        except Exception as e2:
            logger.error(f"Yahoo v7 error: {e2}")

    if prices:
        _cb_yahoo.record_success()
        logger.info(f"Yahoo Finance: {len(prices)} stock prices live")
    else:
        _cb_yahoo.record_failure()
    return prices


async def _fetch_one_helius(client: httpx.AsyncClient, rpc: str, sym: str, mint: str) -> tuple:
    """Fetch un seul token via Helius. Retourne (sym, price_dict) ou (sym, None)."""
    try:
        payload = {"jsonrpc": "2.0", "id": 1, "method": "getAsset", "params": {"id": mint}}
        resp = await client.post(rpc, json=payload)
        data = resp.json()
        result = data.get("result", {})
        if result:
            token_info = result.get("token_info", {})
            price_info = token_info.get("price_info", {})
            price = price_info.get("price_per_token", 0)
            if price and price > 0:
                return (sym, {"price": round(float(price), 6), "source": "helius_das"})
    except Exception as e:
        logger.debug("Helius DAS fetch error for %s: %s", sym, e)
    return (sym, None)


async def _fetch_helius_prices() -> dict:
    """Recupere les prix via Helius DAS API — parallel batches de 10."""
    if not HELIUS_API_KEY:
        return {}  # Pas de cle Helius — silencieux, CoinGecko prend le relais

    if _cb_helius.is_open:
        return {}  # Circuit breaker ouvert — silencieux

    rpc = get_rpc_url()
    if not rpc:
        return {}

    prices = {}
    client = await _get_http()
    # Exclure les tokens sans vrais mints Solana (CoinGecko IDs contiennent des tirets)
    items = [(sym, mint) for sym, mint in TOKEN_MINTS.items() if "-" not in mint and len(mint) > 20]

    # Fetch en batches paralleles de 10
    BATCH_SIZE = 10
    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i:i + BATCH_SIZE]
        tasks = [_fetch_one_helius(client, rpc, sym, mint) for sym, mint in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, tuple) and result[1] is not None:
                prices[result[0]] = result[1]
        # Petit delai entre batches pour pas surcharger
        if i + BATCH_SIZE < len(items):
            await asyncio.sleep(0.1)

    if prices:
        _cb_helius.record_success()
    else:
        _cb_helius.record_failure()

    return prices


async def get_prices(symbols: list | None = None) -> dict:
    """Fetch live prices — Helius DAS + CoinPaprika + CoinGecko.

    Returns a dict of {symbol: {"price": float, "source": str, "mint": str}}.
    Symbols that every source failed on are simply absent from the dict
    (Surgery B: no static fallback). Callers MUST handle missing keys.
    """
    global _price_cache, _cache_ts

    if time.time() - _cache_ts < _CACHE_TTL and _price_cache:
        if symbols:
            return {s: _price_cache[s] for s in symbols if s in _price_cache}
        return _price_cache

    prices = {}

    # Source 1: Helius DAS API
    helius_prices = await _fetch_helius_prices()
    prices.update(helius_prices)

    # Source 2: CoinPaprika (gratuit, pas de cle API, rate limit genereux)
    # Mapping par ID CoinPaprika (pas par symbol — evite les doublons BTC/BONK etc)
    SYM_TO_COINPAPRIKA = {
        "SOL": "sol-solana", "USDC": "usdc-usd-coin", "USDT": "usdt-tether",
        "BONK": "bonk-bonk", "JUP": "jup-jupiter", "RAY": "ray-raydium",
        "WIF": "wif-dogwifhat", "RENDER": "rndr-render-token", "HNT": "hnt-helium",
        "TRUMP": "trump-official-trump", "PYTH": "pyth-pyth-network", "W": "w-wormhole",
        "ETH": "eth-ethereum", "BTC": "btc-bitcoin",
        "ORCA": "orca-orca", "JTO": "jto-jito", "TNSR": "tnsr-tensor",
        "MEW": "mew-cat-in-a-dogs-world", "POPCAT": "popcat-popcat",
        "MOBILE": "mobile-helium-mobile", "MNDE": "mnde-marinade",
        "MSOL": "msol-marinade-staked-sol", "DRIFT": "drift-drift-protocol",
        "KMNO": "kmno-kamino", "PENGU": "pengu-pudgy-penguins", "AI16Z": "ai16z-ai16z",
        "FARTCOIN": "fartcoin-fartcoin", "GRASS": "grass-grass",
        "SAMO": "samo-samoyedcoin",
        "LINK": "link-chainlink", "UNI": "uni-uniswap", "AAVE": "aave-aave",
        "LDO": "ldo-lido-dao", "FET": "fet-fetch-ai",
        "PEPE": "pepe-pepe", "DOGE": "doge-dogecoin", "SHIB": "shib-shiba-inu",
        "XRP": "xrp-xrp", "AVAX": "avax-avalanche", "MATIC": "matic-polygon",
        "TAO": "tao-bittensor", "AKT": "akt-akash-network", "AIOZ": "aioz-aioz-network",
        "ARB": "arb-arbitrum", "OP": "op-optimism", "TIA": "tia-celestia",
        "INJ": "inj-injective", "STX": "stx-stacks", "SUI": "sui-sui",
        "APT": "apt-aptos", "SEI": "sei-sei", "NEAR": "near-near-protocol",
        "FIL": "fil-filecoin", "AR": "ar-arweave", "ONDO": "ondo-ondo-finance",
    }
    stock_syms = {"AAPL","TSLA","NVDA","GOOGL","MSFT","AMZN","META","MSTR","SPY","QQQ",
                  "NFLX","AMD","PLTR","COIN","CRM","INTC","UBER","MARA","AVGO","DIA",
                  "IWM","GLD","ARKK","RIOT","SHOP","SQ","PYPL","ORCL"}
    missing_crypto = [s for s in TOKEN_MINTS if s not in prices and s not in stock_syms]
    if missing_crypto and not _cb_coinpaprika.is_open:
        try:
            client = await _get_http()
            resp = await client.get("https://api.coinpaprika.com/v1/tickers", timeout=12)
            if resp.status_code == 200:
                cp_data = resp.json()
                # Build lookup by CoinPaprika ID
                cp_by_id = {}
                for coin in cp_data:
                    cp_id = (coin.get("id") or "").lower()
                    usd = (coin.get("quotes") or {}).get("USD", {}).get("price")
                    if cp_id and usd is not None:
                        cp_by_id[cp_id] = float(usd)
                # Reverse map: MAXIA symbol -> CoinPaprika ID -> price
                cp_id_to_sym = {v: k for k, v in SYM_TO_COINPAPRIKA.items()}
                cp_count = 0
                for sym in missing_crypto:
                    cp_id = SYM_TO_COINPAPRIKA.get(sym)
                    if cp_id and cp_id in cp_by_id and cp_by_id[cp_id] > 0:
                        prices[sym] = {
                            "price": cp_by_id[cp_id],
                            "source": "coinpaprika",
                            "mint": TOKEN_MINTS.get(sym, ""),
                        }
                        cp_count += 1
                if cp_count:
                    _cb_coinpaprika.record_success()
                    logger.info(f"CoinPaprika: {cp_count} prices fetched")
                missing_crypto = [s for s in TOKEN_MINTS if s not in prices and s not in stock_syms]
            else:
                _cb_coinpaprika.record_failure()
        except Exception as e:
            _cb_coinpaprika.record_failure()
            logger.error(f"CoinPaprika error: {e}")

    # Source 3: CoinGecko (fallback si CoinPaprika n'a pas tout)
    SYM_TO_COINGECKO = {
        "SOL": "solana", "USDC": "usd-coin", "USDT": "tether", "BONK": "bonk",
        "JUP": "jupiter-exchange-solana", "RAY": "raydium", "WIF": "dogwifcoin",
        "RENDER": "render-token", "HNT": "helium", "TRUMP": "official-trump",
        "PYTH": "pyth-network", "W": "wormhole", "ETH": "ethereum", "BTC": "bitcoin",
        "ORCA": "orca", "JTO": "jito-governance-token", "TNSR": "tensor",
        "MEW": "cat-in-a-dogs-world", "POPCAT": "popcat", "MOBILE": "helium-mobile",
        "MNDE": "marinade", "MSOL": "msol", "JITOSOL": "jito-staked-sol",
        "BSOL": "blazestake-staked-sol", "DRIFT": "drift-protocol",
        "KMNO": "kamino", "PENGU": "pudgy-penguins", "AI16Z": "ai16z",
        "FARTCOIN": "fartcoin", "GRASS": "grass", "ZEUS": "zeus-network",
        "NOSOL": "nosana", "SAMO": "samoyedcoin", "STEP": "step-finance",
        "BOME": "book-of-meme", "SLERF": "slerf", "MPLX": "metaplex",
        "INF": "infinity-by-sanctum", "PNUT": "peanut-the-squirrel",
        "GOAT": "goatseus-maximus",
        "LINK": "chainlink", "UNI": "uniswap", "AAVE": "aave",
        "LDO": "lido-dao", "VIRTUAL": "virtual-protocol", "OLAS": "autonolas",
        "FET": "artificial-superintelligence-alliance", "PEPE": "pepe",
        "DOGE": "dogecoin", "SHIB": "shiba-inu",
        "XRP": "ripple", "AVAX": "avalanche-2", "MATIC": "matic-network",
        "TAO": "bittensor", "AKT": "akash-network", "AIOZ": "aioz-network",
        "ARB": "arbitrum", "OP": "optimism", "TIA": "celestia",
        "INJ": "injective-protocol", "STX": "blockstack", "SUI": "sui",
        "APT": "aptos", "SEI": "sei-network", "NEAR": "near",
        "FIL": "filecoin", "AR": "arweave", "ONDO": "ondo-finance",
    }
    if missing_crypto:
        cg_ids = [SYM_TO_COINGECKO[s] for s in missing_crypto if s in SYM_TO_COINGECKO]
        if cg_ids and not _cb_coingecko.is_open:
            try:
                ids_str = ",".join(cg_ids)
                client = await _get_http()
                resp = await client.get(
                    f"https://api.coingecko.com/api/v3/simple/price?ids={ids_str}&vs_currencies=usd"
                )
                if resp.status_code == 200:
                    cg_data = resp.json()
                    cg_id_to_sym = {v: k for k, v in SYM_TO_COINGECKO.items()}
                    for cg_id, price_data in cg_data.items():
                        sym = cg_id_to_sym.get(cg_id, "")
                        if sym and price_data.get("usd"):
                            prices[sym] = {
                                "price": round(float(price_data["usd"]), 6),
                                "source": "coingecko",
                                "mint": TOKEN_MINTS.get(sym, ""),
                            }
                    cg_count = sum(1 for s in missing_crypto if s in prices)
                    if cg_count:
                        _cb_coingecko.record_success()
                        logger.info(f"CoinGecko: {cg_count} additional prices fetched")
                else:
                    _cb_coingecko.record_failure()
            except Exception as e:
                _cb_coingecko.record_failure()
                logger.error(f"CoinGecko error: {e}")

    # Surgery B: no static fallback. Symbols without any live price are
    # simply absent from the returned dict.

    _price_cache = prices
    _cache_ts = time.time()

    live = sum(1 for p in prices.values() if p.get("source") == "helius_das")
    cp = sum(1 for p in prices.values() if p.get("source") == "coinpaprika")
    cg = sum(1 for p in prices.values() if p.get("source") == "coingecko")
    logger.info(f"{live} Helius, {cp} CoinPaprika, {cg} CoinGecko (total {len(prices)})")

    if symbols:
        return {s: prices[s] for s in symbols if s in prices}
    return prices


async def get_price(symbol: str) -> float | None:
    """Return the live price for a symbol, or None if every source failed.

    Uses a per-symbol cache (TTL 45s) before falling through to get_prices().
    Signature changed from V12 (`-> float`, returned 0 on failure) to return
    an explicit None so callers cannot accidentally mistake "no data" for
    "price is zero" (Surgery B).
    """
    now = time.time()
    cached = _symbol_cache.get(symbol)
    if cached and now - cached.get("ts", 0) < _SYMBOL_CACHE_TTL:
        _cache_stats["hits"] += 1
        return cached.get("price")
    _cache_stats["misses"] += 1
    prices = await get_prices([symbol])
    result = prices.get(symbol)
    if not result:
        return None
    price = result.get("price")
    if not price or price <= 0:
        return None
    # Cap cache size — evict oldest entry if full
    if len(_symbol_cache) >= _SYMBOL_CACHE_MAX:
        oldest_sym = min(_symbol_cache, key=lambda s: _symbol_cache[s].get("ts", 0))
        del _symbol_cache[oldest_sym]
    _symbol_cache[symbol] = {"price": price, "ts": now, "source": result.get("source", "unknown")}
    return price


def get_cache_stats() -> dict:
    """Retourne les stats du cache prix + circuit breakers."""
    return {
        "global_cache_age_s": round(time.time() - _cache_ts, 1) if _cache_ts else None,
        "global_cache_size": len(_price_cache),
        "symbol_cache_size": len(_symbol_cache),
        "stock_cache_age_s": round(time.time() - _stock_cache_ts, 1) if _stock_cache_ts else None,
        "hits": _cache_stats["hits"],
        "misses": _cache_stats["misses"],
        "hit_rate": f"{_cache_stats['hits'] / max(1, _cache_stats['hits'] + _cache_stats['misses']):.0%}",
        "circuit_breakers": {
            "helius": _cb_helius.get_status(),
            "coingecko": _cb_coingecko.get_status(),
            "yahoo": _cb_yahoo.get_status(),
        },
    }


async def get_crypto_prices() -> dict:
    """Return live crypto prices only (no equities, no tokenized stocks).

    Surgery A already removed the 10 xStock mints from TOKEN_MINTS, so the
    `stock_syms` filter is now just defense-in-depth against future regressions.
    Symbols without a live price are simply absent from the returned dict
    (Surgery B — no static fallback).
    """
    stock_syms = {"AAPL", "TSLA", "NVDA", "GOOGL", "MSFT", "AMZN", "META", "MSTR",
                  "SPY", "QQQ", "NFLX", "AMD", "PLTR", "COIN", "CRM", "INTC",
                  "UBER", "MARA", "AVGO", "DIA", "IWM", "GLD", "ARKK", "RIOT",
                  "SHOP", "SQ", "PYPL", "ORCL"}
    cryptos = [s for s in TOKEN_MINTS if s not in stock_syms]
    return await get_prices(cryptos)


async def get_stock_prices() -> dict:
    """Recupere les prix des actions — Pyth -> Finnhub -> Yahoo -> fallback.

    Utilise pyth_oracle.get_stock_price() pour les stocks avec feed Pyth (11 stocks),
    puis Yahoo Finance pour les stocks restants sans feed Pyth.
    """
    global _stock_cache, _stock_cache_ts
    stocks = ["AAPL", "TSLA", "NVDA", "GOOGL", "MSFT", "AMZN", "META", "MSTR", "SPY", "QQQ",
              "NFLX", "AMD", "PLTR", "COIN", "CRM", "INTC", "UBER", "MARA",
              "AVGO", "DIA", "IWM", "GLD", "ARKK", "RIOT", "SHOP", "SQ", "PYPL", "ORCL"]

    # Use cache if fresh
    if time.time() - _stock_cache_ts < _STOCK_CACHE_TTL and _stock_cache:
        return _stock_cache

    result = {}

    # ── Source 1: Pyth Hermes batch (11 stocks with Pyth feed IDs — real-time) ──
    # NOTE: We call get_pyth_price() directly instead of get_stock_price() to avoid
    # circular calls (get_stock_price -> price_oracle.get_stock_prices -> get_stock_price).
    try:
        from .pyth_oracle import EQUITY_FEEDS, get_pyth_price
        pyth_tasks = []
        pyth_syms = []
        for sym in stocks:
            lookup = "GOOG" if sym == "GOOGL" else sym
            if lookup in EQUITY_FEEDS:
                pyth_tasks.append(get_pyth_price(EQUITY_FEEDS[lookup]))
                pyth_syms.append(sym)

        if pyth_tasks:
            pyth_results = await asyncio.gather(*pyth_tasks, return_exceptions=True)
            for sym, res in zip(pyth_syms, pyth_results):
                if isinstance(res, Exception):
                    continue
                if isinstance(res, dict) and "error" not in res and res.get("price", 0) > 0:
                    # Skip stale prices — let Yahoo/Finnhub handle them
                    if res.get("stale"):
                        logger.warning(f"STALE Pyth stock price for {sym} (age={res.get('age_s')}s), skipping")
                        continue
                    price = res["price"]
                    change = 0
                    prev = _stock_cache.get(sym, {})
                    if prev and prev.get("price", 0) > 0 and prev.get("source") != "fallback":
                        change = prev.get("change", 0)  # Keep previous change until Yahoo refreshes it
                    result[sym] = {"price": round(price, 2), "change": change, "source": "pyth"}
        pyth_count = sum(1 for v in result.values() if v.get("source") == "pyth")
        if pyth_count:
            logger.info(f"Pyth stock prices: {pyth_count}/{len(pyth_syms)} live")
    except Exception as e:
        logger.error(f"Pyth oracle stock fetch error: {e}")

    # ── Source 2: Yahoo Finance for all stocks (best for change % data) ──
    missing = [s for s in stocks if s not in result]
    if missing or not result:
        yahoo_prices = await _fetch_yahoo_stock_prices()
        logger.info(f"Yahoo returned {len(yahoo_prices)} stock prices, CB state: {_cb_yahoo.get_status()}")
        for sym in stocks:
            if sym in yahoo_prices:
                if sym not in result:
                    # Yahoo is the only source for this stock
                    result[sym] = yahoo_prices[sym]
                else:
                    # Stock already has a live price from Pyth — enrich with change % from Yahoo
                    result[sym]["change"] = yahoo_prices[sym].get("change", 0)

    # ── Source 3: Finnhub for any still-missing stocks ──
    still_missing = [s for s in stocks if s not in result]
    if still_missing:
        try:
            from .price_cascade import get_stock_price_finnhub
            finnhub_tasks = [get_stock_price_finnhub(sym) for sym in still_missing]
            finnhub_results = await asyncio.gather(*finnhub_tasks, return_exceptions=True)
            for sym, res in zip(still_missing, finnhub_results):
                if isinstance(res, Exception):
                    continue
                if isinstance(res, dict) and "error" not in res and res.get("price", 0) > 0:
                    result[sym] = {"price": round(res["price"], 2), "change": 0, "source": "finnhub"}
        except Exception as e:
            logger.error(f"Finnhub stock fetch error: {e}")

    # Surgery B: no static fallback — stocks that every source failed on are
    # simply absent from the returned dict.
    logger.info(f"Stock prices: {len(result)}/{len(stocks)} live")

    _stock_cache = result
    _stock_cache_ts = time.time()
    return result
