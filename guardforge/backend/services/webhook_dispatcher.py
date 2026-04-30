"""GuardForge — Webhook dispatcher for high-risk PII events.

Sends POST notifications to user-registered URLs when a scan produces a
PII detection at or above a configured risk level. Fire-and-forget via
asyncio.create_task — never blocks the scan endpoint.

Each webhook may have an HMAC-SHA256 secret; if set, the dispatcher
includes an `X-GuardForge-Signature` header so the receiver can verify
the payload integrity.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Risk level ordering (must match pii_detector._RISK_ORDER)
_RISK_ORDER: dict[str, int] = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

# Strict 1-second timeout on all webhook calls.
# Dead URLs must not block the scan endpoint.
_HTTP_TIMEOUT = httpx.Timeout(timeout=1.0)


def _meets_threshold(actual: str, minimum: str) -> bool:
    """Return True if actual risk level is >= minimum threshold."""
    return _RISK_ORDER.get(actual, 0) >= _RISK_ORDER.get(minimum, 4)


def _sign_payload(secret: str, body: bytes) -> str:
    """Compute HMAC-SHA256 hex signature of the payload."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


async def _post_one(
    url: str,
    secret: str,
    payload: dict[str, Any],
    webhook_id: int,
) -> tuple[bool, str]:
    """POST a payload to a single webhook URL. Returns (success, message)."""
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "GuardForge-Webhook/0.1.0",
        "X-GuardForge-Event": payload.get("event", "unknown"),
    }
    if secret:
        headers["X-GuardForge-Signature"] = "sha256=" + _sign_payload(secret, body)
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            res = await client.post(url, content=body, headers=headers)
            if res.status_code >= 400:
                return False, f"HTTP {res.status_code}"
            return True, f"HTTP {res.status_code}"
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        logger.warning(
            "[webhook] timeout/connection error for %s: %s", url, type(exc).__name__
        )
        return False, f"connection error: {type(exc).__name__}"
    except httpx.HTTPError as exc:
        logger.warning("[webhook] http error for %s: %s", url, type(exc).__name__)
        return False, f"transport error: {type(exc).__name__}"


async def dispatch_event(
    webhooks: list[dict[str, Any]],
    event_type: str,
    risk_level: str,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Dispatch an event to all matching webhooks in parallel.

    Args:
        webhooks: List of webhook dicts (id, name, url, secret, min_risk_level, enabled).
        event_type: e.g. 'scan.high_risk', 'tokenize.critical'.
        risk_level: actual risk of the event (critical/high/medium/low).
        payload: event-specific data merged into the webhook body.

    Returns:
        List of dispatch results: [{webhook_id, ok, message}, ...]
    """
    body = {
        "event": event_type,
        "risk_level": risk_level,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        **payload,
    }

    matching = [
        w
        for w in webhooks
        if w.get("enabled")
        and _meets_threshold(risk_level, w.get("min_risk_level", "critical"))
    ]
    if not matching:
        return []

    tasks = [_post_one(w["url"], w.get("secret", ""), body, w["id"]) for w in matching]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    out = []
    for w, (ok, msg) in zip(matching, results):
        if not ok:
            logger.warning(
                "[webhook] dispatch failed for %s (id=%d): %s",
                w.get("name"),
                w["id"],
                msg,
            )
        out.append({"webhook_id": w["id"], "ok": ok, "message": msg})
    return out
