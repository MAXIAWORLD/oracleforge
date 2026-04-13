"""GuardForge — Custom entities CRUD API.

Allows users to define their own PII patterns (regex) at runtime, persisted
in the `custom_entities` table. Patterns are loaded into the live PIIDetector
on every CRUD operation so changes take effect immediately.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_db
from core.models import CustomEntity
from services.pii_detector import CustomPattern, PIIDetector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/entities", tags=["guard"])


# ── Auth ─────────────────────────────────────────────────────────

def _require_auth(x_api_key: str = Header(default="")) -> str:
    settings = get_settings()
    if not x_api_key or x_api_key != settings.secret_key:
        raise HTTPException(401, "Unauthorized — X-API-Key required")
    return x_api_key


# ── Validation ───────────────────────────────────────────────────

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
_VALID_RISK = frozenset({"critical", "high", "medium", "low"})
_MAX_PATTERN_LEN = 2000


def _validate_pattern(pattern: str) -> re.Pattern[str]:
    """Compile and sanity-check a user-provided regex pattern."""
    if len(pattern) > _MAX_PATTERN_LEN:
        raise HTTPException(422, f"Pattern exceeds {_MAX_PATTERN_LEN} character limit")
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise HTTPException(422, f"Invalid regex: {exc}") from exc
    return compiled


# ── Schemas ──────────────────────────────────────────────────────

class EntityCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=3,
        max_length=64,
        description="Lowercase identifier with underscores, e.g. 'internal_project_id'.",
    )
    pattern: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_PATTERN_LEN,
        description="Python regex pattern. Use word boundaries (\\b) for best results.",
    )
    risk_level: str = Field(
        default="medium",
        description="critical | high | medium | low",
    )
    confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Detection confidence 0-1. Below the backend PII_CONFIDENCE_THRESHOLD, the entity is silently dropped.",
    )
    description: str = Field(default="", max_length=500)
    enabled: bool = Field(default=True)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "internal_ticket_id",
                    "pattern": r"\bTICKET-\d{6}\b",
                    "risk_level": "low",
                    "confidence": 0.95,
                    "description": "Internal support ticket identifier",
                    "enabled": True,
                }
            ]
        }
    }


class EntityResponse(BaseModel):
    id: int
    name: str
    pattern: str
    risk_level: str
    confidence: float
    description: str
    enabled: bool
    created_at: str | None = None
    updated_at: str | None = None


def _row_to_response(row: CustomEntity) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "pattern": row.pattern,
        "risk_level": row.risk_level,
        "confidence": row.confidence,
        "description": row.description,
        "enabled": bool(row.enabled),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# ── Helpers ──────────────────────────────────────────────────────

async def _reload_detector_patterns(request: Request, session: AsyncSession) -> None:
    """Re-fetch all enabled custom entities and push them to the live detector."""
    detector: PIIDetector = request.app.state.pii_detector
    rows = (await session.execute(select(CustomEntity).where(CustomEntity.enabled == 1))).scalars().all()
    patterns: list[CustomPattern] = []
    for row in rows:
        try:
            compiled = re.compile(row.pattern)
        except re.error as exc:
            logger.warning("[entities] skipping invalid regex %s: %s", row.name, exc)
            continue
        patterns.append(CustomPattern(
            name=row.name,
            regex=compiled,
            risk_level=row.risk_level,
            confidence=row.confidence,
        ))
    detector.set_custom_patterns(patterns)
    logger.info("[entities] reloaded %d custom patterns into detector", len(patterns))


# ── Endpoints ────────────────────────────────────────────────────

@router.get(
    "",
    summary="List all custom entities",
    description=(
        "Returns all user-defined PII entity patterns stored in the database, "
        "including disabled ones. Use this for the dashboard `/entities` page."
    ),
)
async def list_entities(
    _: str = Depends(_require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    rows = (await session.execute(select(CustomEntity).order_by(CustomEntity.name))).scalars().all()
    return {"entities": [_row_to_response(r) for r in rows], "total": len(rows)}


@router.post(
    "",
    summary="Create a custom entity pattern",
    description=(
        "Adds a new user-defined PII pattern to the database and immediately "
        "loads it into the live detector. The next /api/scan call will detect "
        "matches without requiring a backend restart.\n\n"
        "**Name** must be lowercase with underscores, 3-64 chars (e.g. `internal_ticket_id`). "
        "**Pattern** must be a valid Python regex. Use `\\b` word boundaries for accuracy. "
        "**Risk level** is critical/high/medium/low. **Confidence** is 0-1."
    ),
    responses={
        201: {"description": "Entity created."},
        409: {"description": "An entity with this name already exists."},
        422: {"description": "Invalid pattern, name format, or risk level."},
    },
    status_code=201,
)
async def create_entity(
    body: EntityCreate,
    request: Request,
    _: str = Depends(_require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if not _NAME_PATTERN.match(body.name):
        raise HTTPException(
            422,
            "Name must be lowercase with underscores, 3-64 chars, starting with a letter.",
        )
    if body.risk_level not in _VALID_RISK:
        raise HTTPException(422, f"risk_level must be one of {sorted(_VALID_RISK)}")
    _validate_pattern(body.pattern)

    existing = (await session.execute(select(CustomEntity).where(CustomEntity.name == body.name))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(409, f"Entity '{body.name}' already exists")

    row = CustomEntity(
        name=body.name,
        pattern=body.pattern,
        risk_level=body.risk_level,
        confidence=body.confidence,
        description=body.description,
        enabled=1 if body.enabled else 0,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    await _reload_detector_patterns(request, session)
    return _row_to_response(row)


@router.delete(
    "/{name}",
    summary="Delete a custom entity",
    description="Removes the entity from the database and unloads it from the live detector.",
    responses={
        200: {"description": "Entity deleted."},
        404: {"description": "Entity not found."},
    },
)
async def delete_entity(
    name: str,
    request: Request,
    _: str = Depends(_require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    row = (await session.execute(select(CustomEntity).where(CustomEntity.name == name))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, f"Entity '{name}' not found")
    await session.delete(row)
    await session.commit()
    await _reload_detector_patterns(request, session)
    return {"deleted": True, "name": name}


@router.post(
    "/reload",
    summary="Reload all custom entities into the detector",
    description=(
        "Forces a refresh of the in-memory custom pattern list from the database. "
        "Useful if the database was modified externally (e.g. via direct SQL). "
        "Normally NOT needed — create/delete operations auto-reload."
    ),
)
async def reload_entities(
    request: Request,
    _: str = Depends(_require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    await _reload_detector_patterns(request, session)
    detector: PIIDetector = request.app.state.pii_detector
    return {"reloaded": True, "loaded": len(detector.list_custom_patterns())}
