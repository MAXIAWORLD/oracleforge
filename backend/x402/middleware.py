"""MAXIA Oracle — x402 middleware for Base mainnet, direct-sale mode (Phase 4).

Extraction origin: MAXIA V12/backend/integrations/x402_middleware.py (378 lines,
14 chains). This port keeps only the Base-mainnet path, drops the 13 other
chain verifiers, and replaces V12's `core.database` replay helper with the
MAXIA Oracle SQLite table `x402_txs` added in Step 2.

Flow:
    1. The middleware computes a price from `X402_PRICE_MAP` using exact
       match on the request path first, then a prefix match for entries
       ending with "/".
    2. If no price matches, the request proceeds untouched (unprotected
       route, e.g. /health or /api/register).
    3. If a price matches and the request carries no `X-Payment` header, the
       middleware returns 402 with a single-entry `accepts` list for
       base-mainnet.
    4. If `X-Payment` is present, the middleware verifies it via
       `x402_verify_payment_base()` (facilitator + on-chain fallback) and
       atomically records the transaction hash for replay protection. If the
       payment is valid and not a replay, the downstream route is invoked
       and a `request.state.x402_paid = True` flag is set so the auth
       dependency knows to skip the API-key check for this call.

Direct-sale guarantees:
    - The `payTo` field is always our treasury wallet, never a third party.
    - The service never holds a private key.
    - There is no escrow, no multi-party settlement, no custody.
    - Funds are withdrawn manually from the treasury to cold storage.

x402 as a parallel access path:
    This middleware does not replace the X-API-Key auth. A request that
    carries a valid `X-Payment` gets a one-shot paid access to the route;
    any other request falls through to the existing X-API-Key auth
    dependency in `core.auth.require_access`.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse

from core.config import BASE_CHAIN_ID, X402_PRICE_MAP, X402_TREASURY_ADDRESS_BASE
from core.db import get_db, x402_record_tx, x402_tx_already_processed
from core.disclaimer import DISCLAIMER_TEXT, wrap_error
from x402.base_verifier import build_x402_challenge_base, x402_verify_payment_base

logger = logging.getLogger("maxia_oracle.x402.middleware")


# ── Price matcher ───────────────────────────────────────────────────────────


def _match_price(path: str) -> float | None:
    """Return the x402 price for `path` or None if the path is not protected.

    Matching rules:
        1. Exact match wins (e.g. "/api/prices/batch" -> 0.005).
        2. Otherwise, the longest prefix entry ending with "/" wins
           (e.g. "/api/price/BTC" matches "/api/price/").
    """
    exact = X402_PRICE_MAP.get(path)
    if exact is not None:
        return exact

    # Longest matching prefix wins so that more specific rules override.
    best_prefix: str | None = None
    best_price: float | None = None
    for prefix, price in X402_PRICE_MAP.items():
        if not prefix.endswith("/"):
            continue
        if path.startswith(prefix):
            if best_prefix is None or len(prefix) > len(best_prefix):
                best_prefix = prefix
                best_price = price
    return best_price


# ── 402 challenge builder ───────────────────────────────────────────────────


def _build_402_response(path: str, price: float) -> JSONResponse:
    """Return a canonical 402 challenge with a single Base-mainnet accepts entry."""
    accepts: list[dict[str, Any]] = []
    if X402_TREASURY_ADDRESS_BASE:
        accepts.append(
            build_x402_challenge_base(path, price, X402_TREASURY_ADDRESS_BASE)
        )
    return JSONResponse(
        status_code=402,
        content={
            "x402Version": 2,
            "accepts": accepts,
            "error": "payment required",
            "disclaimer": DISCLAIMER_TEXT,
        },
        headers={"X-Payment-Required": "true"},
    )


def _payment_error(status: int, message: str, **extra: Any) -> JSONResponse:
    return JSONResponse(status_code=status, content=wrap_error(message, **extra))


# ── Middleware entry point ──────────────────────────────────────────────────


async def x402_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Any]],
) -> Any:
    """Starlette-style HTTP middleware implementing x402 pay-per-call on Base.

    Registered via `app.middleware("http")` in main.py. Runs AFTER the
    security-headers middleware because response header mutation is cheaper
    at the outermost layer.
    """
    path = request.url.path
    price = _match_price(path)

    # Unprotected routes (health, register, etc.) pass through untouched.
    if price is None:
        return await call_next(request)

    payment_header = request.headers.get("X-Payment")

    # If the client did not provide a payment header, leave the route
    # accessible via the X-API-Key path: downstream auth handles the case.
    # The x402 challenge is ONLY emitted when the client explicitly signals
    # it cannot use X-API-Key (by sending `X-Payment: required`), or when
    # the route is flagged as payment-only. For MAXIA Oracle V1 we emit the
    # challenge when no X-API-Key is present either — this lets agents
    # discover x402 organically on priced endpoints.
    has_api_key = bool(request.headers.get("X-API-Key"))

    if not payment_header:
        if has_api_key:
            # The route is priced, but the caller already has an API key.
            # Fall through to downstream auth (free tier) — no 402.
            return await call_next(request)
        # No X-API-Key and no X-Payment: emit the 402 challenge so the agent
        # can discover the payment options.
        return _build_402_response(path, price)

    # ── Payment verification ────────────────────────────────────────────────

    logger.info(
        "[x402] Payment attempt: path=%s amount=$%.6f header=%s...",
        path,
        price,
        payment_header[:16] if len(payment_header) >= 16 else payment_header,
    )

    try:
        result = await x402_verify_payment_base(payment_header, price)
    except Exception as exc:
        logger.error(
            "[x402] Verification raised %s on %s",
            type(exc).__name__,
            path,
            exc_info=True,
        )
        return _payment_error(402, "payment verification error")

    if not result.get("valid"):
        return _payment_error(
            402,
            "payment verification failed",
            detail=result.get("error", ""),
        )

    # ── Replay protection ───────────────────────────────────────────────────

    tx_hash = result.get("txHash") or payment_header
    if not tx_hash:
        return _payment_error(402, "payment verification returned no tx hash")

    db = get_db()
    # Fast-path: check before insert so we can return a specific error.
    if x402_tx_already_processed(db, tx_hash):
        return _payment_error(402, "payment already used (replay detected)")

    inserted = x402_record_tx(db, tx_hash, price, path)
    if not inserted:
        # Race condition: another worker recorded the same tx between our
        # check and our insert. Treat this as a replay attempt.
        return _payment_error(402, "payment already used (replay detected)")

    # Mark the request as x402-paid so downstream auth can skip the API-key
    # dependency for this call.
    request.state.x402_paid = True
    request.state.x402_tx_hash = tx_hash
    request.state.x402_amount_usdc = price
    request.state.x402_chain_id = BASE_CHAIN_ID

    return await call_next(request)
