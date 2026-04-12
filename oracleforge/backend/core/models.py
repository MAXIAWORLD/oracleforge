"""OracleForge — ORM models + Pydantic schemas.

Tables: PriceRecord, SourceHealth.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime, Float, Integer, String, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


# ── ORM ──────────────────────────────────────────────────────────


class PriceRecord(Base):
    __tablename__ = "price_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    price_usd: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SourceHealth(Base):
    __tablename__ = "source_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    is_healthy: Mapped[bool] = mapped_column(Boolean, default=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Pydantic Schemas ─────────────────────────────────────────────


class PriceResponse(BaseModel):
    symbol: str
    price_usd: float
    confidence: float
    sources_used: int
    sources_available: int
    latency_ms: int
    cached: bool = False


class BatchPriceResponse(BaseModel):
    prices: list[PriceResponse]
    total_latency_ms: int


class SourceStatus(BaseModel):
    name: str
    enabled: bool
    healthy: bool
    last_latency_ms: int = 0


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    sources_healthy: int = 0
    sources_total: int = 0
