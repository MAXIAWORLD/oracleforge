"""V1.9 — Price alert evaluation and webhook delivery.

Checks active alerts against sampled prices in the background sampler
loop (every HISTORY_SAMPLE_INTERVAL_S). When an alert condition is met,
fires a one-shot webhook POST and deactivates the alert.

SSRF protection: callback_url must be HTTPS and the hostname must not
resolve to a private/loopback address.
"""
from __future__ import annotations

import ipaddress
import logging
import re
import socket
from typing import Any, Final
from urllib.parse import urlparse

from core.config import ALERTS_WEBHOOK_TIMEOUT_S

logger = logging.getLogger("maxia_oracle.alerts")

_HTTPS_PATTERN: Final[re.Pattern[str]] = re.compile(r"^https://", re.IGNORECASE)
_MAX_URL_LENGTH: Final[int] = 2048


def validate_callback_url(url: str) -> str | None:
    """Validate a webhook callback URL. Returns error message or None if valid."""
    if not url or not isinstance(url, str):
        return "callback_url is required"
    if len(url) > _MAX_URL_LENGTH:
        return f"callback_url exceeds {_MAX_URL_LENGTH} characters"
    if not _HTTPS_PATTERN.match(url):
        return "callback_url must use HTTPS"

    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return "callback_url has no hostname"

    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return "callback_url must not target localhost"

    try:
        resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _, _, _, _, sockaddr in resolved:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return "callback_url resolves to a private/reserved IP"
    except (socket.gaierror, ValueError):
        return "callback_url hostname could not be resolved"

    return None


def evaluate_alert(
    condition: str,
    threshold: float,
    current_price: float,
) -> bool:
    """Check if a price alert condition is met."""
    if condition == "above":
        return current_price >= threshold
    if condition == "below":
        return current_price <= threshold
    return False


async def fire_webhook(
    callback_url: str,
    payload: dict[str, Any],
) -> bool:
    """POST the alert payload to the callback URL. Returns True on success."""
    from core.http_client import get_http_client

    try:
        client = await get_http_client()
        resp = await client.post(
            callback_url,
            json=payload,
            timeout=ALERTS_WEBHOOK_TIMEOUT_S,
            follow_redirects=False,
        )
        if 200 <= resp.status_code < 300:
            logger.info("Webhook delivered to %s (status=%d)", callback_url, resp.status_code)
            return True
        logger.warning("Webhook failed %s (status=%d)", callback_url, resp.status_code)
        return False
    except Exception:
        logger.warning("Webhook delivery error for %s", callback_url, exc_info=True)
        return False


async def check_and_fire_alerts(
    prices: dict[str, dict[str, Any]],
) -> int:
    """Evaluate all active alerts against current prices. Returns count triggered."""
    from core.db import get_all_active_alerts, get_db, trigger_alert

    db = get_db()
    active = get_all_active_alerts(db)
    if not active:
        return 0

    triggered = 0
    for alert in active:
        sym = alert["symbol"]
        price_data = prices.get(sym)
        if price_data is None:
            continue
        current_price = price_data.get("price") if isinstance(price_data, dict) else None
        if not current_price or current_price <= 0:
            continue

        if evaluate_alert(alert["condition"], alert["threshold"], current_price):
            trigger_alert(db, alert["id"])
            triggered += 1

            payload = {
                "alert_id": alert["id"],
                "symbol": sym,
                "condition": alert["condition"],
                "threshold": alert["threshold"],
                "triggered_price": current_price,
                "service": "maxia-oracle",
                "disclaimer": "Data feed only. Not investment advice. No custody. No KYC.",
            }
            await fire_webhook(alert["callback_url"], payload)

    if triggered > 0:
        logger.info("Triggered %d alert(s)", triggered)
    return triggered
