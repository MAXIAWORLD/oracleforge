"""Stripe billing service — checkout, webhook signature, event handlers (V2.3).

The official `stripe` Python SDK is intentionally NOT a dependency. The
five HTTPS calls we need (create checkout session, create billing portal
session, list customers by email) are simple form-encoded POSTs that we
issue directly via httpx. Removing the SDK keeps the install graph small
and makes it trivial to audit what hits Stripe's API.

Webhook signature verification is implemented from the spec
(https://stripe.com/docs/webhooks/signatures) using `hmac.compare_digest`.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import sqlite3
from typing import Any, Final
from urllib.parse import urlencode

import httpx

from core import config
from core.auth import generate_key
from core.billing_tiers import (
    DEV_TIER,
    FREE_TIER,
    PRO_TIER,
    quota_for_tier,
)
from core.db import insert_pending_key, now_unix, rotate_api_key
from services.email import transactional

logger = logging.getLogger("maxia_oracle.stripe")

_STRIPE_API_BASE: Final[str] = "https://api.stripe.com/v1"
_HTTP_TIMEOUT_S: Final[float] = 10.0

# Stripe rejects signatures whose timestamp is older than 5 minutes by
# default — we mirror that constraint here.
_SIGNATURE_TOLERANCE_S: Final[int] = 300

# Tiers that webhook handlers will accept in metadata.tier. Anything else
# is silently downgraded to no-op (prevents a malicious operator from
# escalating a key by injecting tier=godmode).
_PAID_TIERS: Final[frozenset[str]] = frozenset({DEV_TIER, PRO_TIER})


# ══════════════════════════════════════════════════════════════════════════
# ── Webhook signature verification ──
# ══════════════════════════════════════════════════════════════════════════


def verify_signature(
    payload: bytes,
    signature_header: str,
    secret: str,
    *,
    tolerance_s: int = _SIGNATURE_TOLERANCE_S,
) -> bool:
    """Validate Stripe-Signature header against the raw request body.

    Header format: ``t=1234567890,v1=hex,v1=hex_alt`` (multiple v1 values
    can be present during signing-secret rotation). Returns True if at
    least one v1 hex matches HMAC-SHA256(secret, "<t>.<payload>") and
    `t` is within `tolerance_s` of the current time.

    Never raises — always returns a bool so the caller can 400 cleanly.
    """
    if not signature_header or not secret:
        return False
    try:
        parts = dict(
            seg.split("=", 1) for seg in signature_header.split(",") if "=" in seg
        )
    except ValueError:
        return False

    timestamp_raw = parts.get("t")
    if not timestamp_raw:
        return False
    try:
        timestamp = int(timestamp_raw)
    except ValueError:
        return False

    if abs(now_unix() - timestamp) > tolerance_s:
        return False

    candidate_signatures = [
        value
        for key, value in (
            seg.split("=", 1) for seg in signature_header.split(",") if "=" in seg
        )
        if key == "v1"
    ]
    if not candidate_signatures:
        return False

    signed_payload = f"{timestamp}.".encode() + payload
    expected = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    return any(hmac.compare_digest(expected, sig) for sig in candidate_signatures)


# ══════════════════════════════════════════════════════════════════════════
# ── HTTP helpers ──
# ══════════════════════════════════════════════════════════════════════════


def _flatten_form(data: dict[str, Any], prefix: str = "") -> list[tuple[str, str]]:
    """Convert nested dict to Stripe's bracketed form encoding.

    Stripe expects ``metadata[key]=value``, ``line_items[0][price]=...``,
    ``payment_method_types[0]=card`` rather than JSON. List-of-dict encodes
    with positional indices (``[0]``, ``[1]``, …); list-of-scalar uses the
    same indexing for consistency with Stripe's parser.
    """
    items: list[tuple[str, str]] = []
    for key, value in data.items():
        full_key = f"{prefix}[{key}]" if prefix else key
        if isinstance(value, dict):
            items.extend(_flatten_form(value, full_key))
        elif isinstance(value, (list, tuple)):
            for idx, elt in enumerate(value):
                indexed_key = f"{full_key}[{idx}]"
                if isinstance(elt, dict):
                    items.extend(_flatten_form(elt, indexed_key))
                elif elt is None:
                    continue
                else:
                    items.append((indexed_key, str(elt)))
        elif value is None:
            continue
        else:
            items.append((full_key, str(value)))
    return items


async def _stripe_post(path: str, data: dict[str, Any]) -> dict[str, Any]:
    """POST form-encoded data to the Stripe REST API. Raises on non-2xx.

    httpx 0.27.x has a bug where passing `data=[(k,v),...]` to AsyncClient.post
    triggers a "sync request with AsyncClient" RuntimeError. We side-step it by
    serialising the form body ourselves with `urllib.parse.urlencode` and
    posting it as a raw byte body via `content=`.
    """
    if not config.STRIPE_SECRET_KEY:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured")
    body = urlencode(_flatten_form(data)).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {config.STRIPE_SECRET_KEY}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_S) as client:
        resp = await client.post(
            f"{_STRIPE_API_BASE}{path}",
            headers=headers,
            content=body,
        )
    if resp.status_code >= 400:
        # Stripe always returns JSON {error: {message, code, ...}}
        try:
            err = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            err = resp.text
        raise RuntimeError(f"Stripe {path} failed ({resp.status_code}): {err}")
    return resp.json()


async def _stripe_get(
    path: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    if not config.STRIPE_SECRET_KEY:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured")
    headers = {"Authorization": f"Bearer {config.STRIPE_SECRET_KEY}"}
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_S) as client:
        resp = await client.get(
            f"{_STRIPE_API_BASE}{path}", headers=headers, params=params
        )
    if resp.status_code >= 400:
        try:
            err = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            err = resp.text
        raise RuntimeError(f"Stripe GET {path} failed ({resp.status_code}): {err}")
    return resp.json()


# ══════════════════════════════════════════════════════════════════════════
# ── Checkout session ──
# ══════════════════════════════════════════════════════════════════════════


async def create_checkout_session(
    *,
    price_id: str,
    key_hash: str,
    tier: str,
    success_url: str,
    cancel_url: str,
    customer_email: str | None = None,
) -> dict[str, Any]:
    """Create a Stripe Checkout session in subscription mode.

    metadata.key_hash + metadata.tier carry the link back to api_keys so the
    webhook handler can flip the tier. customer_email pre-fills the email
    field for new buyers; existing customers use a returned-customer flow on
    the Stripe-hosted page.

    `payment_method_types` includes "card" + "crypto" — Stripe Pay with
    Crypto must be enabled in the dashboard. Stripe silently ignores
    "crypto" if the account hasn't activated it.
    """
    data: dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {"key_hash": key_hash, "tier": tier},
        "subscription_data": {
            "metadata": {"key_hash": key_hash, "tier": tier},
        },
        "allow_promotion_codes": "true",
    }
    if customer_email:
        data["customer_email"] = customer_email
    # Send line_items as a flat repeated form key — the helper handles list-of-dict.
    return await _stripe_post("/checkout/sessions", data)


async def create_billing_portal_session(
    *, customer_id: str, return_url: str
) -> dict[str, Any]:
    """Create a Stripe-hosted billing portal session URL for `customer_id`."""
    return await _stripe_post(
        "/billing_portal/sessions",
        {"customer": customer_id, "return_url": return_url},
    )


async def find_customer_by_email(email: str) -> str | None:
    """Return the Stripe customer_id for `email`, or None if not found."""
    if not email:
        return None
    result = await _stripe_get("/customers", {"email": email, "limit": 1})
    items = result.get("data") or []
    if not items:
        return None
    return items[0].get("id")


# ══════════════════════════════════════════════════════════════════════════
# ── Event handler — checkout.session.completed / subscription.deleted ──
# ══════════════════════════════════════════════════════════════════════════


def _record_event(db: sqlite3.Connection, event_id: str, event_type: str) -> bool:
    """Insert (event_id, event_type) into stripe_events. Return False on replay."""
    cursor = db.execute(
        "INSERT OR IGNORE INTO stripe_events (event_id, event_type, received_at) "
        "VALUES (?, ?, ?)",
        (event_id, event_type, now_unix()),
    )
    return cursor.rowcount == 1


def handle_event(db: sqlite3.Connection, event: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a verified Stripe event to the right handler.

    Returns a small dict suitable for embedding in the webhook ack response
    (the webhook itself always returns 200 unless the signature was wrong).

    Idempotency: each event_id is recorded once in `stripe_events`. A replay
    is a no-op that returns ``{"status": "duplicate"}``.
    """
    event_id = event.get("id") or ""
    event_type = event.get("type") or ""
    if not event_id or not event_type:
        return {"status": "ignored", "reason": "missing id/type"}

    if not _record_event(db, event_id, event_type):
        logger.info("Stripe replay ignored: %s (%s)", event_id, event_type)
        return {"status": "duplicate", "event_id": event_id}

    obj = (event.get("data") or {}).get("object") or {}

    if event_type == "checkout.session.completed":
        return _handle_checkout_completed(db, obj)
    if event_type == "customer.subscription.deleted":
        return _handle_subscription_deleted(db, obj)
    if event_type == "customer.subscription.updated":
        return _handle_subscription_updated(db, obj)
    if event_type == "invoice.payment_failed":
        return _handle_payment_failed(db, obj)

    logger.info("Stripe event ignored: %s", event_type)
    return {"status": "ignored", "event_type": event_type}


