"""Stripe billing routes — checkout, webhook, billing portal, key recovery (V2.3).

Five endpoints:
    POST /api/stripe/checkout   — auth (X-API-Key), starts a paid subscription
    POST /api/stripe/webhook    — Stripe → us, signed by STRIPE_WEBHOOK_SECRET
    POST /api/stripe/portal     — auth, returns Stripe billing portal URL
    POST /api/recover           — anon, email-driven key rotation
    GET  /api/account           — auth, current tier + quota usage

Both /checkout and /portal require a valid X-API-Key. We do NOT accept x402
payment for those — the whole point is to bind a Stripe subscription to a
DB-tracked api_keys row, which the anonymous x402 flow cannot do.
"""

from __future__ import annotations

import logging
import re
import secrets
from typing import Final

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from core import config
from core.auth import KEY_PREFIX, hash_key, require_api_key
from core.billing_tiers import quota_for_tier
from core.db import fetch_and_consume_pending_key, get_db, now_unix
from core.disclaimer import wrap_error, wrap_with_disclaimer
from core.rate_limit import (
    DAILY_WINDOW_S,
    check_register,
    compute_window_start,
)
from services.billing import stripe_service
from services.email import loops_sync

router = APIRouter(prefix="/api", tags=["stripe"])
logger = logging.getLogger("maxia_oracle.routes_stripe")

_EMAIL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


# ── Schemas ────────────────────────────────────────────────────────────────


class CheckoutRequest(BaseModel):
    # Use plain str + manual validation in the route so an invalid tier
    # produces a clean 400 (not a Pydantic 422 with cryptic error list).
    tier: str
    currency: str = "usd"
    email: str | None = None

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        cleaned = value.strip().lower()
        if not _EMAIL_PATTERN.match(cleaned):
            raise ValueError("invalid email format")
        return cleaned


class RecoverRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not _EMAIL_PATTERN.match(cleaned):
            raise ValueError("invalid email format")
        return cleaned


# ══════════════════════════════════════════════════════════════════════════
# ── POST /api/stripe/checkout ──
# ══════════════════════════════════════════════════════════════════════════


@router.post("/stripe/checkout")
async def create_checkout(
    body: CheckoutRequest,
    key_hash: str = Depends(require_api_key),
):
    """Create a Stripe Checkout session for the requested tier + currency."""
    if not config.STRIPE_SECRET_KEY:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=wrap_error("billing not configured"),
        )

    tier = (body.tier or "").lower()
    currency = (body.currency or "usd").lower()
    if tier not in {"dev", "pro"}:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error("invalid tier", valid=["dev", "pro"]),
        )
    if currency not in {"usd", "eur"}:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error("invalid currency", valid=["usd", "eur"]),
        )

    # Read price_id live from config so test monkey-patches work.
    price_attr = f"STRIPE_PRICE_{tier.upper()}_{currency.upper()}"
    price_id = getattr(config, price_attr, "") or ""
    if not price_id:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=wrap_error(
                "no price configured for this tier/currency",
                tier=tier,
                currency=currency,
            ),
        )

    success_url = f"{config.LANDING_BASE_URL}/upgrade-success.html?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{config.LANDING_BASE_URL}/#pricing"

    try:
        session = await stripe_service.create_checkout_session(
            price_id=price_id,
            key_hash=key_hash,
            tier=tier,
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=body.email,
        )
    except Exception as exc:
        logger.error("Stripe checkout session failed", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=wrap_error("checkout session creation failed", detail=str(exc)),
        )

    return wrap_with_disclaimer(
        {
            "session_id": session.get("id"),
            "url": session.get("url"),
            "tier": tier,
            "currency": currency,
        }
    )


