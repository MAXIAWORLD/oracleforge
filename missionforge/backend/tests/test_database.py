"""TDD tests for core/database.py — async engine + session."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import init_db, close_db, get_db, Base
from core.models import Mission, ExecutionLog, LLMCallRecord  # noqa: F401 — register tables


class TestInitDb:
    """init_db creates tables and returns an engine."""

    @pytest.mark.asyncio
    async def test_creates_tables(self) -> None:
        engine = await init_db("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.connect() as conn:
                tables = await conn.run_sync(
                    lambda sync_conn: inspect(sync_conn).get_table_names()
                )
            assert "missions" in tables
            assert "execution_logs" in tables
            assert "llm_call_records" in tables
        finally:
            await close_db()

    @pytest.mark.asyncio
    async def test_engine_is_functional(self) -> None:
        engine = await init_db("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                assert result.scalar() == 1
        finally:
            await close_db()


class TestGetDb:
    """get_db yields a working async session."""

    @pytest.mark.asyncio
    async def test_yields_session(self) -> None:
        await init_db("sqlite+aiosqlite:///:memory:")
        try:
            async for session in get_db():
                assert isinstance(session, AsyncSession)
                # Verify we can execute a query
                result = await session.execute(text("SELECT 1"))
                assert result.scalar() == 1
                break
        finally:
            await close_db()

    @pytest.mark.asyncio
    async def test_raises_if_not_initialised(self) -> None:
        """get_db before init_db must raise RuntimeError."""
        await close_db()  # ensure clean state
        with pytest.raises(RuntimeError, match="not initialised"):
            async for _ in get_db():
                pass
