"""TDD tests for routes/reports.py — compliance summary + timeline."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("SECRET_KEY", "test-secret-key-32-chars-ok!!")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DEBUG", "true")

from core.database import Base, get_db
from core.models import ScanLog
from routes.reports import router as reports_router

_TEST_KEY = "test-secret-key-32-chars-ok!!"
_HEADERS = {"x-api-key": _TEST_KEY}

# ── In-memory DB + app fixtures ──────────────────────────────────


@pytest_asyncio.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = FastAPI()
    app.include_router(reports_router)

    # Override get_db dependency to use our in-memory test session
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _seed_logs(session: AsyncSession, rows: list[dict]) -> None:
    """Insert ScanLog rows for testing."""
    for r in rows:
        log = ScanLog(
            input_hash=r.get("input_hash", "abc123"),
            pii_found=r.get("pii_found", 0),
            pii_types=json.dumps(r.get("pii_types", [])),
            policy_applied=r.get("policy_applied", "strict"),
            action_taken=r.get("action_taken", "anonymize"),
            risk_level=r.get("risk_level", "medium"),
            scanned_at=r.get("scanned_at", datetime.now(tz=timezone.utc)),
        )
        session.add(log)
    await session.commit()


# ── Tests ────────────────────────────────────────────────────────


class TestSummaryEndpoint:
    async def test_summary_empty_returns_zeros(self, client: AsyncClient) -> None:
        resp = await client.get("/api/reports/summary", headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_scans"] == 0
        assert data["total_pii_detected"] == 0

    async def test_summary_with_seed_data(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await _seed_logs(db_session, [
            {"pii_found": 3, "pii_types": ["email", "credit_card"], "action_taken": "block", "risk_level": "critical"},
            {"pii_found": 1, "pii_types": ["email"], "action_taken": "anonymize", "risk_level": "medium"},
            {"pii_found": 0, "pii_types": [], "action_taken": "allow", "risk_level": "none"},
        ])
        resp = await client.get("/api/reports/summary", headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_scans"] == 3
        assert data["total_pii_detected"] == 4
        assert "email" in data["pii_by_type"]
        assert data["pii_by_type"]["email"] == 2
        assert "block" in data["action_distribution"]
        assert "critical" in data["risk_distribution"]

    async def test_summary_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/reports/summary")
        assert resp.status_code == 401

    async def test_summary_invalid_date_returns_422(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/reports/summary?from_date=not-a-date", headers=_HEADERS
        )
        assert resp.status_code == 422

    async def test_summary_response_shape(self, client: AsyncClient) -> None:
        resp = await client.get("/api/reports/summary", headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        required_keys = {
            "period", "total_scans", "total_pii_detected",
            "pii_by_type", "action_distribution", "risk_distribution", "top_policies",
        }
        assert required_keys.issubset(data.keys())
        assert "from" in data["period"]
        assert "to" in data["period"]


class TestTimelineEndpoint:
    async def test_timeline_empty_returns_empty_series(self, client: AsyncClient) -> None:
        resp = await client.get("/api/reports/timeline", headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "series" in data
        assert isinstance(data["series"], list)

    async def test_timeline_with_seed_data(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        now = datetime.now(tz=timezone.utc)
        await _seed_logs(db_session, [
            {"pii_found": 2, "scanned_at": now},
            {"pii_found": 1, "scanned_at": now},
        ])
        resp = await client.get("/api/reports/timeline", headers=_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["series"]) >= 1
        day_entry = data["series"][0]
        assert "date" in day_entry
        assert day_entry["scans"] == 2
        assert day_entry["pii"] == 3

    async def test_timeline_hour_granularity(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        now = datetime.now(tz=timezone.utc)
        await _seed_logs(db_session, [{"pii_found": 5, "scanned_at": now}])
        resp = await client.get(
            "/api/reports/timeline?granularity=hour", headers=_HEADERS
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["granularity"] == "hour"
        assert len(data["series"]) >= 1
        assert "hour" in data["series"][0]

    async def test_timeline_invalid_granularity(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/reports/timeline?granularity=week", headers=_HEADERS
        )
        assert resp.status_code == 422

    async def test_timeline_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/reports/timeline")
        assert resp.status_code == 401
