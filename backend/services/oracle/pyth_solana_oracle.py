"""MAXIA Oracle -- Pyth native Solana on-chain reader (V1.4).

Reads Pyth price feed accounts directly on Solana mainnet via
`getAccountInfo` JSON-RPC + inline binary decode of the Anchor
`PriceUpdateV2` layout. No Hermes HTTP relay, no third-party Python
dependency -- pure httpx + stdlib struct.

## Why a separate reader from pyth_oracle.py (Hermes)?

`pyth_oracle.py` reads from https://hermes.pyth.network (off-chain HTTP
relay). This module reads the on-chain price feed account maintained
by the Pyth Data Association on shard 0. Both share the same publishers
and same feed IDs, but the on-chain account is verifiable by any Solana
program -- it's the canonical source of truth on Solana.

## Why price feed accounts (not ephemeral posting)?

The Pyth Solana Receiver program (`rec5EK...`) accepts *ephemeral*
price updates from any caller: each `postUpdate` instruction creates a
fresh keypair account, and a reader can only find it if the poster tells
them the pubkey. That's fine for a DeFi integration ("post and consume
in the same tx"), but it is useless for an external reader.

The Push Oracle program (`pythWSns...`) solves this by maintaining a
stable *Price Feed Account* per (shard_id, feed_id) pair, at a
deterministic PDA address. The Pyth Data Association sponsors the
updates on shard 0 for a curated list of majors.

PDA derivation:
    find_program_address(
        [shard_u16_little_endian, feed_id_32_bytes],
        push_oracle_program_id,
    )

All PDAs are pre-computed offline (see `scripts/precompute_pyth_solana_pdas.py`)
and hardcoded in PYTH_SOLANA_FEEDS below. This keeps the backend free of
any on-curve / ed25519 dependency at runtime.

## Account layout (PriceUpdateV2, Anchor-serialized, 134 bytes total)

    [0..8]    anchor discriminator (= 0x22F123639D7EF4CD for PriceUpdateV2)
    [8..40]   write_authority                               -- Pubkey  (32 B)
    [40]      verification_level variant
                  0 = Partial (followed by 1 byte num_signatures)
                  1 = Full    (no payload)
    then (offset depends on verification variant):
              feed_id                                       -- [u8;32]
              price              i64 little-endian
              conf               u64 little-endian
              exponent           i32 little-endian
              publish_time       i64 little-endian          -- unix seconds
              prev_publish_time  i64 little-endian
              ema_price          i64 little-endian
              ema_conf           u64 little-endian
              posted_slot        u64 little-endian

Source: https://github.com/pyth-network/pyth-crosschain, crate
`pyth_solana_receiver_sdk::price_update::{PriceUpdateV2,PriceFeedMessage}`,
pinned layout 2026-04-16 live-audit.

## Safety & product rules

- We REJECT any account with `verification_level != Full`. A Partial
  update only requires a subset of Wormhole guardian signatures, which
  lowers the honesty threshold -- dangerous for a price feed shipped
  under the "data feed, not investment advice" disclaimer.
- We REJECT any account whose decoded `feed_id` does not match the
  symbol we asked for (defends against account substitution / PDA
  collision accidents).
- We REJECT any non-positive price (malformed or pre-init feed).
- Stale threshold: `age_s > 60` (Pyth publishes every 400 ms; 60 s
  means ~150 missed slots = dead feed).
- Never raises. All error paths return `{"error": str, "source":
  "pyth_solana", "symbol": str}` so the HTTP route can turn that into
  a clean 404/502 and `collect_sources()` can drop it silently.

## What this reader does NOT do

- No TWAP / EMA aggregation across windows (`ema_price` is returned as
  a raw extra field but not used in `price`).
- No signing / posting / mutation of any account. This is read-only.
- No cross-shard iteration. Only shard 0 (sponsored). If a feed is
  not live on shard 0, it is simply absent from PYTH_SOLANA_FEEDS.
- No MCP resubscription / streaming. Each request is a fresh poll.
"""
from __future__ import annotations

