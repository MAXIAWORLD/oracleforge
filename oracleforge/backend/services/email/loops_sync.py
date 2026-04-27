"""Loops.so contact sync — fire-and-forget audience push for the waitlist.

The waitlist endpoint must NEVER fail because Loops is misconfigured or down.
Every code path returns a boolean and never raises. The LOOPS_API_KEY env var
is read at call time so tests and ops can flip it without restarting.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger("maxia_oracle.loops")

_LOOPS_CREATE_URL = "https://app.loops.so/api/v1/contacts/create"
_TIMEOUT_S = 5.0


def _mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        return f"{local[:1]}***@{domain}"
    return f"{local[:2]}***@{domain}"


async def add_contact(email: str, user_group: str) -> bool:
    """Push a contact to Loops. Returns True on 200/201/409, False otherwise.

    Never raises. The waitlist endpoint can fire-and-forget this call.
    """
    api_key = os.getenv("LOOPS_API_KEY", "").strip()
    if not api_key:
        return False

    payload = {"email": email, "userGroup": user_group, "source": user_group}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.post(_LOOPS_CREATE_URL, headers=headers, json=payload)
        if resp.status_code in (200, 201):
            logger.info("Loops contact added: %s (%s)", _mask_email(email), user_group)
            return True
        if resp.status_code == 409:
            logger.info("Loops contact already on list: %s", _mask_email(email))
            return True
        logger.warning(
            "Loops contact push returned %s for %s",
            resp.status_code,
            _mask_email(email),
        )
        return False
    except Exception as exc:
        logger.warning("Loops contact push failed for %s: %s", _mask_email(email), exc)
        return False
