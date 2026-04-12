"""Shared pytest fixtures for MissionForge backend tests."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

# Set env before importing settings
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-chars-ok!!")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DEBUG", "true")


from core.config import Settings
from core.database import Base, close_db, init_db, get_db


@pytest.fixture
def settings() -> Settings:
    """Return a test Settings instance (in-memory DB, safe defaults)."""
    return Settings(
        secret_key="test-secret-key-32-chars-ok!!",
        database_url="sqlite+aiosqlite:///:memory:",
        debug=True,
        chroma_persist_dir="./test_chroma_db",
        missions_dir="./test_missions",
    )


@pytest_asyncio.fixture
async def db_engine(settings: Settings):
    """Initialise an in-memory database and yield the engine."""
    engine = await init_db(settings.database_url)
    yield engine
    await close_db()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh async session for a single test."""
    async for session in get_db():
        yield session
