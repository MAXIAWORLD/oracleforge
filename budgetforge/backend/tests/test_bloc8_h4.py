"""
Bloc 8 — H4 : portal.py secret fallback en production (TDD RED→GREEN)

_portal_secret() utilise "portal-dev-secret" si PORTAL_SECRET absent.
En production, ça permet de forger des cookies portal.
Fix : lever 503 si app_env=production et portal_secret vide.
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


class TestH4PortalSecretFallback:
    def test_portal_secret_raises_in_production_if_missing(self):
        """_portal_secret() doit lever HTTPException 503 en production si PORTAL_SECRET vide."""
        from fastapi import HTTPException as FastAPIHTTPException

        with patch("routes.portal.settings") as mock_settings:
            mock_settings.portal_secret = ""
            mock_settings.app_env = "production"
            from routes.portal import _portal_secret

            with pytest.raises(FastAPIHTTPException) as exc_info:
                _portal_secret()
        assert exc_info.value.status_code == 503

    def test_portal_secret_returns_bytes_in_dev_without_secret(self):
        """En dev sans PORTAL_SECRET → fallback autorisé (pas d'erreur)."""
        with patch("routes.portal.settings") as mock_settings:
            mock_settings.portal_secret = ""
            mock_settings.app_env = "development"
            from routes.portal import _portal_secret

            result = _portal_secret()
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_portal_secret_returns_configured_secret_in_production(self):
        """En production avec PORTAL_SECRET configuré → retourne la clé sans erreur."""
        with patch("routes.portal.settings") as mock_settings:
            mock_settings.portal_secret = "real-secret-key"
            mock_settings.app_env = "production"
            from routes.portal import _portal_secret

            result = _portal_secret()
        assert result == b"real-secret-key"

    @pytest.mark.anyio
    async def test_verify_endpoint_fails_in_production_without_secret(
        self, client, test_db
    ):
        """GET /api/portal/verify en production sans PORTAL_SECRET → 500 (RuntimeError)."""
        from datetime import datetime, timedelta, timezone
        from core.models import PortalToken

        # Insérer un token valide en DB
        token = PortalToken(
            email="test@example.com",
            token="valid-token-xyz",
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).replace(
                tzinfo=None
            ),
        )
        test_db.add(token)
        test_db.commit()

        with patch("routes.portal.settings") as mock_settings:
            mock_settings.portal_secret = ""
            mock_settings.app_env = "production"
            mock_settings.app_url = "https://example.com"
            response = await client.get("/api/portal/verify?token=valid-token-xyz")

        assert response.status_code == 503, (
            "HTTPException 503 attendue si PORTAL_SECRET absent en production"
        )
