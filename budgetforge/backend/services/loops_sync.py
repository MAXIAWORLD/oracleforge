"""Loops.so contact sync — fire-and-forget audience push.

Signup must NEVER fail because Loops is misconfigured or down. Every code path
returns a boolean and never raises. Errors are logged with masked email.
"""

from __future__ import annotations

import logging

import httpx

from core.config import settings
from core.log_utils import mask_email

logger = logging.getLogger(__name__)

_LOOPS_CREATE_URL = "https://app.loops.so/api/v1/contacts/create"
_TIMEOUT_S = 5.0


async def add_contact(email: str, user_group: str) -> bool:
    """Push a contact to Loops. Returns True on success or duplicate, False otherwise.

    Never raises. The signup flow can fire-and-forget this call.
    """
    api_key = getattr(settings, "loops_api_key", "") or ""
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
            logger.info("Loops contact added: %s (%s)", mask_email(email), user_group)
            return True
        if resp.status_code == 409:
            logger.info("Loops contact already on list: %s", mask_email(email))
            return True
        logger.warning(
            "Loops contact push returned %s for %s",
            resp.status_code,
            mask_email(email),
        )
        return False
    except Exception as exc:
        logger.warning("Loops contact push failed for %s: %s", mask_email(email), exc)
        return False