import base64
import logging
import struct
import time
from typing import Any, Final

import httpx

from core.config import SOLANA_RPC_URLS
from core.errors import safe_error
from core.http_client import get_http_client

logger = logging.getLogger("pyth_solana_oracle")


# ── Constants ───────────────────────────────────────────────────────────────

PUSH_ORACLE_PROGRAM_ID: Final[str] = "pythWSnswVUd12oZpeFP8e9CVaEqJg25g1Vtc2biRsT"

# Anchor discriminator for the PriceUpdateV2 account type. Verified
# live on mainnet 2026-04-16 against BTC/ETH/SOL accounts.
PRICE_UPDATE_V2_DISCRIMINATOR: Final[bytes] = bytes.fromhex("22f123639d7ef4cd")

# Minimum account length. An ALLOCATED PriceUpdateV2 is 134 bytes (max
# across Partial/Full variants). We accept 133+ to tolerate a hypothetical
# tight-packed Full serialization, but in practice the Push Oracle always
# allocates 134.
MIN_ACCOUNT_LEN: Final[int] = 133

RPC_TIMEOUT_S: Final[float] = 8.0
_CACHE_TTL_S: Final[int] = 5               # Solana slot ~400 ms -> 12 slots
_STALE_AFTER_S: Final[int] = 60            # ~150 missed slots => dead
_CACHE_MAX: Final[int] = 100

# Circuit breaker — same pattern as redstone_oracle.
_CB_MAX_FAILURES: Final[int] = 5
_CB_COOLDOWN_S: Final[int] = 60

# Symbol charset — same as the rest of the oracle surface.
_SYMBOL_MAX_LEN: Final[int] = 10


# ── Feed catalog (hardcoded, pre-computed 2026-04-16) ───────────────────────
#
# Source: `oracleforge/scripts/precompute_pyth_solana_pdas.py`. Re-run
# that script to regenerate this dict when new feeds are sponsored on
# shard 0. Each entry holds:
#     feed_id       -- 64-char lowercase hex, matches the Hermes feed id.
#     price_account -- base58 PDA shard 0 derived with seeds
#                      [shard_u16_le, feed_id_32] over the Push Oracle
#                      program id PUSH_ORACLE_PROGRAM_ID.
#
# Coverage mandate: only symbols that on 2026-04-16 returned
# `verification_level = Full` and `age_s < 120` were kept. Symbols absent
# from this dict are silently unsupported -- Hermes coverage (see
# pyth_oracle.CRYPTO_FEEDS + EQUITY_FEEDS) remains available for them.

