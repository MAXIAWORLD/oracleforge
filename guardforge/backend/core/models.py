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
    risk_level: Mapped[str] = mapped_column(String(20), default="none")
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VaultEntry(Base):
    __tablename__ = "vault_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Webhook(Base):
    """Webhook URL to notify on high-risk PII detections.

    On every scan with overall_risk=critical (or matching min_risk_level),
    the backend sends a POST to the registered URL with a JSON payload
    describing the event. Asynchronous, fire-and-forget.
    """
    __tablename__ = "webhooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    secret: Mapped[str] = mapped_column(String(255), default="")
    min_risk_level: Mapped[str] = mapped_column(String(20), default="critical")
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)


class CustomEntity(Base):
    """User-defined PII entity pattern.

    Allows customers to add their own regex patterns for internal codes,
    project IDs, custom identifiers, etc. — without modifying source code.
    """
    __tablename__ = "custom_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), default="medium")
    confidence: Mapped[float] = mapped_column(Float, default=0.85)
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Integer, default=1)  # SQLite-friendly bool as int
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ── Pydantic schemas ─────────────────────────────────────────────


class PIIEntity(BaseModel):
    type: str
    value: str
    start: int
    end: int
    confidence: float
    risk_level: str = "medium"


class ScanResult(BaseModel):
    original_length: int
    pii_entities: list[PIIEntity]
    anonymized_text: str
    pii_count: int
    policy: str
    overall_risk: str = "none"
    risk_distribution: dict[str, int] = {}


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    vault_entries: int = 0
    policies_loaded: int = 0
