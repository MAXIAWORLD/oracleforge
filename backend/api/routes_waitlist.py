"""POST /api/waitlist — capture an email for the OracleForge beta drip.

Unauthenticated. Throttled by client IP via the same `register_limit` table
used by /api/register (1 attempt/60s) — the email goes straight to Loops.so;
no row is written in the local DB. Validation is intentionally permissive
(RFC-ish regex) because Loops will quality-check addresses on its end.
"""

from __future__ import annotations

import asyncio
import logging
import re

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from core.db import get_db
from core.disclaimer import wrap_error, wrap_with_disclaimer
from core.rate_limit import check_register
from services.email.loops_sync import add_contact

router = APIRouter(prefix="/api", tags=["waitlist"])
logger = logging.getLogger("maxia_oracle.waitlist")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USER_GROUP = "OracleForge Beta"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class WaitlistRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _normalize(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v) or len(v) > 254:
            raise ValueError("invalid email address")
        return v


@router.post("/waitlist")
async def waitlist(body: WaitlistRequest, request: Request) -> JSONResponse:
    db = get_db()
    decision = check_register(db, _client_ip(request))
    if not decision.allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=wrap_error(
                "waitlist throttled",
                limit=decision.limit,
                window_seconds=decision.window_s,
                retry_after_seconds=decision.retry_after,
            ),
            headers={"Retry-After": str(decision.retry_after)},
        )
    asyncio.create_task(add_contact(body.email, _USER_GROUP))
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=wrap_with_disclaimer(
            {
                "ok": True,
                "message": "You are on the list. We will email you when v0.2 ships.",
            }
        ),
    )