PYTH_SOLANA_FEEDS: Final[dict[str, dict[str, str]]] = {
    "BONK": {
        "feed_id": "72b021217ca3fe68922a19aaf990109cb9d84e9ad004b4d2025ad6f529314419",
        "price_account": "DBE3N8uNjhKPRHfANdwGvCZghWXyLPdqdSbEW2XFwBiX",
    },
    "BTC": {
        "feed_id": "e62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
        "price_account": "4cSM2e6rvbGQUFiJbqytoVMi5GgghSMr8LwVrT9VPSPo",
    },
    "ETH": {
        "feed_id": "ff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
        "price_account": "42amVS4KgzR9rA28tkVYqVXjq9Qa8dcZQMbH5EYFX6XC",
    },
    "EUR": {
        "feed_id": "a995d00bb36a63cef7fd2c287dc105fc8f3d93779f062f09551b0af3e81ec30b",
        "price_account": "Fu76ChamBDjE8UuGLV6GP2AcPPSU6gjhkNhAyuoPm7ny",
    },
    "GBP": {
        "feed_id": "84c2dde9633d93d1bcad84e7dc41c9d56578b7ec52fabedc1f335d673df0a7c1",
        "price_account": "G25Tm7UkVruTJ7mcbCxFm45XGWwsH72nJKNGcHEQw1tU",
    },
    "JTO": {
        "feed_id": "b43660a5f790c69354b0729a5ef9d50d68f1df92107540210b9cccba1f947cc2",
        "price_account": "7ajR2zA4MGMMTqRAVjghTKqPPn4kbrj3pYkAVRVwTGzP",
    },
    "JUP": {
        "feed_id": "0a0408d619e9380abad35060f9192039ed5042fa6f82301d0e48bb52be830996",
        "price_account": "7dbob1psH1iZBS7qPsm3Kwbf5DzSXK8Jyg31CTgTnxH5",
    },
    "PYTH": {
        "feed_id": "0bbf28e9a841a1cc788f6a361b17ca072d0ea3098a1e5df1c3922d06719579ff",
        "price_account": "8vjchtMuJNY4oFQdTi8yCe6mhCaNBFaUbktT482TpLPS",
    },
    "RAY": {
        "feed_id": "91568baa8beb53db23eb3fb7f22c6e8bd303d103919e19733f2bb642d3e7987a",
        "price_account": "Hhipna3EoWR7u8pDruUg8RxhP5F6XLh6SEHMVDmZhWi8",
    },
    "SOL": {
        "feed_id": "ef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4cfac8c280b56d",
        "price_account": "7UVimffxr9ow1uXYxsr4LHAcV58mLzhmwaeKvJ1pjLiE",
    },
    "USDC": {
        "feed_id": "eaa020c61cc479712813461ce153894a96a6c00b21ed0cfc2798d1f9a9e9c94a",
        "price_account": "Dpw1EAVrSB1ibxiDQyTAW6Zip3J4Btk2x4SgApQCeFbX",
    },
    "USDT": {
        "feed_id": "2b89b9dc8fdf9f34709a5b106b472f0f39bb6ca9ce04b0fd7f2e971688e2e53b",
        "price_account": "HT2PLQBcG5EiCcNSaMHAjSgd9F98ecpATbk4Sk5oYuM",
    },
    "WIF": {
        "feed_id": "4ca4beeca86f0d164160323817a4e42b10010a724c2217c6ee41b54cd4cc61fc",
        "price_account": "6B23K3tkb51vLZA14jcEQVCA1pfHptzEHFA93V5dYwbT",
    },
}


# ── Module state (cache, breaker, metrics) ──────────────────────────────────

_cache: dict[str, dict[str, Any]] = {}

_cb_failures: int = 0
_cb_open_until: float = 0.0

_metrics: dict[str, Any] = {
    "total_requests": 0,
    "successful": 0,
    "errors": 0,
    "cache_hits": 0,
    "symbols_not_supported": 0,
    "rejects_verification": 0,
    "rejects_feed_id_mismatch": 0,
    "rejects_discriminator_mismatch": 0,
    "circuit_breaks": 0,
    "rpc_fallbacks": 0,
}


def _circuit_is_open() -> bool:
    if _cb_failures < _CB_MAX_FAILURES:
        return False
    return time.time() < _cb_open_until


def _record_success() -> None:
    global _cb_failures
    _cb_failures = 0


def _record_failure() -> None:
    global _cb_failures, _cb_open_until
    _cb_failures += 1
    if _cb_failures >= _CB_MAX_FAILURES:
        _cb_open_until = time.time() + _CB_COOLDOWN_S
        _metrics["circuit_breaks"] += 1
        logger.warning(
            "[pyth_solana] circuit OPEN after %d failures, cooldown %ds",
            _cb_failures, _CB_COOLDOWN_S,
        )


def _sanitize_symbol(symbol: str) -> str | None:
    """Return a canonical uppercase ticker, or None if malformed."""
    if not isinstance(symbol, str):
        return None
    cleaned = symbol.strip().upper()
    if not cleaned or len(cleaned) > _SYMBOL_MAX_LEN:
        return None
    if not all(c.isalnum() for c in cleaned):
        return None
    return cleaned


