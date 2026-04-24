"""
Bloc 8 — C1 : Defense-in-depth auth fail-open (TDD RED→GREEN)

Si APP_ENV=production ET ADMIN_API_KEY absent → require_admin/require_viewer
doivent retourner 503 (pas fail-open). Startup guard dans lifespan est la
première couche ; auth.py est la deuxième (defense-in-depth).
"""

import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from core.database import Base, get_db


@pytest.fixture(scope="function")
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
async def client(test_db):
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


class TestC1AdminFailOpen:
    """require_admin ne doit PAS être fail-open en production."""

    @pytest.mark.anyio
    async def test_require_admin_503_when_key_missing_in_production(self, client):
        """En production sans ADMIN_API_KEY → 503, pas 200. RED avant fix."""
        with patch("core.auth.settings") as mock_settings:
            mock_settings.admin_api_key = ""
            mock_settings.app_env = "production"
            response = await client.get("/api/admin/stats")
        assert response.status_code == 503, (
            "require_admin doit retourner 503 en production si admin_api_key absent"
        )

    @pytest.mark.anyio
    async def test_require_viewer_503_when_key_missing_in_production(self, client):
        """En production sans ADMIN_API_KEY → require_viewer retourne 503. RED avant fix."""
        with patch("core.auth.settings") as mock_settings:
            mock_settings.admin_api_key = ""
            mock_settings.app_env = "production"
            response = await client.get("/api/admin/stats")
        assert response.status_code == 503

    @pytest.mark.anyio
    async def test_require_admin_fail_open_allowed_in_dev(self, client):
        """En dev (app_env != production) sans clé → fail-open normal (200 ou 404, pas 503)."""
        with patch("core.auth.settings") as mock_settings:
            mock_settings.admin_api_key = ""
            mock_settings.app_env = "development"
            response = await client.get("/api/admin/stats")
        assert response.status_code != 503, "Dev mode doit rester fail-open (pas 503)"

    @pytest.mark.anyio
    async def test_require_admin_works_normally_with_valid_key_in_production(
        self, client
    ):
        """En production avec clé présente → auth fonctionne normalement (pas 503)."""
        with patch("core.auth.settings") as mock_settings:
            mock_settings.admin_api_key = "test-admin-key"
            mock_settings.app_env = "production"
            # Sans header → 401 attendu (pas 503)
            response = await client.get("/api/admin/stats")
        assert response.status_code == 401, (
            "Clé absente du header doit donner 401, pas 503"
        )
