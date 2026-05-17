"""POST /api/key-email — attach an email to an existing free key.

Optional step shown after key generation. Lets users receive their key
by email and opt into product updates without blocking the free flow.
"""
from __future__ import annotations

import asyncio
import logging
import re

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from core.auth import hash_key
from core.db import get_db
from core.disclaimer import wrap_error, wrap_with_disclaimer
from services.email.loops_sync import add_contact

router = APIRouter(prefix="/api", tags=["key-email"])
logger = logging.getLogger("maxia_oracle.key_email")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USER_GROUP = "OracleForge Free Key"



class KeyEmailRequest(BaseModel):
    email: str
    api_key: str

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v) or len(v) > 254:
            raise ValueError("invalid email address")
        return v

    @field_validator("api_key")
    @classmethod
    def _validate_key(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("mxo_") or len(v) < 10:
            raise ValueError("invalid api key format")
        return v


@router.post("/key-email")
async def attach_email(body: KeyEmailRequest) -> JSONResponse:
    db = get_db()
    key_hash = hash_key(body.api_key)

    # Check key exists
    row = db.execute(
        "SELECT email FROM api_keys WHERE key_hash = ? AND active = 1",
        (key_hash,),
    ).fetchone()
    if row is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=wrap_error("key not found"),
        )

    # Attach email if not already set (idempotent)
    if row[0] is None:
        db.execute(
            "UPDATE api_keys SET email = ? WHERE key_hash = ?",
            (body.email, key_hash),
        )

    asyncio.create_task(add_contact(body.email, _USER_GROUP))
    logger.info("Email attached key=%s…", key_hash[:8])

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=wrap_with_disclaimer({"ok": True}),
    )