def has_feed(symbol: str) -> bool:
    """True iff `symbol` has a configured shard-0 price feed account."""
    cleaned = _sanitize_symbol(symbol)
    return cleaned is not None and cleaned in PYTH_SOLANA_FEEDS


def list_supported_symbols() -> list[str]:
    """Sorted list of symbols exposed by this module."""
    return sorted(PYTH_SOLANA_FEEDS.keys())


# ── Binary decoder ──────────────────────────────────────────────────────────


class _DecodeError(Exception):
    """Raised by `_decode_price_update_v2` on any layout / validation error.
    Mapped to a user-facing error string by the public API below.
    """


def _decode_price_update_v2(data: bytes, expected_feed_id_hex: str) -> dict[str, Any]:
    """Parse the Anchor PriceUpdateV2 layout.

    Strict: rejects any discriminator/feed_id/verification mismatch. The
    caller turns each _DecodeError into a user-facing `error` string and
    bumps the matching reject counter.

    Returns a dict with the parsed fields (price still in i64+exp form;
    the caller applies scaling for the JSON payload).
    """
    if len(data) < MIN_ACCOUNT_LEN:
        raise _DecodeError(f"account too short: {len(data)} < {MIN_ACCOUNT_LEN}")

    disc = data[0:8]
    if disc != PRICE_UPDATE_V2_DISCRIMINATOR:
        raise _DecodeError("discriminator mismatch (account is not PriceUpdateV2)")

    # write_authority [8..40] is informational; we do not validate it.
    vl_variant = data[40]
    if vl_variant == 1:
        verification = "Full"
        off = 41
    elif vl_variant == 0:
        # Partial(num_signatures: u8).
        num_sig = data[41]
        verification = f"Partial(num_signatures={num_sig})"
        off = 42
    else:
        raise _DecodeError(f"unknown verification_level variant: {vl_variant}")

    # Bounds check before reading the message body (84 B + 8 B posted_slot).
    if len(data) < off + 32 + 8 + 8 + 4 + 8 + 8 + 8 + 8 + 8:
        raise _DecodeError("account truncated before end of PriceFeedMessage")

    feed_id = data[off:off + 32]; off += 32
    price = struct.unpack_from("<q", data, off)[0]; off += 8
    conf = struct.unpack_from("<Q", data, off)[0]; off += 8
    exponent = struct.unpack_from("<i", data, off)[0]; off += 4
    publish_time = struct.unpack_from("<q", data, off)[0]; off += 8
    prev_publish_time = struct.unpack_from("<q", data, off)[0]; off += 8
    ema_price = struct.unpack_from("<q", data, off)[0]; off += 8
    ema_conf = struct.unpack_from("<Q", data, off)[0]; off += 8
    posted_slot = struct.unpack_from("<Q", data, off)[0]

    feed_id_hex = feed_id.hex()
    if feed_id_hex != expected_feed_id_hex:
        raise _DecodeError("feed_id mismatch -- PDA points to a different feed")

    return {
        "verification": verification,
        "verification_is_full": (vl_variant == 1),
        "feed_id_hex": feed_id_hex,
        "price_i64": price,
        "conf_u64": conf,
        "exponent": exponent,
        "publish_time": publish_time,
        "prev_publish_time": prev_publish_time,
        "ema_price_i64": ema_price,
        "ema_conf_u64": ema_conf,
        "posted_slot": posted_slot,
    }


# ── RPC layer ───────────────────────────────────────────────────────────────


