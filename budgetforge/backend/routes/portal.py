import hmac
import hashlib
import logging
import smtplib
import time
from datetime import datetime, timedelta, date, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from core.config import settings
from core.database import get_db
from core.limiter import limiter
from core.log_utils import mask_email
from core.models import Project, PortalToken, PortalRevokedSession, Usage

logger = logging.getLogger(__name__)
router = APIRouter(tags=["portal"])

_TOKEN_TTL_HOURS = 1
_SESSION_MAX_AGE = 90 * 24 * 3600  # 90 jours


def cleanup_expired_tokens(db: Session) -> None:
    db.query(PortalToken).filter(
        PortalToken.expires_at < datetime.now(timezone.utc).replace(tzinfo=None)
    ).delete()
    db.commit()


def _portal_secret() -> bytes:
    if not settings.portal_secret:
        if settings.app_env == "production":
            raise HTTPException(
                status_code=503,
                detail="Service misconfigured: PORTAL_SECRET not set in production",
            )
        return b"portal-dev-secret"
    return settings.portal_secret.encode()


def _sign_session(email: str) -> str:
    iat = str(int(time.time()))
    payload = f"{email}|{iat}"
    sig = hmac.new(_portal_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{email}|{iat}|{sig}"


def _verify_session(cookie: str, db: Session | None = None) -> str | None:
    """H3 — valide la signature ET l'âge du cookie (iat).
    H6 — vérifie que la session n'est pas révoquée (table portal_revoked_sessions)."""
    parts = cookie.split("|")
    if len(parts) != 3:
        return None
    email, iat_str, sig = parts
    payload = f"{email}|{iat_str}"
    expected = hmac.new(_portal_secret(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        iat = int(iat_str)
    except ValueError:
        return None
    if int(time.time()) - iat > _SESSION_MAX_AGE:
        return None
    if db is not None:
        revoked = (
            db.query(PortalRevokedSession)
            .filter(
                PortalRevokedSession.email == email, PortalRevokedSession.iat == iat
            )
            .first()
        )
        if revoked:
            return None
    return email


class PortalRequestBody(BaseModel):
    email: str


def send_portal_email(email: str, token: str) -> bool:
    if not settings.smtp_host:
        logger.warning(
            "SMTP not configured — skipping portal email to %s", mask_email(email)
        )
        return False

    link = f"{settings.app_url}/portal#token={token}"
    body = f"""\
Access your BudgetForge projects

Click the link below to view your API keys and projects.
The link expires in {_TOKEN_TTL_HOURS} hour.

  {link}

If you didn't request this, ignore this email.

— The BudgetForge team
https://llmbudget.maxiaworld.app
"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your BudgetForge access link"
    msg["From"] = settings.alert_from_email
    msg["To"] = email
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.alert_from_email, email, msg.as_string())
        logger.info("Portal email sent to %s", mask_email(email))
        return True
    except Exception as e:
        logger.error("Portal email failed for %s: %s", mask_email(email), e)
        return False


@router.post("/api/portal/request")
@limiter.limit("5/hour")
async def portal_request(
    request: Request, body: PortalRequestBody, db: Session = Depends(get_db)
):
    import asyncio as _asyncio
    import time as _time

    _MIN_RESPONSE_S = 0.1  # constant-time floor prevents email enumeration by timing
    _start = _time.monotonic()

    cleanup_expired_tokens(db)
    email = body.email.strip().lower()
    if "\r" in email or "\n" in email:
        raise HTTPException(status_code=400, detail="Invalid email")
    projects = db.query(Project).filter(Project.name == email).all()
    if projects:
        token = PortalToken(
            email=email,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
            + timedelta(hours=_TOKEN_TTL_HOURS),
        )
        db.add(token)
        db.commit()
        db.refresh(token)
        await _asyncio.to_thread(send_portal_email, email, token.token)

    elapsed = _time.monotonic() - _start
    if elapsed < _MIN_RESPONSE_S:
        await _asyncio.sleep(_MIN_RESPONSE_S - elapsed)

    return {"ok": True}


@router.get("/api/portal/usage")
def portal_usage(request: Request, project_id: int, db: Session = Depends(get_db)):
    cookie = request.cookies.get("portal_session")
    if not cookie:
        raise HTTPException(status_code=401, detail="No session")
    email = _verify_session(cookie, db)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid session")

    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.name == email,
        )
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=403, detail="Project not found or access denied"
        )

    today = date.today()
    start = today - timedelta(days=29)
    start_dt = datetime(start.year, start.month, start.day)

    rows = (
        db.query(
            func.date(Usage.created_at).label("day"),
            func.sum(Usage.cost_usd).label("spend"),
        )
        .filter(Usage.project_id == project_id, Usage.created_at >= start_dt)
        .group_by(func.date(Usage.created_at))
        .all()
    )
    by_day = {r.day: float(r.spend) for r in rows}

    daily = [
        {
            "date": (start + timedelta(days=i)).isoformat(),
            "spend": round(by_day.get((start + timedelta(days=i)).isoformat(), 0.0), 9),
        }
        for i in range(30)
    ]
    return {"daily": daily}


def _project_list(projects: list) -> list:
    return [
        {
            "id": p.id,
            "name": p.name,
            "api_key": p.api_key,
            "plan": p.plan,
            "budget_usd": p.budget_usd,
            "unlimited_budget": p.budget_usd is None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in projects
    ]


@router.get("/api/portal/verify")
def portal_verify(token: str, response: Response, db: Session = Depends(get_db)):
    record = db.query(PortalToken).filter(PortalToken.token == token).first()
    if not record:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if record.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        db.delete(record)
        db.commit()
        raise HTTPException(status_code=401, detail="Token expired")

    email = record.email
    # Invalider le token — usage unique (magic link)
    db.delete(record)
    db.commit()

    secure = settings.app_url.startswith("https")
    response.set_cookie(
        key="portal_session",
        value=_sign_session(email),
        max_age=_SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
    )
    projects = db.query(Project).filter(Project.name == email).all()
    return {"email": email, "projects": _project_list(projects)}


@router.get("/api/portal/session")
def portal_session(request: Request, db: Session = Depends(get_db)):
    cookie = request.cookies.get("portal_session")
    if not cookie:
        raise HTTPException(status_code=401, detail="No session")
    email = _verify_session(cookie, db)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid session")
    projects = db.query(Project).filter(Project.name == email).all()
    return {"email": email, "projects": _project_list(projects)}


@router.post("/api/portal/logout")
def portal_logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """H6 — Révoque la session courante et supprime le cookie."""
    cookie = request.cookies.get("portal_session")
    if cookie:
        parts = cookie.split("|")
        if len(parts) == 3:
            email, iat_str, _ = parts
            try:
                iat = int(iat_str)
                existing = (
                    db.query(PortalRevokedSession)
                    .filter(
                        PortalRevokedSession.email == email,
                        PortalRevokedSession.iat == iat,
                    )
                    .first()
                )
                if not existing:
                    db.add(PortalRevokedSession(email=email, iat=iat))
                    db.commit()
            except ValueError:
                pass
    response.delete_cookie("portal_session", httponly=True, samesite="lax")
    return {"ok": True}
