from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from core.models import Usage

PLAN_LIMITS: dict[str, int] = {
    "free":     1_000,
    "pro":    100_000,
    "agency": 500_000,
    "ltd":    100_000,
}


def get_calls_this_month(project_id: int, db: Session) -> int:
    first_of_month = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    result = db.query(func.count(Usage.id)).filter(
        Usage.project_id == project_id,
        Usage.created_at >= first_of_month,
    ).scalar()
    return result or 0


def check_quota(project, db: Session) -> None:
    plan = getattr(project, "plan", None) or "free"
    limit = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    calls = get_calls_this_month(project.id, db)
    if calls >= limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Monthly call quota exceeded for plan '{plan}' "
                f"({calls:,}/{limit:,} calls). "
                f"Upgrade at https://llmbudget.maxiaworld.app/#pricing"
            ),
        )
