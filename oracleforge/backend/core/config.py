"""MAXIA Oracle — configuration + strict startup validation.

Phase 1 origin: extracted from MAXIA V12/backend/core/config.py and reduced
to the strict subset used by the oracle services. Phase 3 additions: strict
environment validation at import time (addresses V12 audit vulnerability C5,
"secrets without startup validation"). Phase 4 additions: x402 middleware
configuration for the Base mainnet direct-sale payment path.

The V12 original mixed escrow keys, marketing wallet, 17 agents, GPU, bridge
and staking config in one ~600-line file. MAXIA Oracle is strictly non-custodial
and non-regulated, so this file exposes ONLY the Solana RPC helpers consumed
by price_oracle.py plus the Phase 3 API deployment settings and the Phase 4
x402 Base-mainnet configuration.

## Environment variables (decision #8 from Phase 3 architecture)

REQUIRED in every environment:
    ENV                  — One of {"dev", "staging", "prod"}. The process
                           REFUSES to start if this is unset or invalid.

REQUIRED in staging and prod:
    API_KEY_PEPPER       — Server-side secret mixed into SHA256(api_key + pepper).
                           Prevents rainbow-table attacks even if the api_keys
                           table is exfiltrated. Must be >= 32 chars.
    DB_PATH              — Absolute or relative path to the SQLite database file.
                           Required in non-dev to prevent accidental use of a
                           throw-away default.
    X402_TREASURY_ADDRESS_BASE
                         — Public Base-mainnet address that receives x402
                           payments. MUST match ^0x[a-fA-F0-9]{40}$. The
                           private key is NEVER stored server-side; funds are
                           withdrawn manually to cold storage.

OPTIONAL in every environment:
    LOG_LEVEL            — Python logging level name (default "INFO" in dev,
                           "WARNING" in prod).
    HELIUS_API_KEY       — Helius DAS API key (unlocks per-token crypto prices).
    CHAINSTACK_RPC       — Chainstack Solana RPC URL (highest free-tier budget).
    ALCHEMY_SOLANA_KEY   — Alchemy Solana API key.
    SOLANA_RPC           — Custom Solana RPC URL.
    BASE_RPC_URL         — Base mainnet RPC (used by chainlink_oracle AND the
                           Phase 4 x402 base_verifier).
    PYTH_HERMES_URL      — Pyth Hermes endpoint (used by pyth_oracle).
    FINNHUB_API_KEY      — Equity fallback (used by pyth_oracle.get_stock_price).
    X402_FACILITATOR_URL — Coinbase x402 facilitator URL.
                           Default: https://x402.org/facilitator
                           MUST be HTTPS in staging/prod.
    BASE_MIN_TX_USDC     — Minimum USDC amount accepted on a single x402 call.
                           Default: 0.001 (matches X402_PRICE_MAP single-call price).

OPTIONAL in dev, REQUIRED in staging/prod:
    (same as above API_KEY_PEPPER / DB_PATH / X402_TREASURY_ADDRESS_BASE)
"""
from __future__ import annotations

import os
import re
from typing import Final

from dotenv import load_dotenv

load_dotenv()


# ── Environment bootstrap (strict validation — fails fast at import time) ──

_VALID_ENVS: Final[frozenset[str]] = frozenset({"dev", "staging", "prod"})
_MIN_PEPPER_LENGTH: Final[int] = 32


def _require_env(name: str, reason: str) -> str:
    """Read a required environment variable or raise RuntimeError.

    The error message names the variable and explains WHY it is required so
    the operator can fix the deployment without digging through the code.
    """
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} environment variable is required. {reason}"
        )
    return value


ENV: Final[str] = _require_env(
    "ENV",
    'Set ENV to one of "dev", "staging", "prod" before starting.',
)
if ENV not in _VALID_ENVS:
    raise RuntimeError(
        f'ENV must be one of {sorted(_VALID_ENVS)}, got "{ENV}".'
    )

IS_DEV: Final[bool] = ENV == "dev"
IS_STAGING: Final[bool] = ENV == "staging"
IS_PROD: Final[bool] = ENV == "prod"
IS_NON_DEV: Final[bool] = ENV in {"staging", "prod"}


# ── API key pepper (required in staging/prod, optional in dev) ──

_pepper_raw = os.getenv("API_KEY_PEPPER", "").strip()
if IS_NON_DEV and len(_pepper_raw) < _MIN_PEPPER_LENGTH:
    raise RuntimeError(
        f"API_KEY_PEPPER environment variable is required in {ENV}. "
        f"Generate a random value with at least {_MIN_PEPPER_LENGTH} characters "
        f'(e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`).'
    )
API_KEY_PEPPER: Final[str] = _pepper_raw


# ── DB path (required in staging/prod, default in dev) ──

