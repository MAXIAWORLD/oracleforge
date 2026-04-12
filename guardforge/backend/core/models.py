"""GuardForge — ORM models + schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime, Integer, String, Text, Float, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class ScanLog(Base):
    __tablename__ = "scan_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    pii_found: Mapped[int] = mapped_column(Integer, default=0)
    pii_types: Mapped[str] = mapped_column(Text, default="")
    policy_applied: Mapped[str] = mapped_column(String(30), default="strict")
    action_taken: Mapped[str] = mapped_column(String(30), default="anonymize")
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VaultEntry(Base):
    __tablename__ = "vault_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ── Pydantic schemas ─────────────────────────────────────────────


class PIIEntity(BaseModel):
    type: str
    value: str
    start: int
    end: int
    confidence: float


class ScanResult(BaseModel):
    original_length: int
    pii_entities: list[PIIEntity]
    anonymized_text: str
    pii_count: int
    policy: str


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    vault_entries: int = 0
    policies_loaded: int = 0