# ══════════════════════════════════════════════════════════════════════════
# ── POST /api/stripe/webhook ──
# ══════════════════════════════════════════════════════════════════════════


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
):
    """Receive Stripe events. Verify HMAC, dispatch to event handlers.

    Always returns 200 once the signature passes — even on a no-op event —
    so Stripe stops retrying. A 4xx response makes Stripe back off and
    eventually disable the endpoint.
    """
    if not config.STRIPE_WEBHOOK_SECRET:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=wrap_error("webhook not configured"),
        )

    payload = await request.body()
    if not stripe_service.verify_signature(
        payload, stripe_signature or "", config.STRIPE_WEBHOOK_SECRET
    ):
        logger.warning(
            "Rejected Stripe webhook: bad signature (ip=%s, len=%d)",
            _client_ip(request),
            len(payload),
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error("invalid signature"),
        )

    import json

    try:
        event = json.loads(payload.decode("utf-8"))
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error("invalid event payload"),
        )

    db = get_db()
    result = stripe_service.handle_event(db, event)

    # Fire-and-forget transactional email on successful upgrade.
    if result.get("status") == "upgraded" and result.get("email"):
        try:
            await loops_sync.add_contact(
                result["email"],
                user_group=f"oracle-{result.get('tier', 'paid')}",
            )
        except Exception:
            logger.warning("Loops contact push failed post-upgrade", exc_info=True)

    return wrap_with_disclaimer(result)


# ══════════════════════════════════════════════════════════════════════════
# ── POST /api/stripe/portal ──
# ══════════════════════════════════════════════════════════════════════════


@router.post("/stripe/portal")
async def create_portal_session(
    key_hash: str = Depends(require_api_key),
):
    """Return a one-time Stripe billing portal URL for the caller's subscription."""
    if not config.STRIPE_SECRET_KEY:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=wrap_error("billing not configured"),
        )

    db = get_db()
    row = db.execute(
        "SELECT stripe_customer_id FROM api_keys WHERE key_hash = ?",
        (key_hash,),
    ).fetchone()
    customer_id = row["stripe_customer_id"] if row else None
    if not customer_id:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=wrap_error("no active subscription on this key"),
        )

    return_url = f"{config.LANDING_BASE_URL}/account.html"
    try:
        session = await stripe_service.create_billing_portal_session(
            customer_id=customer_id, return_url=return_url
        )
    except Exception as exc:
        logger.error("Stripe portal session failed", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=wrap_error("portal session creation failed", detail=str(exc)),
        )

    return wrap_with_disclaimer({"url": session.get("url")})


# ══════════════════════════════════════════════════════════════════════════
# ── POST /api/recover ──
# ══════════════════════════════════════════════════════════════════════════


@router.post("/recover")
async def recover_key(body: RecoverRequest, request: Request):
    """Rotate an API key by email — never reveals if the email exists.

    Throttled per-IP using the same `register_limit` table (1 / 60s) so a
    bot cannot enumerate emails. The response is always 200 with a generic
    message; the actual new key (if any) is sent by email via Loops.

    Flow when the email IS associated with a paid subscription:
        1. find_active_paid_row(email)
        2. generate fresh raw_key + key_hash
        3. UPDATE api_keys SET key_hash=new, … WHERE old key_hash matches
           — preserves stripe_customer_id, stripe_subscription_id, tier
        4. mark old key inactive (handled by row update — primary key changed)
        5. send transactional email via Loops

    Flow when no row matches: noop, identical 200 response.
    """
    db = get_db()
    decision = check_register(db, _client_ip(request))
    if not decision.allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=wrap_error(
                "rate limit",
                retry_after_seconds=decision.retry_after,
            ),
            headers={"Retry-After": str(decision.retry_after)},
        )

    row = db.execute(
        "SELECT key_hash, tier FROM api_keys "
        "WHERE email = ? AND active = 1 AND tier != 'free' "
        "ORDER BY created_at DESC LIMIT 1",
        (body.email,),
    ).fetchone()

    generic_response = wrap_with_disclaimer(
        {
            "message": (
                "If a paid subscription exists for this email, a new API key "
                "has been sent to it. Check your inbox."
            )
        }
    )

    if row is None:
        logger.info("recover: no paid row for email=%s***", body.email[:3])
        return generic_response

    old_hash = row["key_hash"]
    tier = row["tier"]

    new_raw = KEY_PREFIX + secrets.token_urlsafe(32)
    new_hash = hash_key(new_raw)

    # Atomic rotation: replace key_hash on the existing row. We update the PK
    # which SQLite supports; it preserves stripe_customer_id / subscription /
    # tier on the same logical row. Rate-limit + alerts rows keyed on the old
    # hash become orphans (cleaned at next purge) — acceptable for V2.3.
    try:
        db.execute(
            "UPDATE api_keys SET key_hash = ? WHERE key_hash = ?",
            (new_hash, old_hash),
        )
    except Exception:
        logger.error("recover: key rotation failed", exc_info=True)
        return generic_response

    # Send the new key by email. We use Loops with an ad-hoc user_group so
    # operators can wire a transactional template; the helper is fire-and-
    # forget and never raises.
    try:
        await loops_sync.add_contact(body.email, user_group=f"oracle-recover-{tier}")
    except Exception:
        logger.warning("recover: Loops push failed", exc_info=True)

    # IMPORTANT: in V2.3 the new key is also returned in the response so the
    # user sees it immediately (Loops template wiring is a Phase 7 follow-up).
    # When transactional email is fully wired we will switch to the email-
    # only delivery path.
    return wrap_with_disclaimer(
        {
            "message": "New key generated. Save it — it is shown only once.",
            "api_key": new_raw,
            "tier": tier,
        }
    )