def _extract_metadata(obj: dict[str, Any]) -> dict[str, str]:
    metadata = obj.get("metadata") or {}
    return {str(k): str(v) for k, v in metadata.items() if v is not None}


def _handle_checkout_completed(
    db: sqlite3.Connection, session: dict[str, Any]
) -> dict[str, Any]:
    """V2.5 flow:
        1. Validate metadata (tier, key_hash from Checkout creation)
        2. Generate a *fresh* raw API key + hash (rotation)
        3. Atomically replace the row's key_hash, set tier + stripe ids + email
        4. Park the new raw key in `pending_key_delivery` keyed by session.id
           so the success page can fetch it once
        5. Send the welcome-paid email with the new raw key (best-effort)

    Why rotate at checkout completion?
        The raw key was generated client-side at /api/register or in the
        checkout JS, and the server only ever sees the SHA256 hash. We
        cannot reconstruct the raw key to email it to the customer. By
        rotating, we get a fresh raw value owned end-to-end by the server
        and can deliver it via two redundant channels: the email (canonical)
        and the success page (immediate UX).
    """
    metadata = _extract_metadata(session)
    old_key_hash = metadata.get("key_hash") or ""
    tier = (metadata.get("tier") or "").lower()

    if tier not in _PAID_TIERS:
        logger.warning(
            "checkout.session.completed with unknown tier=%r — ignoring", tier
        )
        return {"status": "ignored", "reason": "invalid tier"}

    if not old_key_hash:
        return {"status": "ignored", "reason": "missing key_hash"}

    session_id = session.get("id") or ""
    customer_id = session.get("customer") or ""
    subscription_id = session.get("subscription") or ""
    customer_email = (
        (session.get("customer_details") or {}).get("email")
        or session.get("customer_email")
        or ""
    )

    new_raw_key, new_key_hash = generate_key()

    rotated = rotate_api_key(
        db,
        old_key_hash=old_key_hash,
        new_key_hash=new_key_hash,
        tier=tier,
        stripe_customer_id=customer_id or None,
        stripe_subscription_id=subscription_id or None,
        email=customer_email or None,
    )
    if not rotated:
        logger.warning(
            "checkout.session.completed for unknown key_hash=%s…",
            old_key_hash[:16],
        )
        return {"status": "ignored", "reason": "unknown key_hash"}

    if session_id:
        insert_pending_key(db, session_id=session_id, raw_key=new_raw_key)

    email_sent = False
    if customer_email:
        try:
            email_sent = transactional.send_welcome_paid(
                to_email=customer_email,
                tier=tier,
                api_key=new_raw_key,
                daily_limit=quota_for_tier(tier),
            )
        except Exception:
            logger.warning(
                "welcome email crashed (will fall back to success page)",
                exc_info=True,
            )

    logger.info(
        "Upgraded key=%s… to tier=%s (cust=%s sub=%s, email_sent=%s)",
        old_key_hash[:16],
        tier,
        customer_id,
        subscription_id,
        email_sent,
    )
    return {
        "status": "upgraded",
        "tier": tier,
        "customer_id": customer_id,
        "subscription_id": subscription_id,
        "email": customer_email or None,
        "session_id": session_id,
        "email_sent": email_sent,
        "rotated": True,
    }


