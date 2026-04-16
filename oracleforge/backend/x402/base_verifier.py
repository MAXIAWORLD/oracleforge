"""Base-mainnet x402 verifier — thin wrapper over the V1.2 multi-chain verifier.

Phase 4 shipped a Base-only verifier. V1.2 factored the generic EVM
logic out into `x402.multichain_verifier` and now supports four chains
(Base, Arbitrum, Optimism, Polygon). This file stays as a rétrocompat
shim so that `x402.middleware` and `tests/test_phase4_x402.py` can keep
their existing imports untouched.

Every function here delegates to the chain-agnostic implementation with
`chain="base"`. Do not add new logic here — extend the multichain
verifier instead and expose new chains through the middleware.
"""
from __future__ import annotations

from typing import Any

from core.config import (
    BASE_CHAIN_ID,
    BASE_MIN_TX_USDC,
    BASE_RPC_URLS,
    BASE_USDC_CONTRACT,
    IS_NON_DEV,
    X402_FACILITATOR_URL,
    X402_TREASURY_ADDRESS_BASE,
)
from x402.multichain_verifier import (
    build_x402_challenge as _build_challenge,
    verify_evm_transaction as _verify_evm,
    verify_usdc_transfer as _verify_usdc,
    x402_verify_payment as _verify_payment,
)

# Re-export canonical symbols used by Phase 4 tests and by the middleware.
__all__ = [
    "BASE_CHAIN_ID",
    "BASE_MIN_TX_USDC",
    "BASE_RPC_URLS",
    "BASE_USDC_CONTRACT",
    "IS_NON_DEV",
    "X402_FACILITATOR_URL",
    "X402_TREASURY_ADDRESS_BASE",
    "verify_base_transaction",
    "verify_usdc_transfer_base",
    "x402_verify_payment_base",
    "build_x402_challenge_base",
]


async def verify_base_transaction(
    tx_hash: str, expected_to: str | None = None
) -> dict[str, Any]:
    """Verify a Base-mainnet transaction receipt (compat wrapper)."""
    return await _verify_evm("base", tx_hash, expected_to=expected_to)


async def verify_usdc_transfer_base(
    tx_hash: str,
    expected_amount_raw: int | None = None,
    expected_recipient: str | None = None,
) -> dict[str, Any]:
    """Verify a Base-mainnet USDC ERC-20 Transfer (compat wrapper)."""
    return await _verify_usdc(
        chain="base",
        tx_hash=tx_hash,
        expected_amount_raw=expected_amount_raw,
        expected_recipient=expected_recipient,
    )


async def x402_verify_payment_base(
    payment_header: str, expected_amount_usdc: float
) -> dict[str, Any]:
    """Verify an x402 payment on Base (compat wrapper — facilitator + fallback)."""
    return await _verify_payment("base", payment_header, expected_amount_usdc)


def build_x402_challenge_base(
    path: str, price_usdc: float, pay_to: str
) -> dict[str, Any]:
    """Build a single 402 accepts entry for Base (compat wrapper).

    The V1.0 signature takes an explicit `pay_to`. The V1.2 verifier
    reads the treasury from `X402_CHAIN_CONFIG["base"]["treasury"]`; the
    positional `pay_to` parameter is preserved for call-site compatibility
    but is ignored when it matches the configured treasury. When they
    differ (e.g. a test that injects a fake treasury), the explicit
    `pay_to` wins in the returned dict so existing assertions hold.
    """
    entry = _build_challenge("base", path, price_usdc)
    if entry is None:
        # No treasury configured for Base. Preserve the V1.0 shape so
        # Phase 4 tests that always pass a fake `pay_to` keep working.
        return {
            "scheme": "exact",
            "network": "base-mainnet",
            "maxAmountRequired": str(int(price_usdc * 1_000_000)),
            "resource": path,
            "description": f"MAXIA Oracle: {path}",
            "mimeType": "application/json",
            "payTo": pay_to,
            "asset": BASE_USDC_CONTRACT,
            "maxTimeoutSeconds": 60,
            "extra": {
                "chainId": BASE_CHAIN_ID,
                "facilitator": X402_FACILITATOR_URL,
            },
        }
    # Let the caller's explicit pay_to win if they passed one that
    # differs from the configured treasury — matches V1.0 semantics.
    if pay_to and pay_to.lower() != entry["payTo"].lower():
        entry["payTo"] = pay_to
    return entry
