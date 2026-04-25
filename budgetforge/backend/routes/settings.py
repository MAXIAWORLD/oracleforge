import ipaddress
import re
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import SiteSetting
from core.auth import require_admin

router = APIRouter(prefix="/api", tags=["settings"])

_SMTP_KEYS = (
    "smtp_host",
    "smtp_port",
    "smtp_user",
    "smtp_password",
    "alert_from_email",
)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# B7.2 (H16): blocs IP privées/loopback pour smtp_host
_PRIVATE_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]
_BLOCKED_SMTP_HOSTS = {"localhost", "metadata.google.internal"}


def _validate_smtp_host(host: str) -> None:
    """B7.2 (H16): refuse les IPs privées et les hostnames internes comme smtp_host."""
    if not host or host == "":
        return
    if host.lower() in _BLOCKED_SMTP_HOSTS:
        raise ValueError(f"smtp_host '{host}' is not allowed")
    try:
        addr = ipaddress.ip_address(host)
        for net in _PRIVATE_NETS:
            if addr in net:
                raise ValueError(
                    f"smtp_host '{host}' points to a private/internal IP range"
                )
    except ValueError as exc:
        if "private" in str(exc) or "internal" in str(exc) or "not allowed" in str(exc):
            raise
        # C'est un hostname (pas une IP) → autorisé


class SettingsUpdate(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    alert_from_email: Optional[str] = None

    @field_validator("smtp_host")
    @classmethod
    def valid_smtp_host(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            _validate_smtp_host(v)
        return v

    @field_validator("smtp_port")
    @classmethod
    def valid_port(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 65535):
            raise ValueError("smtp_port must be between 1 and 65535")
        return v

    @field_validator("alert_from_email")
    @classmethod
    def valid_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v != "" and not _EMAIL_RE.match(v):
            raise ValueError("alert_from_email must be a valid email address")
        return v


def _get_all(db: Session) -> dict[str, str | None]:
    rows = {r.key: r.value for r in db.query(SiteSetting).all()}
    return {k: rows.get(k) for k in _SMTP_KEYS}


def _upsert(db: Session, key: str, value: str) -> None:
    row = db.query(SiteSetting).filter(SiteSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(SiteSetting(key=key, value=value))


@router.get("/settings", dependencies=[Depends(require_admin)])
def get_settings(db: Session = Depends(get_db)) -> dict:
    raw = _get_all(db)
    return {
        "smtp_host": raw.get("smtp_host") or "",
        "smtp_port": int(raw["smtp_port"]) if raw.get("smtp_port") else 587,
        "smtp_user": raw.get("smtp_user") or "",
        "smtp_password_set": bool(raw.get("smtp_password")),
        "alert_from_email": raw.get("alert_from_email") or "",
    }


@router.put("/settings", dependencies=[Depends(require_admin)])
def update_settings(body: SettingsUpdate, db: Session = Depends(get_db)) -> dict:
    updates = body.model_dump(exclude_none=True)
    for key, val in updates.items():
        _upsert(db, key, str(val))
    db.commit()
    return get_settings(db)
