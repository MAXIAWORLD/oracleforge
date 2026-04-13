"""GuardForge — Compliance Reports API routes.

Provides aggregated scan statistics for CISO/DPO reporting:
  - GET /api/reports/summary  — totals, pii by type, risk distribution
  - GET /api/reports/timeline — time-series of scans and pii detections
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_db
from core.models import ScanLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])


# ── Auth ─────────────────────────────────────────────────────────

def _require_auth(x_api_key: str = Header(default="")) -> str:
    settings = get_settings()
    if not x_api_key or x_api_key != settings.secret_key:
        raise HTTPException(401, "Unauthorized — X-API-Key required")
    return x_api_key


# ── Helpers ──────────────────────────────────────────────────────

def _parse_date(value: str | None, default: date) -> datetime:
    """Parse YYYY-MM-DD string to UTC-aware datetime at midnight."""
    if not value:
        return datetime(default.year, default.month, default.day, tzinfo=timezone.utc)
    try:
        d = date.fromisoformat(value)
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    except ValueError as exc:
        raise HTTPException(422, f"Invalid date format: '{value}'. Expected YYYY-MM-DD.") from exc


def _date_key(dt: datetime | None, granularity: str) -> str:
    """Format a datetime as YYYY-MM-DD or YYYY-MM-DDTHH for time-series."""
    if dt is None:
        return "unknown"
    if granularity == "hour":
        return dt.strftime("%Y-%m-%dT%H")
    return dt.strftime("%Y-%m-%d")


# ── Endpoints ────────────────────────────────────────────────────

@router.get(
    "/summary",
    summary="Compliance summary for a date range",
    description=(
        "Aggregates the persistent audit trail to produce a CISO/DPO-ready compliance summary "
        "over the given date range. Returns total scan count, total PII items detected, breakdown "
        "by PII type, breakdown by action taken (block/anonymize/warn/tokenize), breakdown by risk "
        "level (critical/high/medium/low), and the most-used policies.\n\n"
        "**Date params**: `from_date` and `to_date` accept ISO format `YYYY-MM-DD`. Both are optional "
        "— defaults are 30 days ago and today.\n\n"
        "Used by the dashboard `/reports` page and exportable as JSON for compliance audits."
    ),
    responses={
        200: {"description": "Returns period, totals, pii_by_type, action_distribution, risk_distribution, top_policies."},
        401: {"description": "Missing or invalid X-API-Key."},
        422: {"description": "Invalid date format (must be YYYY-MM-DD)."},
        500: {"description": "Internal error querying the audit log."},
    },
)
async def get_summary(
    from_date: str | None = None,
    to_date: str | None = None,
    _: str = Depends(_require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return compliance summary for a date range.

    Query params:
        from_date: YYYY-MM-DD (default: 30 days ago)
        to_date:   YYYY-MM-DD (default: today)
    """
    today = date.today()
    from_dt = _parse_date(from_date, date(today.year, today.month, max(1, today.day - 30)))
    to_dt_base = _parse_date(to_date, today)
    to_dt = to_dt_base.replace(hour=23, minute=59, second=59)

    pii_by_type: dict[str, int] = defaultdict(int)
    action_distribution: dict[str, int] = defaultdict(int)
    risk_distribution: dict[str, int] = defaultdict(int)
    policy_counts: dict[str, int] = defaultdict(int)
    total_scans = 0
    total_pii = 0

    try:
        stmt = select(ScanLog).where(
            ScanLog.scanned_at >= from_dt,
            ScanLog.scanned_at <= to_dt,
        )
        rows = (await session.execute(stmt)).scalars().all()

        for row in rows:
            total_scans += 1
            total_pii += row.pii_found

            # Parse pii_types (stored as JSON array or comma-separated)
            try:
                types = json.loads(row.pii_types) if row.pii_types else []
            except (json.JSONDecodeError, ValueError):
                types = [t.strip() for t in row.pii_types.split(",") if t.strip()]
            for t in types:
                pii_by_type[t] += 1

            action_distribution[row.action_taken] += 1
            risk_distribution[row.risk_level] += 1
            policy_counts[row.policy_applied] += 1

    except Exception as exc:
        logger.error("[reports] summary query failed: %s", exc)
        raise HTTPException(500, "Failed to query audit log") from exc

    top_policies = sorted(
        [{"name": k, "count": v} for k, v in policy_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )

    return {
        "period": {
            "from": from_dt.strftime("%Y-%m-%d"),
            "to": to_dt_base.strftime("%Y-%m-%d"),
        },
        "total_scans": total_scans,
        "total_pii_detected": total_pii,
        "pii_by_type": dict(pii_by_type),
        "action_distribution": dict(action_distribution),
        "risk_distribution": dict(risk_distribution),
        "top_policies": top_policies,
    }


@router.get(
    "/timeline",
    summary="Time-series of scans and PII detections",
    description=(
        "Returns a time-series of scan counts and PII detection counts bucketed by day or hour. "
        "Used by the dashboard `/reports` page to render line charts.\n\n"
        "**Granularity**: 'day' or 'hour'. For 'hour', use a narrower date range (1-7 days) to "
        "avoid hundreds of buckets.\n\n"
        "**Empty buckets**: only buckets with data are included in the response. Render gaps in "
        "the client side if you want continuous time-series."
    ),
    responses={
        200: {"description": "Returns period, granularity, and series array."},
        401: {"description": "Missing or invalid X-API-Key."},
        422: {"description": "Invalid date format or invalid granularity."},
        500: {"description": "Internal error querying the audit log."},
    },
)
async def get_timeline(
    from_date: str | None = None,
    to_date: str | None = None,
    granularity: str = "day",
    _: str = Depends(_require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return time-series of scans and PII detections.

    Query params:
        from_date:   YYYY-MM-DD (default: 7 days ago)
        to_date:     YYYY-MM-DD (default: today)
        granularity: 'day' or 'hour' (default: day)
    """
    if granularity not in ("day", "hour"):
        raise HTTPException(422, "granularity must be 'day' or 'hour'")

    today = date.today()
    from_dt = _parse_date(from_date, date(today.year, today.month, max(1, today.day - 7)))
    to_dt_base = _parse_date(to_date, today)
    to_dt = to_dt_base.replace(hour=23, minute=59, second=59)

    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"scans": 0, "pii": 0})

    try:
        stmt = select(ScanLog).where(
            ScanLog.scanned_at >= from_dt,
            ScanLog.scanned_at <= to_dt,
        )
        rows = (await session.execute(stmt)).scalars().all()

        for row in rows:
            key = _date_key(row.scanned_at, granularity)
            buckets[key]["scans"] += 1
            buckets[key]["pii"] += row.pii_found

    except Exception as exc:
        logger.error("[reports] timeline query failed: %s", exc)
        raise HTTPException(500, "Failed to query audit log") from exc

    # Build sorted series
    date_field = "date" if granularity == "day" else "hour"
    series = sorted(
        [{date_field: k, "scans": v["scans"], "pii": v["pii"]} for k, v in buckets.items()],
        key=lambda x: x[date_field],
    )

    return {
        "period": {
            "from": from_dt.strftime("%Y-%m-%d"),
            "to": to_dt_base.strftime("%Y-%m-%d"),
        },
        "granularity": granularity,
        "series": series,
    }
