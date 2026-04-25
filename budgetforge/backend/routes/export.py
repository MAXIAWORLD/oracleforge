import csv
import io
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from core.config import settings
from core.database import get_db
from core.models import Usage
from core.auth import require_viewer

router = APIRouter(prefix="/api/usage", tags=["export"])

_CSV_INJECTION_CHARS = frozenset("=+-@\t\r")


def _safe_csv_cell(val) -> str:
    """B7.3 (H14): préfixe par ' les valeurs CSV qui commencent par des chars d'injection Excel."""
    s = str(val) if val is not None else ""
    if s and s[0] in _CSV_INJECTION_CHARS:
        return "'" + s
    return s


def _query_usages(
    db: Session,
    project_id: Optional[int],
    date_from_dt,
    date_to_dt,
):
    q = db.query(Usage)
    if project_id is not None:
        q = q.filter(Usage.project_id == project_id)
    if date_from_dt is not None:
        q = q.filter(Usage.created_at >= date_from_dt)
    if date_to_dt is not None:
        q = q.filter(Usage.created_at <= date_to_dt)
    return q.order_by(Usage.created_at.desc())


@router.get("/export", dependencies=[Depends(require_viewer)])
async def export_usage(
    format: str = Query("csv"),
    project_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    if format not in ("csv", "json"):
        raise HTTPException(status_code=400, detail="format must be 'csv' or 'json'")

    # B1.3 — Defense in depth (audit C17)
    if settings.admin_api_key:
        is_global_admin = x_admin_key == settings.admin_api_key
    else:
        is_global_admin = settings.app_env != "production"
    if project_id is None and not is_global_admin:
        raise HTTPException(
            status_code=400,
            detail="project_id est requis. L'export global est réservé à l'admin.",
        )

    try:
        date_from_dt = datetime.fromisoformat(date_from) if date_from else None
        date_to_dt = datetime.fromisoformat(date_to) if date_to else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid date format: {exc}")

    q = _query_usages(db, project_id, date_from_dt, date_to_dt)

    if format == "json":
        records = q.all()
        return [
            {
                "id": u.id,
                "project_id": u.project_id,
                "provider": u.provider,
                "model": u.model,
                "tokens_in": u.tokens_in,
                "tokens_out": u.tokens_out,
                "cost_usd": u.cost_usd,
                "agent": u.agent,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in records
        ]

    fields = [
        "id",
        "project_id",
        "provider",
        "model",
        "tokens_in",
        "tokens_out",
        "cost_usd",
        "agent",
        "created_at",
    ]

    def generate_csv():
        # B7.4 (C18): yield_per(1000) pour éviter OOM sur grosses DB
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        yield output.getvalue()
        output.seek(0)
        output.truncate()

        for u in q.yield_per(1000):
            writer.writerow(
                {
                    "id": _safe_csv_cell(u.id),
                    "project_id": _safe_csv_cell(u.project_id),
                    "provider": _safe_csv_cell(u.provider),
                    "model": _safe_csv_cell(u.model),
                    "tokens_in": _safe_csv_cell(u.tokens_in),
                    "tokens_out": _safe_csv_cell(u.tokens_out),
                    "cost_usd": _safe_csv_cell(u.cost_usd),
                    "agent": _safe_csv_cell(u.agent or ""),
                    "created_at": _safe_csv_cell(
                        u.created_at.isoformat() if u.created_at else ""
                    ),
                }
            )
            if output.tell() > 65536:  # flush toutes les ~64KB
                yield output.getvalue()
                output.seek(0)
                output.truncate()

        if output.tell() > 0:
            yield output.getvalue()

    timestamp = (
        datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y%m%d_%H%M%S")
    )
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="budgetforge_export_{timestamp}.csv"'
        },
    )
