"""MAXIA Oracle -- Uniswap v3 TWAP on-chain reader (V1.5).

Reads the time-weighted average price (TWAP) of curated Uniswap v3 pools
on Base and Ethereum mainnet via the `observe(uint32[])` method (direct
eth_call, no transaction, no dep). Returns the TWAP computed from the
slope of `tickCumulatives` over a caller-chosen window.

## Why Uniswap v3 TWAP?

A TWAP derived from a Uniswap v3 pool on a DEX is a price signal that
is independently verifiable on-chain and robust to short-term
manipulation: the attacker has to keep the pool at a skewed price for
the entire TWAP window to move the metric. With a 30-minute window on a
high-liquidity pool (WETH/USDC 0.05% at $150M+ TVL), manipulating it
enough to move the price by 1% requires millions of dollars of tokens
standing on the wrong side of the book for the full window.

That makes TWAP complementary to Pyth (Hermes off-chain), Chainlink
(heartbeat + 0.5% deviation) and RedStone (centralized REST): another
independent anchor in the multi-source stack.

## Pool selection

Only pools with a proven, liquid deployment on each chain are shipped.
See `UNISWAP_V3_POOLS` below; the list was hand-audited live on
2026-04-16 via `scratch_audit_v15.py` (which is not checked in -- it's
a one-shot validation script). Adding a new pool requires:

  1. A publicly verifiable Uniswap v3 deployment with TVL > $10M.
  2. Manual verification that `observe([window, 0])` returns a TWAP
     within 1% of other sources (Pyth / Chainlink / Hermes).
  3. An entry in `UNISWAP_V3_POOLS` and a doc note in
     `docs/v1.5_uniswap_twap.md`.

## Math

The pool exposes `observe([window, 0]) -> (int56[] tickCumulatives, ...)`.
The time-weighted average tick over the window is:

    avg_tick = (tickCumulatives[1] - tickCumulatives[0]) // window

Per Uniswap v3 spec, the raw price of token1 in terms of token0 is:

    raw_price = 1.0001 ** tick

To convert to a human price of 1 token0 in token1 units:

    human_price = raw_price * 10 ** (decimals0 - decimals1)

When the asset we want to price is token1 (for pools where stablecoin
comes first alphabetically, like Ethereum WETH/USDC), we invert.

## Safety rules

- `observe()` reverts if the pool observation cardinality is smaller
  than the requested window. We catch the revert and return an error
  rather than silently falling back to a stale spot price.
- `window` must be within `[60, 86400]` seconds (1 min to 24 h).
- Cache TTL is 60 s; a TWAP over 1800 s changes slowly, so 1-minute
  freshness is plenty. RPC fallback through `CHAIN_RPC_URLS` pool.
- Circuit breaker: 5 consecutive failures open for 60 s, matching the
  Chainlink reader pattern.
- Never raises; every error path returns
  `{"error": str, "source": "uniswap_v3", ...}`.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Final

import httpx

from core.config import CHAIN_RPC_URLS
from core.errors import safe_error
from core.http_client import get_http_client

logger = logging.getLogger("uniswap_v3_oracle")


# ── Constants ───────────────────────────────────────────────────────────────

SUPPORTED_CHAINS: Final[tuple[str, ...]] = ("base", "ethereum")
DEFAULT_CHAIN: Final[str] = "ethereum"

DEFAULT_WINDOW_S: Final[int] = 1800   # 30 minutes
MIN_WINDOW_S: Final[int] = 60
MAX_WINDOW_S: Final[int] = 86400

OBSERVE_SELECTOR: Final[str] = "0x883bdbfd"  # observe(uint32[])

RPC_TIMEOUT_S: Final[float] = 10.0
_CACHE_TTL_S: Final[int] = 60
_CACHE_MAX: Final[int] = 100

_CB_MAX_FAILURES: Final[int] = 5
_CB_COOLDOWN_S: Final[int] = 60

_SYMBOL_MAX_LEN: Final[int] = 10


# ── Pool catalog (hand-audited 2026-04-16) ──────────────────────────────────
#
# Each entry is a (symbol, chain) pair pointing at the canonical Uniswap v3
# pool for that asset on that chain. Fields:
#   pool          -- 0x-prefixed EVM address
#   token0 / dec  -- token at address-slot 0 (lexicographically lowest)
#   token1 / dec  -- token at address-slot 1
#   base_is_token0-- True iff the asset we want to PRICE (e.g. WETH for "ETH")
#                    is token0. Flips the inversion at compute time.
#   fee_bps       -- fee tier * 10000 (5 = 0.05%, 30 = 0.30%, 100 = 1%)
#   tvl_note      -- short rationale for picking this pool (for audit trail)
#
# V1.5 ships a minimal 3-pool catalog -- both ETH variants + WBTC. The
# scratch audit confirmed these return live TWAPs consistent with the
# rest of the MAXIA Oracle multi-source stack to <0.1%. Extending the
# catalog is a V1.x cleanup, not a V1.5 deliverable.

UNISWAP_V3_POOLS: Final[dict[str, dict[str, dict[str, Any]]]] = {
    "ETH": {
        "ethereum": {
            "pool": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
            "token0": "USDC", "token0_dec": 6,
            "token1": "WETH", "token1_dec": 18,
            "base_is_token0": False,
            "fee_bps": 5,
            "tvl_note": "Uniswap v3 canonical USDC/WETH 0.05%, $150M+ TVL.",
        },
        "base": {
            "pool": "0xd0b53D9277642d899DF5C87A3966A349A798F224",
            "token0": "WETH", "token0_dec": 18,
            "token1": "USDC", "token1_dec": 6,
            "base_is_token0": True,
            "fee_bps": 5,
            "tvl_note": "Uniswap v3 WETH/USDC 0.05% on Base, highest Base TVL.",
        },
    },
    "BTC": {
        "ethereum": {
            "pool": "0x99ac8cA7087fA4A2A1FB6357269965A2014ABc35",
            "token0": "WBTC", "token0_dec": 8,
            "token1": "USDC", "token1_dec": 6,
            "base_is_token0": True,
            "fee_bps": 30,
            "tvl_note": "Uniswap v3 WBTC/USDC 0.30%, canonical BTC/USD proxy.",
        },
    },
}


# ── Module state ────────────────────────────────────────────────────────────

_cache: dict[tuple[str, str, int], dict[str, Any]] = {}

_cb_failures: dict[str, int] = {"ethereum": 0, "base": 0}
_cb_open_until: dict[str, float] = {"ethereum": 0.0, "base": 0.0}

_metrics: dict[str, Any] = {
    "total_requests": 0,
    "successful": 0,
    "errors": 0,
    "cache_hits": 0,
    "symbols_not_supported": 0,
    "rpc_fallbacks": 0,
    "rpc_reverts": 0,
    "circuit_breaks": 0,
}


def _circuit_is_open(chain: str) -> bool:
    if _cb_failures.get(chain, 0) < _CB_MAX_FAILURES:
        return False
    return time.time() < _cb_open_until.get(chain, 0.0)


def _record_success(chain: str) -> None:
    _cb_failures[chain] = 0


def _record_failure(chain: str) -> None:
    _cb_failures[chain] = _cb_failures.get(chain, 0) + 1
    if _cb_failures[chain] >= _CB_MAX_FAILURES:
        _cb_open_until[chain] = time.time() + _CB_COOLDOWN_S
        _metrics["circuit_breaks"] += 1
        logger.warning(
            "[uniswap_v3:%s] circuit OPEN after %d failures, cooldown %ds",
            chain, _cb_failures[chain], _CB_COOLDOWN_S,
        )


# ── Input validation ────────────────────────────────────────────────────────


def _sanitize_symbol(symbol: str) -> str | None:
    if not isinstance(symbol, str):
        return None
    cleaned = symbol.strip().upper()
    if not cleaned or len(cleaned) > _SYMBOL_MAX_LEN:
        return None
    if not all(c.isalnum() for c in cleaned):
        return None
    return cleaned


def _sanitize_chain(chain: str) -> str | None:
    if not isinstance(chain, str):
        return None
    cleaned = chain.strip().lower()
    if cleaned not in SUPPORTED_CHAINS:
        return None
    return cleaned


def _sanitize_window(window_s: int) -> int | None:
    if not isinstance(window_s, int) or isinstance(window_s, bool):
        return None
    if window_s < MIN_WINDOW_S or window_s > MAX_WINDOW_S:
        return None
    return window_s


def has_pool(symbol: str, chain: str) -> bool:
    """True iff a Uniswap v3 pool is configured for (symbol, chain)."""
    sym = _sanitize_symbol(symbol)
    ch = _sanitize_chain(chain)
    if sym is None or ch is None:
        return False
    return sym in UNISWAP_V3_POOLS and ch in UNISWAP_V3_POOLS[sym]


def all_supported_symbols() -> dict[str, list[str]]:
    """Return {chain: sorted [symbols]} grouping.

    Used by routes_sources.py to surface the full coverage per chain in
    `/api/symbols.by_source.uniswap_v3_<chain>` without duplicating the
    hardcoded dict.
    """
    grouping: dict[str, set[str]] = {chain: set() for chain in SUPPORTED_CHAINS}
    for symbol, by_chain in UNISWAP_V3_POOLS.items():
        for chain in by_chain:
            if chain in grouping:
                grouping[chain].add(symbol)
    return {chain: sorted(syms) for chain, syms in grouping.items()}


# ── ABI encoding / decoding ─────────────────────────────────────────────────


def _encode_observe_calldata(seconds_agos: tuple[int, ...]) -> str:
    """Encode observe(uint32[] secondsAgos) calldata.

    Layout: selector (4 bytes) + offset to dynamic data (32 bytes) +
    array length (32 bytes) + entries (32 bytes each, big-endian, uint32
    left-padded to uint256).
    """
    parts = [OBSERVE_SELECTOR]
    parts.append((32).to_bytes(32, "big").hex())
    parts.append(len(seconds_agos).to_bytes(32, "big").hex())
    for s in seconds_agos:
        if not (0 <= s < 2**32):
            raise ValueError(f"secondsAgos entry out of uint32 range: {s}")
        parts.append(s.to_bytes(32, "big").hex())
    return "".join(parts)


def _decode_observe_result(hex_result: str) -> tuple[list[int], list[int]]:
    """Decode observe()'s return tuple into (tickCumulatives, secondsPerLiqX128).

    Solidity ABI for `(int56[] memory, uint160[] memory)`:
        [offset1:32][offset2:32] .. [len1:32][item1:32][item2:32 ...]
                                    [len2:32][item1:32][item2:32 ...]

    We only care about tickCumulatives -- the second array is returned
    too so callers can implement EWMA-style pricing, but MAXIA Oracle
    does not expose it outside of this helper.
    """
    raw = bytes.fromhex(hex_result.removeprefix("0x"))
    if len(raw) < 64:
        raise ValueError("observe() response too short (expected 2 offsets)")

    off1 = int.from_bytes(raw[0:32], "big")
    off2 = int.from_bytes(raw[32:64], "big")
    for name, off in (("tickCumulatives", off1), ("secondsPerLiquidity", off2)):
        if off + 32 > len(raw):
            raise ValueError(f"{name} offset out of bounds: {off}")

    len1 = int.from_bytes(raw[off1:off1 + 32], "big")
    if off1 + 32 + len1 * 32 > len(raw):
        raise ValueError("tickCumulatives array truncated")
    tick_cumulatives = [
        int.from_bytes(raw[off1 + 32 + i * 32: off1 + 64 + i * 32], "big", signed=True)
        for i in range(len1)
    ]

    len2 = int.from_bytes(raw[off2:off2 + 32], "big")
    if off2 + 32 + len2 * 32 > len(raw):
        raise ValueError("secondsPerLiquidity array truncated")
    seconds_per_liq = [
        int.from_bytes(raw[off2 + 32 + i * 32: off2 + 64 + i * 32], "big", signed=False)
        for i in range(len2)
    ]

    return tick_cumulatives, seconds_per_liq


def _twap_price_from_ticks(
    tick_cumulatives: list[int],
    window_s: int,
    decimals0: int,
    decimals1: int,
    base_is_token0: bool,
) -> tuple[int, float]:
    """Return `(avg_tick, human_price)` computed from two cumulatives.

    See module docstring for the math. `secondsAgos = [window, 0]` so
    `tick_cumulatives[1]` is the newest cumulative tick.
    """
    if len(tick_cumulatives) != 2:
        raise ValueError(
            f"expected 2 tick cumulatives, got {len(tick_cumulatives)}"
        )
    if window_s <= 0:
        raise ValueError("window_s must be positive")

    delta = tick_cumulatives[1] - tick_cumulatives[0]
    # Uniswap v3 uses integer division towards negative infinity in
    # Solidity; Python's `//` matches, but we want truncation toward
    # zero for symmetric behaviour on negative ticks -- do it manually.
    if (delta < 0) and (delta % window_s != 0):
        avg_tick = -(-delta // window_s)
    else:
        avg_tick = delta // window_s

    raw = 1.0001 ** avg_tick
    human_t1_per_t0 = raw * (10 ** (decimals0 - decimals1))
    if base_is_token0:
        human_price = human_t1_per_t0
    else:
        if human_t1_per_t0 == 0:
            raise ValueError("raw price underflowed to 0 -- pool may be mispriced")
        human_price = 1.0 / human_t1_per_t0
    return avg_tick, human_price


# ── RPC layer ───────────────────────────────────────────────────────────────


async def _eth_call(
    client: httpx.AsyncClient,
    rpc_url: str,
    to: str,
    data: str,
) -> tuple[str | None, str | None]:
    """Return (hex_result, revert_reason). Exactly one of the two is set.

    revert_reason is a short string when the node returned a regular
    JSON-RPC error (e.g. 'execution reverted: OLD'). Transport failures
    and unexpected shapes return (None, None) so the caller tries the
    next RPC in the pool.
    """
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": to, "data": data}, "latest"],
    }
    try:
        resp = await client.post(rpc_url, json=body, timeout=RPC_TIMEOUT_S)
    except httpx.TimeoutException:
        logger.debug("[uniswap_v3] rpc timeout %s", rpc_url)
        return None, None
    except httpx.HTTPError as exc:
        logger.debug("[uniswap_v3] rpc transport %s: %s", rpc_url, type(exc).__name__)
        return None, None

    if resp.status_code >= 400:
        logger.debug("[uniswap_v3] rpc %s -> HTTP %d", rpc_url, resp.status_code)
        return None, None

    try:
        payload = resp.json()
    except ValueError:
        return None, None

    if isinstance(payload, dict):
        if "result" in payload:
            result = payload["result"]
            if isinstance(result, str) and result.startswith("0x"):
                return result, None
            return None, None
        err = payload.get("error")
        if isinstance(err, dict):
            msg = err.get("message", "")
            if isinstance(msg, str):
                return None, msg
    return None, None


async def _observe(
    client: httpx.AsyncClient,
    chain: str,
    pool: str,
    seconds_agos: tuple[int, ...],
) -> tuple[list[int] | None, str | None]:
    """Call observe() on `pool` through the chain's RPC pool.

    Returns (tick_cumulatives, revert_reason). Exactly one is set on
    success/revert; both None if every RPC failed.
    """
    calldata = _encode_observe_calldata(seconds_agos)
    rpcs = CHAIN_RPC_URLS.get(chain, ())

    for idx, rpc in enumerate(rpcs):
        hex_result, revert = await _eth_call(client, rpc, pool, calldata)
        if revert is not None:
            return None, revert
        if hex_result is None:
            continue
        if idx > 0:
            _metrics["rpc_fallbacks"] += 1
        try:
            tick_cumulatives, _ = _decode_observe_result(hex_result)
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "[uniswap_v3:%s] decode failed on %s: %s", chain, rpc,
                type(exc).__name__,
            )
            continue
        return tick_cumulatives, None

    return None, None


# ── Public API ──────────────────────────────────────────────────────────────


async def get_twap_price(
    symbol: str,
    chain: str = DEFAULT_CHAIN,
    window_s: int = DEFAULT_WINDOW_S,
) -> dict[str, Any]:
    """Fetch a Uniswap v3 TWAP price for `symbol` on `chain`.

    Returns on success:
        {"price", "avg_tick", "window_s", "tick_cumulatives",
         "chain", "pool", "fee_bps", "token0", "token1",
         "source": "uniswap_v3", "symbol"}

    On failure (never raises):
        {"error": str, "source": "uniswap_v3", "symbol", "chain"}
    """
    cleaned_sym = _sanitize_symbol(symbol)
    cleaned_chain = _sanitize_chain(chain)
    cleaned_window = _sanitize_window(window_s)

    if cleaned_sym is None:
        return {
            "error": "invalid symbol format",
            "source": "uniswap_v3",
            "symbol": str(symbol)[:32],
            "chain": str(chain)[:32],
        }
    if cleaned_chain is None:
        return {
            "error": (
                f"unsupported chain -- must be one of "
                f"{sorted(SUPPORTED_CHAINS)}"
            ),
            "source": "uniswap_v3",
            "symbol": cleaned_sym,
            "chain": str(chain)[:32],
        }
    if cleaned_window is None:
        return {
            "error": (
                f"window_s must be an int within "
                f"[{MIN_WINDOW_S}, {MAX_WINDOW_S}]"
            ),
            "source": "uniswap_v3",
            "symbol": cleaned_sym,
            "chain": cleaned_chain,
        }

    _metrics["total_requests"] += 1

    sym_entry = UNISWAP_V3_POOLS.get(cleaned_sym, {})
    pool_cfg = sym_entry.get(cleaned_chain)
    if pool_cfg is None:
        _metrics["symbols_not_supported"] += 1
        return {
            "error": "no Uniswap v3 pool configured for this symbol on this chain",
            "source": "uniswap_v3",
            "symbol": cleaned_sym,
            "chain": cleaned_chain,
        }

    cache_key = (cleaned_sym, cleaned_chain, cleaned_window)
    now = time.time()
    cached = _cache.get(cache_key)
    if cached and now - cached["ts"] < _CACHE_TTL_S:
        _metrics["cache_hits"] += 1
        return cached["data"]

    if _circuit_is_open(cleaned_chain):
        return {
            "error": f"uniswap_v3 {cleaned_chain} circuit open",
            "source": "uniswap_v3",
            "symbol": cleaned_sym,
            "chain": cleaned_chain,
        }

    client = get_http_client()
    try:
        tick_cumulatives, revert = await _observe(
            client, cleaned_chain, pool_cfg["pool"], (cleaned_window, 0)
        )
    except Exception as exc:  # noqa: BLE001
        _metrics["errors"] += 1
        _record_failure(cleaned_chain)
        return {
            "error": safe_error("uniswap_v3 observe failed", exc, logger),
            "source": "uniswap_v3",
            "symbol": cleaned_sym,
            "chain": cleaned_chain,
        }

    if revert is not None:
        _metrics["rpc_reverts"] += 1
        # A revert means the pool itself answered "no" (usually because
        # the observation cardinality is smaller than the window, or
        # the pool has not accumulated enough history yet). Do NOT trip
        # the circuit -- the RPC is fine, the pool isn't.
        return {
            "error": f"pool rejected observe(): {revert[:200]}",
            "source": "uniswap_v3",
            "symbol": cleaned_sym,
            "chain": cleaned_chain,
        }

    if tick_cumulatives is None:
        _metrics["errors"] += 1
        _record_failure(cleaned_chain)
        return {
            "error": f"uniswap_v3 {cleaned_chain} RPC pool exhausted",
            "source": "uniswap_v3",
            "symbol": cleaned_sym,
            "chain": cleaned_chain,
        }

    try:
        avg_tick, price = _twap_price_from_ticks(
            tick_cumulatives,
            cleaned_window,
            pool_cfg["token0_dec"],
            pool_cfg["token1_dec"],
            pool_cfg["base_is_token0"],
        )
    except Exception as exc:  # noqa: BLE001
        _metrics["errors"] += 1
        return {
            "error": safe_error("uniswap_v3 price computation failed", exc, logger),
            "source": "uniswap_v3",
            "symbol": cleaned_sym,
            "chain": cleaned_chain,
        }

    if price <= 0:
        _metrics["errors"] += 1
        return {
            "error": "uniswap_v3 computed non-positive price",
            "source": "uniswap_v3",
            "symbol": cleaned_sym,
            "chain": cleaned_chain,
        }

    result: dict[str, Any] = {
        "price": round(price, 8),
        "avg_tick": avg_tick,
        "window_s": cleaned_window,
        "tick_cumulatives": tick_cumulatives,
        "chain": cleaned_chain,
        "pool": pool_cfg["pool"],
        "fee_bps": pool_cfg["fee_bps"],
        "token0": pool_cfg["token0"],
        "token1": pool_cfg["token1"],
        "source": "uniswap_v3",
        "symbol": cleaned_sym,
    }

    if len(_cache) >= _CACHE_MAX:
        _cache.pop(next(iter(_cache)), None)
    _cache[cache_key] = {"data": result, "ts": now}

    _metrics["successful"] += 1
    _record_success(cleaned_chain)
    return result


def get_metrics() -> dict[str, Any]:
    return {
        **_metrics,
        "circuit": {
            chain: {
                "state": "open" if _circuit_is_open(chain) else "closed",
                "failures": _cb_failures.get(chain, 0),
                "max_failures": _CB_MAX_FAILURES,
                "cooldown_s": _CB_COOLDOWN_S,
            }
            for chain in SUPPORTED_CHAINS
        },
        "cache_size": len(_cache),
        "supported_pools": {
            sym: sorted(by_chain.keys())
            for sym, by_chain in UNISWAP_V3_POOLS.items()
        },
    }


def _reset_for_tests() -> None:
    """Test-only reset helper."""
    _cache.clear()
    for ch in SUPPORTED_CHAINS:
        _cb_failures[ch] = 0
        _cb_open_until[ch] = 0.0
    for key in list(_metrics.keys()):
        _metrics[key] = 0


logger.info(
    "uniswap_v3_oracle initialised -- %d symbols, chains=%s",
    len(UNISWAP_V3_POOLS), list(SUPPORTED_CHAINS),
)
