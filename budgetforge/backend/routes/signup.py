import asyncio
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from core.config import settings
from core.database import get_db
from core.log_utils import mask_email
from core.models import Project, SignupAttempt
from services.onboarding_email import send_onboarding_email
from services.plan_quota import check_project_quota

logger = logging.getLogger(__name__)
router = APIRouter(tags=["signup"])

_ip_signups: dict[str, list[datetime]] = defaultdict(list)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _check_ip_rate_limit(
    ip: str, db: "Session | None" = None, max_per_day: int = 3
) -> bool:
    if db is not None:
        return _check_ip_rate_limit_db(ip, db, max_per_day)
    # in-memory fallback (unit tests sans DB)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(hours=24)
    recent = [t for t in _ip_signups[ip] if t > cutoff]
    _ip_signups[ip] = recent
    if len(recent) >= max_per_day:
        return False
    _ip_signups[ip].append(now)
    return True


def _check_ip_rate_limit_db(ip: str, db: Session, max_per_day: int = 3) -> bool:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(hours=24)
    count = (
        db.query(SignupAttempt)
        .filter(SignupAttempt.ip == ip, SignupAttempt.created_at > cutoff)
        .count()
    )
    if count >= max_per_day:
        return False
    return True


def _check_domain_rate_limit(email: str, db: Session, max_per_day: int = 10) -> bool:
    domain = email.split("@", 1)[-1] if "@" in email else ""
    if not domain:
        return True
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(hours=24)
    count = (
        db.query(SignupAttempt)
        .filter(SignupAttempt.email_domain == domain, SignupAttempt.created_at > cutoff)
        .count()
    )
    return count < max_per_day


def _record_signup_attempt(ip: str, email: str, db: Session) -> None:
    domain = email.split("@", 1)[-1] if "@" in email else None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(SignupAttempt(ip=ip, email_domain=domain, created_at=now))
    db.commit()


class SignupFreeRequest(BaseModel):
    email: str
    turnstile_token: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        # Strip +tag alias (user+tag@gmail.com → user@gmail.com)
        local, sep, domain = v.partition("@")
        if "+" in local:
            local = local.split("+", 1)[0]
        return f"{local}{sep}{domain}"


async def _verify_turnstile(token: Optional[str], client_ip: str) -> bool:
    """H1 — vérifie un token Cloudflare Turnstile côté serveur.
    Si aucune clé Turnstile n'est configurée : pass-through (déploiement progressif).
    Un warning est loggué en production pour rappeler de configurer la clé."""
    secret = settings.turnstile_secret_key
    if not secret:
        if settings.app_env == "production":
            logger.warning(
                "Turnstile désactivé (TURNSTILE_SECRET_KEY vide). Les signups "
                "ne sont PAS protégés contre les bots. Configurez la clé sur Cloudflare."
            )
        return True
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": secret, "response": token, "remoteip": client_ip},
            )
            data = resp.json()
            return bool(data.get("success"))
    except Exception as e:
        logger.warning("Turnstile verification error: %s", e)
        return False


@router.post("/api/signup/free")
async def signup_free(
    body: SignupFreeRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"

    # H1 — anti-bot avant tout le reste
    if not await _verify_turnstile(body.turnstile_token, client_ip):
        raise HTTPException(
            status_code=400,
            detail="Captcha verification failed. Please retry.",
        )

    if not _check_ip_rate_limit(client_ip, db=db):
        raise HTTPException(
            status_code=429,
            detail="Too many signup attempts from this connection. Try again tomorrow.",
        )
    if not _check_domain_rate_limit(body.email, db=db):
        raise HTTPException(
            status_code=429,
            detail="Too many signups from this email domain. Try again tomorrow.",
        )
    _record_signup_attempt(client_ip, body.email, db)

    check_project_quota(body.email, "free", db)

    project = Project(name=body.email, plan="free")
    db.add(project)
    try:
        db.commit()
        db.refresh(project)
        logger.info("Free signup: new project for %s", mask_email(body.email))
    except IntegrityError:
        db.rollback()
        project = db.query(Project).filter_by(name=body.email).first()
        if not project:
            raise HTTPException(
                status_code=500, detail="Signup failed — please try again."
            )
        logger.info("Free signup: resending email to %s", mask_email(body.email))

    await asyncio.to_thread(
        send_onboarding_email, body.email, project.api_key, project.plan
    )
    return {"ok": True}