async def _rpc_get_account_info(
    client: httpx.AsyncClient,
    rpc_url: str,
    pubkey: str,
) -> bytes | None:
    """Single JSON-RPC call. Returns decoded account bytes, or None.

    None means one of: HTTP error, JSON parse error, account not found,
    unexpected response shape. The caller tries the next RPC in the pool.
    """
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAccountInfo",
        "params": [pubkey, {"encoding": "base64", "commitment": "confirmed"}],
    }
    # Routine fallback-pool errors (timeouts, 403s, malformed JSON) are
    # expected on public RPCs -- we log them at DEBUG with only the type
    # name and swallow them so the next RPC is tried. Nothing here ever
    # reaches a client; safe_error() is reserved for the public API layer.
    try:
        resp = await client.post(rpc_url, json=body, timeout=RPC_TIMEOUT_S)
    except httpx.TimeoutException:
        logger.debug("[pyth_solana] rpc timeout %s", rpc_url)
        return None
    except httpx.HTTPError as exc:
        logger.debug("[pyth_solana] rpc transport error %s: %s", rpc_url, type(exc).__name__)
        return None

    if resp.status_code >= 400:
        logger.debug("[pyth_solana] rpc %s -> HTTP %d", rpc_url, resp.status_code)
        return None

    try:
        payload = resp.json()
    except ValueError:
        logger.debug("[pyth_solana] rpc %s -> non-JSON body", rpc_url)
        return None

    result = payload.get("result")
    if not isinstance(result, dict):
        return None
    value = result.get("value")
    if value is None:
        return None
    data = value.get("data")
    if not (isinstance(data, list) and len(data) == 2 and data[1] == "base64"):
        return None
    try:
        return base64.b64decode(data[0], validate=True)
    except Exception:
        return None


async def _fetch_account(client: httpx.AsyncClient, pubkey: str) -> bytes | None:
    """Iterate the configured RPC pool until one returns account bytes."""
    for idx, rpc in enumerate(SOLANA_RPC_URLS):
        data = await _rpc_get_account_info(client, rpc, pubkey)
        if data is not None:
            if idx > 0:
                _metrics["rpc_fallbacks"] += 1
            return data
    return None


# ── Public API ──────────────────────────────────────────────────────────────