_db_path_raw = os.getenv("DB_PATH", "").strip()
if IS_NON_DEV and not _db_path_raw:
    raise RuntimeError(
        f"DB_PATH environment variable is required in {ENV}. "
        f"Example: DB_PATH=/var/lib/maxia-oracle/maxia_oracle.db"
    )
DB_PATH: Final[str] = _db_path_raw or "./maxia_oracle.db"


# ── Logging level ──

_LOG_LEVEL_DEFAULT = "INFO" if IS_DEV else "WARNING"
LOG_LEVEL: Final[str] = os.getenv("LOG_LEVEL", _LOG_LEVEL_DEFAULT).upper()


# ── Solana RPC (consumed by services.oracle.price_oracle) ──

HELIUS_API_KEY: Final[str] = os.getenv("HELIUS_API_KEY", "")
CHAINSTACK_RPC: Final[str] = os.getenv("CHAINSTACK_RPC", "")
ALCHEMY_SOLANA_KEY: Final[str] = os.getenv("ALCHEMY_SOLANA_KEY", "")
_SOLANA_RPC_CUSTOM: Final[str] = os.getenv("SOLANA_RPC", "")

# Public fallbacks (always appended last, never log URLs that contain api-key=)
_PUBLIC_RPC_FALLBACKS: Final[tuple[str, ...]] = (
    "https://rpc.ankr.com/solana",
    "https://api.mainnet-beta.solana.com",
    "https://solana-mainnet.rpc.extrnode.com",
)


def _build_solana_rpc_urls() -> list[str]:
    """Build a prioritized list of Solana RPC endpoints.

    Priority order (highest free-tier budget first):
        1. Chainstack  (~3M req/month free)
        2. Alchemy     (~750k getTransaction/month free)
        3. Helius      (free tier, shared with DAS calls)
        4. Custom RPC  (from SOLANA_RPC env)
        5. Public RPCs (rate-limited but always reachable)
    """
    urls: list[str] = []
    if CHAINSTACK_RPC:
        urls.append(CHAINSTACK_RPC)
    if ALCHEMY_SOLANA_KEY:
        urls.append(f"https://solana-mainnet.g.alchemy.com/v2/{ALCHEMY_SOLANA_KEY}")
    if HELIUS_API_KEY:
        urls.append(f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}")
    if _SOLANA_RPC_CUSTOM and _SOLANA_RPC_CUSTOM not in urls:
        urls.append(_SOLANA_RPC_CUSTOM)
    urls.extend(_PUBLIC_RPC_FALLBACKS)
    return urls


SOLANA_RPC_URLS: Final[list[str]] = _build_solana_rpc_urls()


def get_rpc_url() -> str:
    """Return the highest-priority Solana RPC URL currently configured.

    Never log the returned URL: it may contain an API key in the query string.
    Use get_rpc_url_safe() for log lines.
    """
    return SOLANA_RPC_URLS[0] if SOLANA_RPC_URLS else _PUBLIC_RPC_FALLBACKS[1]


def get_rpc_url_safe() -> str:
    """Log-safe version of get_rpc_url() — masks the api-key query parameter."""
    url = get_rpc_url()
    if "api-key=" in url:
        return url.split("api-key=")[0] + "api-key=***"
    return url


# ══════════════════════════════════════════════════════════════════════════
# ── x402 Base mainnet configuration (Phase 4) ──
# ══════════════════════════════════════════════════════════════════════════
#
# MAXIA Oracle accepts x402 micropayments on Base mainnet in direct-sale mode:
# the agent pays a fixed USDC amount to our treasury wallet, and we return our
# data. No intermediation, no escrow, no custody. The private key of the
# treasury wallet is NEVER stored server-side; only the public address is
# referenced. Funds are withdrawn manually to cold storage on a regular basis.
#
# This configuration block intentionally supports Base ONLY in V1. The V12
# middleware supported 14 chains but that surface area is not justified for a
# V1 indie launch — Base is the canonical x402 chain (created by Coinbase) and
# covers the dominant agent ecosystems (ElizaOS, Coinbase AgentKit).

# EIP-style 0x-prefixed 20-byte address. Used to fail fast on a typo in
# X402_TREASURY_ADDRESS_BASE before any request hits the middleware.
_EVM_ADDRESS_PATTERN: Final[re.Pattern[str]] = re.compile(r"^0x[a-fA-F0-9]{40}$")


_treasury_base_raw = os.getenv("X402_TREASURY_ADDRESS_BASE", "").strip()
if IS_NON_DEV and not _treasury_base_raw:
    raise RuntimeError(
        f"X402_TREASURY_ADDRESS_BASE environment variable is required in {ENV}. "
        f"Set it to the public Base-mainnet address (0x...) of the MAXIA Oracle "
        f"treasury wallet. Never set a private key server-side — the wallet is "
        f"withdrawn manually to cold storage."
    )