def _handle_subscription_deleted(
    db: sqlite3.Connection, sub: dict[str, Any]
) -> dict[str, Any]:
    subscription_id = sub.get("id") or ""
    if not subscription_id:
        return {"status": "ignored", "reason": "missing subscription id"}

    cursor = db.execute(
        "UPDATE api_keys "
        "SET tier = ?, stripe_subscription_id = NULL "
        "WHERE stripe_subscription_id = ?",
        (FREE_TIER, subscription_id),
    )
    logger.info(
        "Downgraded %d key(s) to free for subscription=%s",
        cursor.rowcount,
        subscription_id,
    )
    return {"status": "downgraded", "rows": cursor.rowcount}


def _handle_subscription_updated(
    db: sqlite3.Connection, sub: dict[str, Any]
) -> dict[str, Any]:
    """Sync tier on plan-change events (e.g. Dev → Pro upgrade in the portal).

    Tier is read from subscription.metadata.tier (we set it at checkout
    creation, and Stripe preserves metadata across updates). When absent
    or invalid, we leave the row untouched — the source of truth is the
    portal "change plan" flow, not arbitrary updates.
    """
    metadata = _extract_metadata(sub)
    tier = (metadata.get("tier") or "").lower()
    subscription_id = sub.get("id") or ""
    status = (sub.get("status") or "").lower()

    if status in {"canceled", "incomplete_expired", "unpaid"}:
        return _handle_subscription_deleted(db, sub)

    if tier not in _PAID_TIERS or not subscription_id:
        return {"status": "ignored", "reason": "no actionable change"}

    cursor = db.execute(
        "UPDATE api_keys SET tier = ? WHERE stripe_subscription_id = ?",
        (tier, subscription_id),
    )
    logger.info(
        "Updated subscription=%s to tier=%s (rows=%d)",
        subscription_id,
        tier,
        cursor.rowcount,
    )
    return {"status": "updated", "tier": tier, "rows": cursor.rowcount}


def _handle_payment_failed(
    db: sqlite3.Connection, invoice: dict[str, Any]
) -> dict[str, Any]:
    """Log only — Stripe will retry then trigger subscription.deleted on its own."""
    sub_id = invoice.get("subscription") or ""
    logger.warning("Stripe invoice.payment_failed for subscription=%s", sub_id)
    return {"status": "logged", "subscription_id": sub_id}