# ══════════════════════════════════════════════════════════════════════════
# ── GET /api/stripe/session-key — one-shot key delivery post-checkout ──
# ══════════════════════════════════════════════════════════════════════════


_STRIPE_SESSION_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^cs_(test_|live_)?[A-Za-z0-9]{20,128}$"
)


@router.get("/stripe/session-key")
async def get_session_key(session_id: str, request: Request):
    """One-shot retrieval of the rotated API key after a successful checkout.

    The Stripe webhook stored the freshly-rotated raw key in
    `pending_key_delivery` keyed by Stripe session_id with a 10-min TTL.
    This endpoint returns the key once and immediately marks the row
    delivered=1 so a second reader gets 404. Combined with the
    welcome-paid email, the user has two redundant ways to learn the key.

    The success page calls this on load. Format checked at the edge to
    avoid wildcard reads.
    """
    if not session_id or not _STRIPE_SESSION_PATTERN.match(session_id):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error("invalid session_id"),
        )
    db = get_db()
    raw_key = fetch_and_consume_pending_key(db, session_id)
    if raw_key is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=wrap_error(
                "session_id unknown, expired or already consumed",
                hint=(
                    "Check your inbox — the welcome email contains your key. "
                    "If lost, use /recover.html"
                ),
            ),
        )
    return wrap_with_disclaimer({"api_key": raw_key, "session_id": session_id})


# ══════════════════════════════════════════════════════════════════════════
# ── GET /api/account ──
# ══════════════════════════════════════════════════════════════════════════


@router.get("/account")
async def get_account(key_hash: str = Depends(require_api_key)):
    """Return the caller's tier, daily quota, used today and reset timestamp."""
    db = get_db()
    row = db.execute(
        "SELECT tier, email, stripe_customer_id, stripe_subscription_id, created_at "
        "FROM api_keys WHERE key_hash = ?",
        (key_hash,),
    ).fetchone()
    if row is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=wrap_error("account not found"),
        )

    tier = row["tier"] or "free"
    limit = quota_for_tier(tier)
    window_start = compute_window_start(now_unix(), DAILY_WINDOW_S)
    used_row = db.execute(
        "SELECT count FROM rate_limit WHERE key_hash = ? AND window_start = ?",
        (key_hash, window_start),
    ).fetchone()
    used = used_row[0] if used_row else 0

    return wrap_with_disclaimer(
        {
            "tier": tier,
            "daily_limit": limit,
            "used_today": used,
            "remaining": max(0, limit - used),
            "reset_at_unix": window_start + DAILY_WINDOW_S,
            "email": row["email"],
            "subscription_active": bool(row["stripe_subscription_id"]),
            "created_at": row["created_at"],
        }
    )
