"""V1.9 — Price alerts CRUD + SSE price streaming.

Alert routes do NOT consume daily quota — they are management endpoints.
The SSE streaming endpoint also does NOT consume quota (it's a long-lived
connection, charging per-tick would drain the free tier instantly).
"""
from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from core.auth import require_api_key
from core.config import ALERTS_MAX_PER_KEY, STREAM_MAX_SYMBOLS
from core.db import (
    count_active_alerts,
    create_alert,
    delete_alert,
    get_alert,
    get_db,
    list_alerts,
)
from core.disclaimer import wrap_error, wrap_with_disclaimer
from services.oracle.alerts import validate_callback_url
from services.oracle.price_stream import price_event_generator

router = APIRouter(prefix="/api", tags=["alerts"])

_SYMBOL_REGEX = re.compile(r"^[A-Z0-9]{1,10}$")


def _is_valid_symbol(symbol: str) -> bool:
    return bool(_SYMBOL_REGEX.match(symbol))


# ── Alert models ──────────────────────────────────────────────────────────────


class AlertCreateRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10)
    condition: Literal["above", "below"]
    threshold: float = Field(..., gt=0)
    callback_url: str = Field(..., min_length=10, max_length=2048)

    @field_validator("symbol")
    @classmethod
    def _uppercase(cls, v: str) -> str:
        return v.strip().upper()


# ── Alert routes ──────────────────────────────────────────────────────────────


@router.post("/alerts", status_code=status.HTTP_201_CREATED)
async def create_alert_route(
    body: AlertCreateRequest,
    key_hash: str = Depends(require_api_key),
):
    """Create a price alert. One-shot: triggers once then deactivates."""
    if not _is_valid_symbol(body.symbol):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error("invalid symbol format"),
        )

    url_err = validate_callback_url(body.callback_url)
    if url_err is not None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error(url_err),
        )

    db = get_db()
    active_count = count_active_alerts(db, key_hash)
    if active_count >= ALERTS_MAX_PER_KEY:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=wrap_error(
                "alert quota exceeded",
                limit=ALERTS_MAX_PER_KEY,
                active=active_count,
            ),
        )

    alert_id = create_alert(
        db,
        key_hash=key_hash,
        symbol=body.symbol,
        condition=body.condition,
        threshold=body.threshold,
        callback_url=body.callback_url,
    )

    return wrap_with_disclaimer(
        {
            "id": alert_id,
            "symbol": body.symbol,
            "condition": body.condition,
            "threshold": body.threshold,
            "active": True,
        }
    )


@router.get("/alerts")
async def list_alerts_route(
    key_hash: str = Depends(require_api_key),
):
    """List all alerts for the authenticated key."""
    db = get_db()
    alerts = list_alerts(db, key_hash, active_only=False)
    return wrap_with_disclaimer({"alerts": alerts, "count": len(alerts)})


@router.delete("/alerts/{alert_id}")
async def delete_alert_route(
    alert_id: int,
    key_hash: str = Depends(require_api_key),
):
    """Delete an alert by id."""
    db = get_db()
    deleted = delete_alert(db, alert_id, key_hash)
    if not deleted:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=wrap_error("alert not found or not owned by this key"),
        )
    return wrap_with_disclaimer({"deleted": True, "id": alert_id})


# ── SSE streaming ────────────────────────────────────────────────────────────


@router.get("/prices/stream")
async def stream_prices(
    symbols: str = Query(
        ...,
        description="Comma-separated symbols (max 10), e.g. BTC,ETH,SOL",
    ),
    key_hash: str = Depends(require_api_key),
):
    """SSE stream of live prices, polled every ~3 seconds.

    Does not consume daily quota. Auto-closes after 1 hour.
    """
    raw_symbols = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not raw_symbols:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error("at least one symbol is required"),
        )
    if len(raw_symbols) > STREAM_MAX_SYMBOLS:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=wrap_error(
                f"max {STREAM_MAX_SYMBOLS} symbols per stream",
                requested=len(raw_symbols),
            ),
        )
    for sym in raw_symbols:
        if not _is_valid_symbol(sym):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=wrap_error("invalid symbol format", symbol=sym),
            )

    seen: set[str] = set()
    dedup: list[str] = []
    for sym in raw_symbols:
        if sym not in seen:
            seen.add(sym)
            dedup.append(sym)

    return StreamingResponse(
        price_event_generator(dedup),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