if _treasury_base_raw and not _EVM_ADDRESS_PATTERN.match(_treasury_base_raw):
    raise RuntimeError(
        f"X402_TREASURY_ADDRESS_BASE must match ^0x[a-fA-F0-9]{{40}}$ "
        f"(42 chars total, 0x prefix + 40 hex). "
        f"Got a value of length {len(_treasury_base_raw)} starting with "
        f"{_treasury_base_raw[:6] or '(empty)'!r}."
    )
X402_TREASURY_ADDRESS_BASE: Final[str] = _treasury_base_raw


# Base mainnet chain parameters. Pinned canonical values — never user-controlled.
BASE_CHAIN_ID: Final[int] = 8453
BASE_USDC_CONTRACT: Final[str] = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


# Minimum USDC amount acceptable on a single x402 call. Keeps sanity against
# accidentally-configured-too-low prices. Default matches the single-call
# price in X402_PRICE_MAP below.
def _read_base_min_tx_usdc() -> float:
    raw = os.getenv("BASE_MIN_TX_USDC", "0.001").strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"BASE_MIN_TX_USDC must be a valid float, got {raw!r}"
        ) from exc
    if value <= 0:
        raise RuntimeError(
            f"BASE_MIN_TX_USDC must be strictly positive, got {value}"
        )
    return value


BASE_MIN_TX_USDC: Final[float] = _read_base_min_tx_usdc()


# V1.1 multi-chain RPC fallback pools.
#
# For every supported EVM chain we keep an ordered tuple of RPC endpoints:
# the env-configured primary (or a sensible public default) first, then two
# independent public fallbacks. The verifier / chainlink reader cycles
# through them in order and returns the first success. A one-RPC prod
# config is never acceptable — too many free public RPCs silently rate-
# limit the second request of a burst, and a cold fallback path is the
# cheapest resilience money can buy.
_BASE_RPC_PRIMARY: Final[str] = os.getenv(
    "BASE_RPC_URL", "https://mainnet.base.org"
).strip() or "https://mainnet.base.org"

_ETHEREUM_RPC_PRIMARY: Final[str] = os.getenv(
    "ETHEREUM_RPC_URL", "https://eth.llamarpc.com"
).strip() or "https://eth.llamarpc.com"

_ARBITRUM_RPC_PRIMARY: Final[str] = os.getenv(
    "ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc"
).strip() or "https://arb1.arbitrum.io/rpc"

CHAIN_RPC_URLS: Final[dict[str, tuple[str, ...]]] = {
    "base": (
        _BASE_RPC_PRIMARY,
        "https://base.llamarpc.com",
        "https://base-mainnet.public.blastapi.io",
    ),
    "ethereum": (
        _ETHEREUM_RPC_PRIMARY,
        "https://ethereum-rpc.publicnode.com",
        "https://rpc.ankr.com/eth",
    ),
    "arbitrum": (
        _ARBITRUM_RPC_PRIMARY,
        "https://arbitrum.llamarpc.com",
        "https://arbitrum-one-rpc.publicnode.com",
    ),
}

# Backward-compatibility alias for x402/base_verifier.py (Phase 4).
# New callers should prefer CHAIN_RPC_URLS["base"].
BASE_RPC_URLS: Final[tuple[str, ...]] = CHAIN_RPC_URLS["base"]


# Coinbase x402 facilitator endpoint. The facilitator decodes the canonical
# x402-v2 payment header (base64-encoded signed EIP-712 payload), verifies it
# against the on-chain state, and returns valid/invalid. If the facilitator
# times out or rejects, the verifier falls back to a direct RPC read of the
# user-supplied transaction hash. Must be HTTPS in non-dev.
X402_FACILITATOR_URL: Final[str] = os.getenv(
    "X402_FACILITATOR_URL", "https://x402.org/facilitator"
).strip() or "https://x402.org/facilitator"

if IS_NON_DEV and not X402_FACILITATOR_URL.startswith("https://"):
    raise RuntimeError(
        f"X402_FACILITATOR_URL must use HTTPS in {ENV}. "
        f"Got: {X402_FACILITATOR_URL!r}. "
        f"Non-TLS facilitator traffic is insecure and disabled in non-dev."
    )


# Priced paths for the x402 middleware. The middleware matches the request
# path against this map to decide whether payment is required.
#
# Matching rules (implemented in x402/middleware.py):
#   1. Exact match on the full path (e.g. "/api/prices/batch")
#   2. Prefix match on entries ending with "/" (e.g. "/api/price/" matches
#      "/api/price/BTC", "/api/price/ETH", etc.)
#
# Prices are in whole USDC. The middleware converts to atomic units (USDC has
# 6 decimals) when building the 402 challenge and when comparing against the
# on-chain transfer amount.
X402_PRICE_MAP: Final[dict[str, float]] = {
    "/api/price/": 0.001,          # per single-symbol call (prefix match)
    "/api/prices/batch": 0.005,    # per batch call (exact match, caps at 50 symbols)
}
