"""MAXIA Oracle — Minimal configuration.

Extracted from MAXIA V12/backend/core/config.py on 2026-04-14, reduced to the
strict subset required by the oracle services in backend/services/oracle/*.

The V12 original mixed escrow keys, marketing wallet, 17 agents, GPU, bridge
and staking config in one ~600-line file. MAXIA Oracle is strictly non-custodial
and non-regulated, so this minimal version exposes ONLY the Solana RPC helpers
used by price_oracle.py (Helius DAS + public RPC failover).

Environment variables (all optional — modules degrade gracefully):
    HELIUS_API_KEY       — Helius DAS API key (unlocks per-token prices)
    CHAINSTACK_RPC       — Chainstack Solana RPC URL (highest rate limit)
    ALCHEMY_SOLANA_KEY   — Alchemy Solana API key
    SOLANA_RPC           — Custom Solana RPC URL
    BASE_RPC_URL         — Base mainnet RPC (read by chainlink_oracle, default public)
    PYTH_HERMES_URL      — Pyth Hermes endpoint (read by pyth_oracle, default public)
    FINNHUB_API_KEY      — Equity fallback (read by pyth_oracle, optional)

Strict startup validation is deferred to Phase 2 (security audit — see
docs/security_audit_extraction.md, vuln C5 from AUDIT_COMPLET_V12.md).
"""
import os

from dotenv import load_dotenv

load_dotenv()

# ── Solana RPC (consumed by services.oracle.price_oracle) ──
HELIUS_API_KEY: str = os.getenv("HELIUS_API_KEY", "")
CHAINSTACK_RPC: str = os.getenv("CHAINSTACK_RPC", "")
ALCHEMY_SOLANA_KEY: str = os.getenv("ALCHEMY_SOLANA_KEY", "")
_SOLANA_RPC_CUSTOM: str = os.getenv("SOLANA_RPC", "")

# Public fallbacks (always appended last, never log URLs that contain api-key=)
_PUBLIC_RPC_FALLBACKS: tuple[str, ...] = (
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


SOLANA_RPC_URLS: list[str] = _build_solana_rpc_urls()


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