async def get_pyth_solana_price(symbol: str) -> dict[str, Any]:
    """Fetch an on-chain Pyth price for `symbol` (shard-0 Price Feed Account).

    Returns:
        On success: {"price": float, "conf": float, "confidence_pct": float,
                     "publish_time": int, "age_s": int, "stale": bool,
                     "source": "pyth_solana", "symbol": str,
                     "price_account": str, "posted_slot": int,
                     "exponent": int, "feed_id": str}
        On failure: {"error": str, "source": "pyth_solana", "symbol": str}

    Never raises.
    """
    cleaned = _sanitize_symbol(symbol)
    if cleaned is None:
        return {
            "error": "invalid symbol format",
            "source": "pyth_solana",
            "symbol": str(symbol)[:32],
        }

    _metrics["total_requests"] += 1

    feed_cfg = PYTH_SOLANA_FEEDS.get(cleaned)
    if feed_cfg is None:
        _metrics["symbols_not_supported"] += 1
        return {
            "error": "symbol not supported on Pyth Solana shard 0",
            "source": "pyth_solana",
            "symbol": cleaned,
        }

    now = time.time()

    cached = _cache.get(cleaned)
    if cached and now - cached["ts"] < _CACHE_TTL_S:
        _metrics["cache_hits"] += 1
        # Recompute age_s on the fly so the cached entry doesn't look fresher
        # than it is when the caller reads it after a 4-second delay.
        fresh = dict(cached["data"])
        fresh["age_s"] = max(0, int(now) - fresh["publish_time"])
        fresh["stale"] = fresh["age_s"] > _STALE_AFTER_S
        return fresh

    if _circuit_is_open():
        return {
            "error": "pyth_solana circuit open",
            "source": "pyth_solana",
            "symbol": cleaned,
        }

    client = get_http_client()
    try:
        account_bytes = await _fetch_account(client, feed_cfg["price_account"])
    except Exception as exc:  # noqa: BLE001
        _metrics["errors"] += 1
        _record_failure()
        return {
            "error": safe_error("pyth_solana fetch failed", exc, logger),
            "source": "pyth_solana",
            "symbol": cleaned,
        }

    if account_bytes is None:
        _metrics["errors"] += 1
        _record_failure()
        return {
            "error": "pyth_solana RPC pool exhausted",
            "source": "pyth_solana",
            "symbol": cleaned,
        }

    try:
        decoded = _decode_price_update_v2(account_bytes, feed_cfg["feed_id"])
    except _DecodeError as exc:
        msg = str(exc)
        _metrics["errors"] += 1
        if "discriminator" in msg:
            _metrics["rejects_discriminator_mismatch"] += 1
        elif "feed_id" in msg:
            _metrics["rejects_feed_id_mismatch"] += 1
        # DO NOT record_failure() on layout rejections -- a parsing problem
        # is not an RPC health issue and shouldn't trip the breaker.
        return {
            "error": f"pyth_solana decode: {msg}",
            "source": "pyth_solana",
            "symbol": cleaned,
        }

    if not decoded["verification_is_full"]:
        _metrics["rejects_verification"] += 1
        return {
            "error": (
                f"pyth_solana rejected partial verification "
                f"({decoded['verification']}) -- Full required"
            ),
            "source": "pyth_solana",
            "symbol": cleaned,
        }

    exponent = decoded["exponent"]
    if exponent > 0 or exponent < -18:
        # Defensive: all published Pyth feeds use negative exponents in
        # a sane range. An exponent outside [-18,0] signals a malformed
        # or fake account.
        _metrics["errors"] += 1
        return {
            "error": f"pyth_solana invalid exponent: {exponent}",
            "source": "pyth_solana",
            "symbol": cleaned,
        }

    scale = 10.0 ** exponent
    price = decoded["price_i64"] * scale
    conf = decoded["conf_u64"] * scale

    if price <= 0:
        _metrics["errors"] += 1
        return {
            "error": "pyth_solana returned non-positive price",
            "source": "pyth_solana",
            "symbol": cleaned,
        }

    publish_time = decoded["publish_time"]
    age_s = max(0, int(now) - publish_time)
    stale = age_s > _STALE_AFTER_S
    confidence_pct = round((conf / price) * 100.0, 4) if price > 0 else 0.0

    result: dict[str, Any] = {
        "price": round(price, 8),
        "conf": round(conf, 8),
        "confidence_pct": confidence_pct,
        "publish_time": publish_time,
        "age_s": age_s,
        "stale": stale,
        "source": "pyth_solana",
        "symbol": cleaned,
        "price_account": feed_cfg["price_account"],
        "posted_slot": decoded["posted_slot"],
        "exponent": exponent,
        "feed_id": feed_cfg["feed_id"],
    }

    # LRU-ish eviction.
    if len(_cache) >= _CACHE_MAX:
        _cache.pop(next(iter(_cache)), None)
    _cache[cleaned] = {"data": result, "ts": now}

    _metrics["successful"] += 1
    _record_success()
    return result


def get_metrics() -> dict[str, Any]:
    """Snapshot of module counters + circuit-breaker state."""
    return {
        **_metrics,
        "circuit": {
            "state": "open" if _circuit_is_open() else "closed",
            "failures": _cb_failures,
            "max_failures": _CB_MAX_FAILURES,
            "cooldown_s": _CB_COOLDOWN_S,
        },
        "cache_size": len(_cache),
        "supported_symbols": len(PYTH_SOLANA_FEEDS),
    }


def _reset_for_tests() -> None:
    """Test-only reset helper. Clears cache, breaker, metrics."""
    global _cb_failures, _cb_open_until
    _cache.clear()
    _cb_failures = 0
    _cb_open_until = 0.0
    for key in list(_metrics.keys()):
        _metrics[key] = 0


logger.info(
    "pyth_solana_oracle initialised -- %d feeds, push_oracle_program=%s",
    len(PYTH_SOLANA_FEEDS), PUSH_ORACLE_PROGRAM_ID,
)
