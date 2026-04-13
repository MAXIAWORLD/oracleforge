"""GuardForge — Webhooks CRUD API.

Manages webhook URLs that receive notifications on high-risk PII detections.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_db
from core.models import Webhook

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["guard"])


# ── Auth ─────────────────────────────────────────────────────────

def _require_auth(x_api_key: str = Header(default="")) -> str:
    settings = get_settings()
    if not x_api_key or x_api_key != settings.secret_key:
        raise HTTPException(401, "Unauthorized — X-API-Key required")
    return x_api_key


_VALID_RISK = frozenset({"critical", "high", "medium", "low"})


class WebhookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="Human-readable name.")
    url: HttpUrl = Field(..., description="HTTPS endpoint that will receive POST notifications.")
    secret: str = Field(default="", max_length=255, description="Optional HMAC secret. If set, the dispatcher signs payloads with HMAC-SHA256.")
    min_risk_level: str = Field(default="critical", description="Minimum risk level to trigger this webhook (critical|high|medium|low).")
    enabled: bool = Field(default=True)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Slack security alerts",
                    "url": "https://hooks.slack.com/services/T00/B00/XXX",
                    "secret": "shared-hmac-secret",
                    "min_risk_level": "critical",
                    "enabled": True,
                }
            ]
        }
    }


def _row_to_response(row: Webhook) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "url": row.url,
        "has_secret": bool(row.secret),
        "min_risk_level": row.min_risk_level,
        "enabled": bool(row.enabled),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_triggered_at": row.last_triggered_at.isoformat() if row.last_triggered_at else None,
        "failure_count": row.failure_count,
    }


@router.get(
    "",
    summary="List all webhooks",
    description="Returns all registered webhooks. Secrets are NEVER returned in the response — only a `has_secret` boolean.",
)
async def list_webhooks(
    _: str = Depends(_require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    rows = (await session.execute(select(Webhook).order_by(Webhook.id))).scalars().all()
    return {"webhooks": [_row_to_response(r) for r in rows], "total": len(rows)}


@router.post(
    "",
    summary="Register a new webhook",
    description=(
        "Adds a new webhook to receive POST notifications when a scan triggers an event "
        "matching `min_risk_level`. The dispatcher fires asynchronously and is fail-tolerant: "
        "if your endpoint is down, the scan still succeeds.\n\n"
        "**Payload format**: `{event, risk_level, timestamp, scan_id, pii_count, pii_types, action, policy}`.\n\n"
        "**Signature**: if a secret is configured, the request includes "
        "`X-GuardForge-Signature: sha256=<hex>` computed as HMAC-SHA256(secret, body)."
    ),
    status_code=201,
)
async def create_webhook(
    body: WebhookCreate,
    _: str = Depends(_require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if body.min_risk_level not in _VALID_RISK:
        raise HTTPException(422, f"min_risk_level must be one of {sorted(_VALID_RISK)}")

    row = Webhook(
        name=body.name,
        url=str(body.url),
        secret=body.secret,
        min_risk_level=body.min_risk_level,
        enabled=1 if body.enabled else 0,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _row_to_response(row)


@router.delete(
    "/{webhook_id}",
    summary="Delete a webhook",
)
async def delete_webhook(
    webhook_id: int,
    _: str = Depends(_require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    row = (await session.execute(select(Webhook).where(Webhook.id == webhook_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, f"Webhook {webhook_id} not found")
    await session.delete(row)
    await session.commit()
    return {"deleted": True, "id": webhook_id}


@router.post(
    "/{webhook_id}/test",
    summary="Send a test event to a webhook",
    description="Fires a synthetic test event so you can verify the receiver is reachable.",
)
async def test_webhook(
    webhook_id: int,
    _: str = Depends(_require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    row = (await session.execute(select(Webhook).where(Webhook.id == webhook_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, f"Webhook {webhook_id} not found")

    from services.webhook_dispatcher import dispatch_event

    test_payload = {
        "scan_id": "test-event",
        "pii_count": 1,
        "pii_types": ["email"],
        "action": "block",
        "policy": "test",
        "test": True,
    }
    results = await dispatch_event(
        webhooks=[{
            "id": row.id,
            "name": row.name,
            "url": row.url,
            "secret": row.secret,
            "min_risk_level": "low",  # always trigger for test
            "enabled": True,
        }],
        event_type="webhook.test",
        risk_level="critical",
        payload=test_payload,
    )
    return {"results": results}
