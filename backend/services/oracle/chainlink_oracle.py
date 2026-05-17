"""MAXIA Oracle — Chainlink on-chain price reader (Base + Ethereum + Arbitrum).

Reads Chainlink Aggregator V3 contracts directly on EVM chains via eth_call.
No centralized API — pure on-chain read (RPC -> smart contract -> price).

V1.0 (Phase 1) origin: extracted from MAXIA V12 as a Base-only reader.
V1.1: extended to a three-chain reader (Base, Ethereum, Arbitrum) with a
per-chain RPC fallback pool. The module-level surface stays backward
compatible: `get_chainlink_price(symbol)` defaults to `chain="base"` and
`CHAINLINK_FEEDS_BASE` is preserved as an alias of the Base dict.

Usage:
    # Default path (Base mainnet, unchanged from V1.0):
    price = await get_chainlink_price("ETH")

    # V1.1 multi-chain:
    eth_on_ethereum = await get_chainlink_price("ETH", chain="ethereum")
    btc_on_arbitrum = await get_chainlink_price("BTC", chain="arbitrum")

Feed addresses are copied from https://docs.chain.link/data-feeds/price-feeds
and verified at runtime against the on-chain `description()` result. A feed
that fails the description check is dropped silently (with a WARNING log)
rather than raising — an unreachable feed must never block the startup path.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Final

import httpx

from core.config import CHAIN_RPC_URLS
from core.errors import safe_error
from core.http_client import get_http_client

logger = logging.getLogger("chainlink")

# ── Supported chains ────────────────────────────────────────────────────────

SUPPORTED_CHAINS: Final[tuple[str, ...]] = ("base", "ethereum", "arbitrum")
DEFAULT_CHAIN: Final[str] = "base"


# ── Chainlink Aggregator V3 addresses per chain ─────────────────────────────
# Source: https://docs.chain.link/data-feeds/price-feeds/addresses
# All feeds listed here are USD-denominated crypto majors, forex pairs, or
# wrapped-asset parity feeds. Exotic feeds (synthetix, LP tokens, reserves,
# risk parameters) are intentionally excluded from V1 — they complicate
# the "is this the price my contract sees?" mental model.
#
# Every feed must respond to description() with a string that contains the
# declared pair (see verify_feeds_at_startup). Mismatches are dropped.

CHAINLINK_FEEDS: Final[dict[str, dict[str, dict[str, Any]]]] = {
    "base": {
        "ETH": {"address": "0x71041dddad3595F9CEd3DcCFBe3D1F4b0a16Bb70", "pair": "ETH / USD", "decimals": 8},
        "BTC": {"address": "0xCCADC697c55bbB68dc5bCdf8d3CBe83CdD4E071E", "pair": "WBTC / USD", "decimals": 8},
        "USDC": {"address": "0x7e860098F58bBFC8648a4311b374B1D669a2bc6B", "pair": "USDC / USD", "decimals": 8},
        "DAI": {"address": "0x591e79239a7d679378eC8c847e5038150364C78F", "pair": "DAI / USD", "decimals": 8},
        "LINK": {"address": "0x17CAb8FE31E32f08326e5E27412894e49B0f9D65", "pair": "LINK / USD", "decimals": 8},
        "CBETH": {"address": "0xd7818272B9e248357d13057AAb0B417aF31E817d", "pair": "cbETH / USD", "decimals": 8},
        "CBBTC": {"address": "0x07DA0E54543a844a80ABE69c8A12F22B3aA59f9D", "pair": "cbBTC / USD", "decimals": 8},
    },
    "ethereum": {
        "ETH": {"address": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419", "pair": "ETH / USD", "decimals": 8},
        "BTC": {"address": "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c", "pair": "BTC / USD", "decimals": 8},
        "USDC": {"address": "0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6", "pair": "USDC / USD", "decimals": 8},
        "USDT": {"address": "0x3E7d1eAB13ad0104d2750B8863b489D65364e32D", "pair": "USDT / USD", "decimals": 8},
        "DAI": {"address": "0xAed0c38402a5d19df6E4c03F4E2DceD6e29c1ee9", "pair": "DAI / USD", "decimals": 8},
        "LINK": {"address": "0x2c1d072e956AFFC0D435Cb7AC38EF18d24d9127c", "pair": "LINK / USD", "decimals": 8},
        "AAVE": {"address": "0x547a514d5e3769680Ce22B2361c10Ea13619e8a9", "pair": "AAVE / USD", "decimals": 8},
        "UNI": {"address": "0x553303d460EE0afB37EdFf9bE42922D8FF63220e", "pair": "UNI / USD", "decimals": 8},
        "MKR": {"address": "0xec1D1B3b0443256cc3860e24a46F108e699484Aa", "pair": "MKR / USD", "decimals": 8},
        "CRV": {"address": "0xCd627aA160A6fA45Eb793D19Ef54f5062F20f33f", "pair": "CRV / USD", "decimals": 8},
        "COMP": {"address": "0xdbd020CAeF83eFd542f4De03e3cF0C28A4428bd5", "pair": "COMP / USD", "decimals": 8},
        "ARB": {"address": "0x31697852a68433DbCc2Ff612c516d69E3D9bd08F", "pair": "ARB / USD", "decimals": 8},
        "SOL": {"address": "0x4ffC43a60e009B551865A93d232E33Fce9f01507", "pair": "SOL / USD", "decimals": 8},
        "AVAX": {"address": "0xFF3EEb22B5E3dE6e705b44749C2559d704923FD7", "pair": "AVAX / USD", "decimals": 8},
        "BNB": {"address": "0x14e613AC84a31f709eadbdF89C6CC390fDc9540A", "pair": "BNB / USD", "decimals": 8},
        "MATIC": {"address": "0x7bAC85A8a13A4BcD8abb3eB7d6b4d632c5a57676", "pair": "MATIC / USD", "decimals": 8},
        "XRP": {"address": "0xCed2660c6Dd1Ffd856A5A82C67f3482d88C50b12", "pair": "XRP / USD", "decimals": 8},
        "ADA": {"address": "0xAE48c91dF1fE419994FFDa27da09D5aC69c30f55", "pair": "ADA / USD", "decimals": 8},
        "LTC": {"address": "0x6AF09DF7563C363B5763b9102712EbeD3b9e859B", "pair": "LTC / USD", "decimals": 8},
        "DOGE": {"address": "0x2465CefD3b488BE410b941b1d4b2767088e2A028", "pair": "DOGE / USD", "decimals": 8},
        "EUR": {"address": "0xb49f677943BC038e9857d61E7d053CaA2C1734C1", "pair": "EUR / USD", "decimals": 8},
        "GBP": {"address": "0x5c0Ab2d9b5a7ed9f470386e82BB36A3613cDd4b5", "pair": "GBP / USD", "decimals": 8},
        "JPY": {"address": "0xBcE206caE7f0ec07b545EddE332A47C2F75bbeb3", "pair": "JPY / USD", "decimals": 8},
    },
    "arbitrum": {
        "ETH": {"address": "0x639Fe6ab55C921f74e7fac1ee960C0B6293ba612", "pair": "ETH / USD", "decimals": 8},
        "BTC": {"address": "0x6ce185860a4963106506C203335A2910413708e9", "pair": "BTC / USD", "decimals": 8},
        "USDC": {"address": "0x50834F3163758fcC1Df9973b6e91f0F0F0434aD3", "pair": "USDC / USD", "decimals": 8},
        "USDT": {"address": "0x3f3f5dF88dC9F13eac63DF89EC16ef6e7E25DdE7", "pair": "USDT / USD", "decimals": 8},
        "DAI": {"address": "0xc5C8E77B397E531B8EC06BFb0048328B30E9eCfB", "pair": "DAI / USD", "decimals": 8},
        "LINK": {"address": "0x86E53CF1B870786351Da77A57575e79CB55812CB", "pair": "LINK / USD", "decimals": 8},
        "ARB": {"address": "0xb2A824043730FE05F3DA2efaFa1CBbe83fa548D6", "pair": "ARB / USD", "decimals": 8},
        "AAVE": {"address": "0xaD1d5344AaDE45F43E596773Bcc4c423EAbdD034", "pair": "AAVE / USD", "decimals": 8},
        "CRV": {"address": "0xaebDA2c976cfd1eE1977Eac079B4382acb849325", "pair": "CRV / USD", "decimals": 8},
        "COMP": {"address": "0xe7C53FFd03Eb6ceF7d208bC4C13446c76d1E5884", "pair": "COMP / USD", "decimals": 8},
        "SOL": {"address": "0x24ceA4b8ce57cdA5058b924B9B9987992450590c", "pair": "SOL / USD", "decimals": 8},
        "MATIC": {"address": "0x52099D4523531f678Dfc568a7B1e5038aadcE1d6", "pair": "MATIC / USD", "decimals": 8},
        "AVAX": {"address": "0x8bf61728eeDCE2F32c456454d87B5d6eD6150208", "pair": "AVAX / USD", "decimals": 8},
        "BNB": {"address": "0x6970460aabF80C5BE983C6b74e5D06dEDCA95D4A", "pair": "BNB / USD", "decimals": 8},
        "XRP": {"address": "0xB4AD57B52aB9141de9926a3e0C8dc6264c2ef205", "pair": "XRP / USD", "decimals": 8},
        "ADA": {"address": "0xD9f615A9b820225edbA2d821c4A696a0924051c6", "pair": "ADA / USD", "decimals": 8},
        "DOGE": {"address": "0x9A7FB1b3950837a8D9b40517626E11D4127C098C", "pair": "DOGE / USD", "decimals": 8},
    },
}

# Backward-compatibility alias for code that pre-dates the multi-chain refactor.
# Reads should prefer `has_feed(symbol, "base")` and `feeds_for("base")`.
CHAINLINK_FEEDS_BASE: Final[dict[str, dict[str, Any]]] = CHAINLINK_FEEDS["base"]

# ── Function selectors (keccak256 first 4 bytes) ────────────────────────────

# latestRoundData() -> (uint80,int256,uint256,uint256,uint80)
_LATEST_ROUND_DATA: Final[str] = "0xfeaf968c"
# description() -> string
_DESCRIPTION: Final[str] = "0x7284e416"
# decimals() -> uint8
_DECIMALS: Final[str] = "0x313ce567"

# ── Cache (keyed by (chain, symbol)) ────────────────────────────────────────

_cl_cache: dict[tuple[str, str], dict[str, Any]] = {}
_CL_CACHE_TTL: Final[int] = 30

# ── Metrics ─────────────────────────────────────────────────────────────────

_cl_metrics: dict[str, Any] = {
    "total_requests": 0,
    "successful": 0,
    "errors": 0,
    "feeds_verified": 0,
    "rpc_fallbacks": 0,
}


# ── Public helpers ──────────────────────────────────────────────────────────


def has_feed(symbol: str, chain: str = DEFAULT_CHAIN) -> bool:
    """Return True iff a Chainlink feed is configured for `symbol` on `chain`."""
    return chain in CHAINLINK_FEEDS and symbol.upper() in CHAINLINK_FEEDS[chain]


def feeds_for(chain: str = DEFAULT_CHAIN) -> dict[str, dict[str, Any]]:
    """Return the feed dict for `chain`, or empty dict if chain is unknown."""
    return CHAINLINK_FEEDS.get(chain, {})


def symbols_for(chain: str = DEFAULT_CHAIN) -> list[str]:
    """Return the sorted list of symbols supported on `chain`."""
    return sorted(CHAINLINK_FEEDS.get(chain, {}).keys())


def all_supported_symbols() -> dict[str, list[str]]:
    """Return {chain: [symbols]} across every supported chain."""
    return {chain: symbols_for(chain) for chain in SUPPORTED_CHAINS}


# ── Internal RPC plumbing ───────────────────────────────────────────────────


async def _get_http() -> httpx.AsyncClient:
    return get_http_client()


async def _try_single_rpc(rpc_url: str, to: str, data: str) -> str:
    """Execute one eth_call against a single RPC endpoint. Raises on failure."""
    client = await _get_http()
    resp = await client.post(
        rpc_url,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_call",
            "params": [{"to": to, "data": data}, "latest"],
        },
    )
    if resp.status_code != 200:
        raise RuntimeError(f"RPC HTTP {resp.status_code}")
    result = resp.json()
    if "error" in result:
        raise RuntimeError(f"RPC error: {result['error'].get('message', '')[:100]}")
    return result.get("result", "0x")


async def _eth_call(to: str, data: str, chain: str) -> str:
    """Execute eth_call on `chain` with RPC fallback. Tries every configured
    RPC in order and returns the first success. Raises only if all fail."""
    rpcs = CHAIN_RPC_URLS.get(chain)
    if not rpcs:
        raise ValueError(f"unsupported chain: {chain}")

    last_exc: Exception | None = None
    for i, rpc_url in enumerate(rpcs):
        try:
            return await _try_single_rpc(rpc_url, to, data)
        except Exception as exc:
            last_exc = exc
            if i > 0:
                _cl_metrics["rpc_fallbacks"] += 1
            continue
    raise RuntimeError(f"all {chain} RPCs failed: {last_exc!r}")


def _decode_latest_round_data(hex_data: str) -> dict[str, int]:
    """Decode latestRoundData() ABI response.
    Returns roundId, answer, startedAt, updatedAt, answeredInRound."""
    clean = hex_data[2:] if hex_data.startswith("0x") else hex_data
    if len(clean) < 320:
        raise ValueError(f"Invalid response length: {len(clean)}")

    round_id = int(clean[0:64], 16)
    answer = int(clean[64:128], 16)
    if answer >= 2**255:
        answer -= 2**256
    started_at = int(clean[128:192], 16)
    updated_at = int(clean[192:256], 16)
    answered_in_round = int(clean[256:320], 16)

    return {
        "round_id": round_id,
        "answer": answer,
        "started_at": started_at,
        "updated_at": updated_at,
        "answered_in_round": answered_in_round,
    }


# ── Public reader ───────────────────────────────────────────────────────────


async def get_chainlink_price(
    symbol: str, chain: str = DEFAULT_CHAIN
) -> dict[str, Any]:
    """Read a Chainlink aggregator price on `chain` for `symbol` (on-chain).

    Returns a dict with keys:
        price, decimals, round_id, updated_at, age_s, stale, source,
        contract, chain.

    On failure the returned dict contains an `"error"` key instead of a
    price — it never raises. The `source` field is stable per chain
    (`chainlink_base`, `chainlink_ethereum`, `chainlink_arbitrum`) so the
    multi-source aggregator in `services/oracle/multi_source.py` can
    label them correctly.
    """
    _cl_metrics["total_requests"] += 1
    sym = symbol.upper()
    source_label = f"chainlink_{chain}"

    if chain not in CHAINLINK_FEEDS:
        return {
            "error": f"unsupported chain: {chain}",
            "chain": chain,
            "source": source_label,
        }

    feed = CHAINLINK_FEEDS[chain].get(sym)
    if not feed:
        return {
            "error": f"No Chainlink feed for {sym} on {chain}",
            "chain": chain,
            "source": source_label,
        }

    now = time.time()
    cache_key = (chain, sym)
    cached = _cl_cache.get(cache_key)
    if cached and now - cached["ts"] < _CL_CACHE_TTL:
        return cached["data"]

    try:
        hex_result = await _eth_call(feed["address"], _LATEST_ROUND_DATA, chain)
        decoded = _decode_latest_round_data(hex_result)

        decimals = feed["decimals"]
        price = decoded["answer"] / (10 ** decimals)
        age_s = int(now) - decoded["updated_at"]
        # Chainlink feeds update on heartbeat (~1h) or deviation threshold.
        is_stale = age_s > 3600

        result: dict[str, Any] = {
            "price": round(price, 6),
            "decimals": decimals,
            "round_id": decoded["round_id"],
            "updated_at": decoded["updated_at"],
            "age_s": age_s,
            "stale": is_stale,
            "source": source_label,
            "contract": feed["address"],
            "chain": chain,
        }

        _cl_cache[cache_key] = {"data": result, "ts": now}
        _cl_metrics["successful"] += 1
        return result

    except Exception as e:
        _cl_metrics["errors"] += 1
        return {
            "error": safe_error(
                f"Chainlink eth_call failed for {sym} on {chain}", e, logger
            ),
            "chain": chain,
            "source": source_label,
        }


async def verify_price_chainlink(
    symbol: str,
    expected_price: float,
    max_deviation_pct: float = 2.0,
    max_age_s: int = 3600,
    chain: str = DEFAULT_CHAIN,
) -> dict[str, Any]:
    """Cross-verify `expected_price` against the on-chain Chainlink feed.

    Returns:
        {"verified": bool, "chainlink_price": float, "deviation_pct": float,
         "age_s": int, "chain": str, "source": str}
    """
    source_label = f"chainlink_{chain}"
    result = await get_chainlink_price(symbol, chain=chain)
    if "error" in result:
        return {
            "verified": False,
            "error": result["error"],
            "chain": chain,
            "source": source_label,
        }

    cl_price = result["price"]
    age_s = result["age_s"]

    if age_s > max_age_s:
        return {
            "verified": False,
            "error": f"Chainlink price too old: {age_s}s",
            "chainlink_price": cl_price,
            "age_s": age_s,
            "chain": chain,
            "source": source_label,
        }

    if expected_price > 0 and cl_price > 0:
        deviation = abs(cl_price - expected_price) / expected_price * 100
    else:
        deviation = 0.0

    verified = deviation <= max_deviation_pct
    return {
        "verified": verified,
        "chainlink_price": cl_price,
        "expected_price": expected_price,
        "deviation_pct": round(deviation, 2),
        "age_s": age_s,
        "chain": chain,
        "source": source_label,
    }


async def verify_feeds_at_startup(
    chain: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Verify Chainlink feed addresses by checking description() on-chain.

    If `chain` is None, iterate every supported chain. Returns
        {"<chain>": {"<symbol>": {"verified": bool, "description": str, "address": str, "error"?: str}}}

    Feeds that fail the check are NOT removed from CHAINLINK_FEEDS — the
    caller decides what to do (log, drop, alert). The module exposes this
    as a diagnostic helper rather than a boot-time side effect so that
    startup never blocks on a transient RPC outage.
    """
    chains = (chain,) if chain is not None else SUPPORTED_CHAINS
    out: dict[str, dict[str, Any]] = {}
    for c in chains:
        out[c] = {}
        for sym, feed in CHAINLINK_FEEDS.get(c, {}).items():
            try:
                hex_result = await _eth_call(feed["address"], _DESCRIPTION, c)
                clean = hex_result[2:] if hex_result.startswith("0x") else hex_result
                if len(clean) >= 192:
                    str_len = int(clean[64:128], 16)
                    desc_bytes = bytes.fromhex(clean[128 : 128 + str_len * 2])
                    description = desc_bytes.decode("utf-8", errors="replace").strip()
                    expected = feed["pair"].lower().replace(" ", "")
                    actual = description.lower().replace(" ", "")
                    matched = expected in actual
                    out[c][sym] = {
                        "verified": matched,
                        "description": description,
                        "address": feed["address"],
                    }
                    if matched:
                        _cl_metrics["feeds_verified"] += 1
                        logger.info(
                            "[Chainlink %s] %s feed verified: %s", c, sym, description
                        )
                    else:
                        logger.warning(
                            "[Chainlink %s] %s mismatch: expected '%s', got '%s'",
                            c,
                            sym,
                            feed["pair"],
                            description,
                        )
                else:
                    out[c][sym] = {
                        "verified": False,
                        "error": "description() returned empty",
                        "address": feed["address"],
                    }
            except Exception as e:
                out[c][sym] = {
                    "verified": False,
                    "error": safe_error(
                        f"Chainlink feed verification failed for {sym} on {c}", e, logger
                    ),
                    "address": feed["address"],
                }
    return out


def get_metrics() -> dict[str, Any]:
    return {
        **_cl_metrics,
        "chains_supported": list(SUPPORTED_CHAINS),
        "feeds_available": all_supported_symbols(),
    }
