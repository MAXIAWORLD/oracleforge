import hmac

from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from core.config import settings
from core.database import get_db


def _admin_key_matches(provided: str) -> bool:
    """Constant-time comparison against the configured admin API key (F1)."""
    if not settings.admin_api_key:
        return False
    return hmac.compare_digest(provided, settings.admin_api_key)


async def require_admin(
    x_admin_key: str = Header(default="", alias="X-Admin-Key"),
    db: Session = Depends(get_db),
) -> None:
    """Allow: global admin key, OR member with role=admin, OR dev mode (no key configured)."""
    if not settings.admin_api_key:
        if settings.app_env == "production":
            raise HTTPException(
                status_code=503,
                detail="Service misconfigured: ADMIN_API_KEY not set in production",
            )
        # Dev mode: block viewer members trying to reach write endpoints
        if x_admin_key and x_admin_key.startswith("bf-mbr-"):
            from core.models import Member

            member = db.query(Member).filter(Member.api_key == x_admin_key).first()
            if member and member.role == "viewer":
                raise HTTPException(
                    status_code=403,
                    detail="Viewer members cannot perform write operations",
                )
        return

    # Global admin key — constant-time compare (F1: timing attack)
    if _admin_key_matches(x_admin_key):
        return

    # Member key
    if x_admin_key.startswith("bf-mbr-"):
        from core.models import Member

        member = db.query(Member).filter(Member.api_key == x_admin_key).first()
        if member:
            if member.role == "admin":
                return
            raise HTTPException(
                status_code=403, detail="Viewer members cannot perform write operations"
            )

    raise HTTPException(status_code=401, detail="Invalid or missing admin key")


async def require_viewer(
    x_admin_key: str = Header(default="", alias="X-Admin-Key"),
    db: Session = Depends(get_db),
) -> None:
    """Allow: global admin key, OR any member (admin or viewer), OR dev mode."""
    if not settings.admin_api_key:
        if settings.app_env == "production":
            raise HTTPException(
                status_code=503,
                detail="Service misconfigured: ADMIN_API_KEY not set in production",
            )
        return  # dev mode

    # Global admin key — constant-time compare (F1: timing attack)
    if _admin_key_matches(x_admin_key):
        return

    if x_admin_key.startswith("bf-mbr-"):
        from core.models import Member

        member = db.query(Member).filter(Member.api_key == x_admin_key).first()
        if member:
            return

    raise HTTPException(status_code=401, detail="Invalid or missing key")
