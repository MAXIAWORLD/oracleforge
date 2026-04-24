"""Shared test fixtures for AuthForge integration tests."""

from __future__ import annotations

import os

# Set env vars BEFORE any app module is imported so lru_cache picks them up.
os.environ["SECRET_KEY"] = "test-secret-key-32-chars-ok!!"

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from core.config import get_settings
from core.database import Base, get_db
from services.auth_service import AuthService, RateLimiter

TEST_SECRET = "test-secret-key-32-chars-ok!!"
TEST_DB = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def engine():
    eng = create_async_engine(
        TEST_DB,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db(engine) -> AsyncSession:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session


def _build_app(engine, rate_limit: int = 100):
    from main import create_app

    get_settings.cache_clear()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app()

    async def override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    settings = get_settings()
    app.state.auth_service = AuthService(settings=settings)
    app.state.rate_limiter = RateLimiter(max_requests=rate_limit, window_seconds=60)
    return app


@pytest.fixture
async def client(engine):
    app = _build_app(engine)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": TEST_SECRET},
    ) as ac:
        yield ac
    get_settings.cache_clear()


@pytest.fixture
async def no_key_client(engine):
    """Client without X-API-Key — for middleware tests."""
    app = _build_app(engine)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    get_settings.cache_clear()
