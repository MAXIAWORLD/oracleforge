import hmac
import re
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Literal, Optional
from core.config import settings
from core.database import get_db
from core.models import Member
from core.auth import require_admin

router = APIRouter(prefix="/api/members", tags=["members"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class MemberCreate(BaseModel):
    email: str
    role: Literal["admin", "viewer"] = "viewer"

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError(f"Invalid email: {v!r}")
        return v.lower()


class MemberResponse(BaseModel):
    id: int
    email: str
    api_key: str
    role: str
    model_config = {"from_attributes": True}


@router.post(
    "",
    status_code=201,
    response_model=MemberResponse,
    dependencies=[Depends(require_admin)],
)
def create_member(
    payload: MemberCreate,
    x_admin_key: Optional[str] = Header(default="", alias="X-Admin-Key"),
    db: Session = Depends(get_db),
):
    # B7.1 (H15): seul le global admin peut créer un member admin (si clé configurée)
    if payload.role == "admin" and settings.admin_api_key:
        if not hmac.compare_digest(x_admin_key or "", settings.admin_api_key):
            raise HTTPException(
                status_code=403,
                detail="Only the global admin can create admin members",
            )
    member = Member(email=payload.email, role=payload.role)
    db.add(member)
    try:
        db.commit()
        db.refresh(member)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail=f"Member '{payload.email}' already exists"
        )
    return member


@router.get(
    "", response_model=list[MemberResponse], dependencies=[Depends(require_admin)]
)
def list_members(db: Session = Depends(get_db)):
    return db.query(Member).all()


@router.delete("/{member_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_member(member_id: int, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(member)
    db.commit()
