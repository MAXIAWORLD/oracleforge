"""POST /api/register — issue a new free-tier API key.

Unauthenticated but throttled by client IP (1 registration / 60s) to prevent
mass-minting of keys. The raw key is returned EXACTLY ONCE in the response
body — we never store it. If the client loses it, they regenerate.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from core.auth import issue_key
from core.db import get_db
from core.disclaimer import wrap_error, wrap_with_disclaimer
from core.rate_limit import check_register

router = APIRouter(prefix="/api", tags=["register"])
logger = logging.getLogger("maxia_oracle.register")


def _client_ip(request: Request) -> str:
    """Return the best-effort client IP, trusting X-Forwarded-For only when set.

    In Phase 7 the nginx vhost will inject X-Forwarded-For with exactly one
    hop (the remote peer), and we trust it here. If the header is missing,
    fall back to the socket peer address.
    """
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/register")
async def register(request: Request) -> JSONResponse:
    """Issue a new free-tier key. Returns the raw key once; never persisted."""
    db = get_db()
    decision = check_register(db, _client_ip(request))
    if not decision.allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=wrap_error(
                "registration throttled",
                limit=decision.limit,
                window_seconds=decision.window_s,
                retry_after_seconds=decision.retry_after,
            ),
            headers={"Retry-After": str(decision.retry_after)},
        )

    try:
        raw_key = issue_key(db)
    except Exception as exc:
        logger.error("Failed to issue API key", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to issue API key",
        ) from exc

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=wrap_with_disclaimer(
            {
                "api_key": raw_key,
                "tier": "free",
                "daily_limit": 100,
                "usage": "Send the key as X-API-Key header on every request. Store it safely — it is shown only once.",
            }
        ),
    )
