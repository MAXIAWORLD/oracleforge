"""
Bloc 8 — H6 : Portal session revocation (TDD RED→GREEN)

Cookie HMAC 90 jours impossible à révoquer sans table server-side.
Fix : PortalRevokedSession (email + iat) + POST /api/portal/logout.
"""

import time
import hmac
import hashlib
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport

from main import app
from core.database import Base, get_db
from core.config import settings as real_settings


def _make_cookie(email: str, offset: int = 0) -> tuple[str, str]:
    """Forge un cookie portal valide. Retourne (cookie_value, iat_str)."""
    iat = str(int(time.time()) + offset)
    payload = f"{email}|{iat}"
    secret = (real_settings.portal_secret or "portal-dev-secret").encode()
    sig = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    return f"{email}|{iat}|{sig}", iat


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


class TestPortalSessionRevocation:
    @pytest.mark.anyio
    async def test_logout_clears_cookie(self, client):
        """POST /api/portal/logout efface le cookie portal_session."""
        cookie, _ = _make_cookie("user@example.com")
        response = await client.post(
            "/api/portal/logout",
            cookies={"portal_session": cookie},
        )
        assert response.status_code == 200
        # Le Set-Cookie doit supprimer le cookie (max-age=0 ou valeur vide)
        set_cookie = response.headers.get("set-cookie", "")
        assert "portal_session" in set_cookie
        assert (
            "max-age=0" in set_cookie.lower()
            or 'portal_session=""' in set_cookie
            or "expires" in set_cookie.lower()
        )

    @pytest.mark.anyio
    async def test_revoked_session_rejected(self, client, test_db):
        """Session révoquée via logout → /api/portal/session retourne 401."""
        from core.models import Project

        email = "revoke-me@example.com"
        project = Project(name=email, plan="free")
        test_db.add(project)
        test_db.commit()

        cookie, _ = _make_cookie(email)

        # D'abord vérifier que la session fonctionne
        r1 = await client.get(
            "/api/portal/session",
            cookies={"portal_session": cookie},
        )
        assert r1.status_code == 200, (
            f"Session devrait être valide avant logout : {r1.text}"
        )

        # Logout → révoque
        await client.post(
            "/api/portal/logout",
            cookies={"portal_session": cookie},
        )

        # Réutiliser le même cookie → rejeté
        r2 = await client.get(
            "/api/portal/session",
            cookies={"portal_session": cookie},
        )
        assert r2.status_code == 401, "Session révoquée doit retourner 401"

    @pytest.mark.anyio
    async def test_logout_without_session_returns_200(self, client):
        """POST /api/portal/logout sans cookie → 200 (idempotent)."""
        response = await client.post("/api/portal/logout")
        assert response.status_code == 200
