"""MAXIA Oracle — configuration + strict startup validation.

Phase 1 origin: extracted from MAXIA V12/backend/core/config.py and reduced
to the strict subset used by the oracle services. Phase 3 additions: strict
environment validation at import time (addresses V12 audit vulnerability C5,
"secrets without startup validation").

The V12 original mixed escrow keys, marketing wallet, 17 agents, GPU, bridge
and staking config in one ~600-line file. MAXIA Oracle is strictly non-custodial
and non-regulated, so this file exposes ONLY the Solana RPC helpers consumed
by price_oracle.py plus the Phase 3 API deployment settings.

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

OPTIONAL in every environment:
    LOG_LEVEL            — Python logging level name (default "INFO" in dev,
                           "WARNING" in prod).
    HELIUS_API_KEY       — Helius DAS API key (unlocks per-token crypto prices).
    CHAINSTACK_RPC       — Chainstack Solana RPC URL (highest free-tier budget).
    ALCHEMY_SOLANA_KEY   — Alchemy Solana API key.
    SOLANA_RPC           — Custom Solana RPC URL.
    BASE_RPC_URL         — Base mainnet RPC (used by chainlink_oracle).
    PYTH_HERMES_URL      — Pyth Hermes endpoint (used by pyth_oracle).
    FINNHUB_API_KEY      — Equity fallback (used by pyth_oracle.get_stock_price).

OPTIONAL in dev, REQUIRED in staging/prod:
    (same as above API_KEY_PEPPER / DB_PATH)
"""
from __future__ import annotations

import os
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
