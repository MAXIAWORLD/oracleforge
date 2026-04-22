"""TDD RED — Portail client : magic link email → voir ses projets + clés."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestPortalRequest:
    @pytest.mark.asyncio
    async def test_request_known_email_returns_200(self, client, test_db):
        """POST /api/portal/request avec email connu → 200 (envoie magic link)."""
        from core.models import Project
        proj = Project(name="user@example.com", plan="free",
                       stripe_customer_id="cus_test", stripe_subscription_id="sub_test")
        test_db.add(proj)
        test_db.commit()

        with patch("routes.portal.send_portal_email"):
            resp = await client.post("/api/portal/request", json={"email": "user@example.com"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_request_unknown_email_returns_200(self, client):
        """POST /api/portal/request avec email inconnu → 200 quand même (sécurité)."""
        resp = await client.post("/api/portal/request", json={"email": "nobody@example.com"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_request_sends_email(self, client, test_db):
        """POST /api/portal/request → send_portal_email appelé."""
        from core.models import Project
        proj = Project(name="send@example.com", plan="pro",
                       stripe_customer_id="cus_x", stripe_subscription_id="sub_x")
        test_db.add(proj)
        test_db.commit()

        with patch("routes.portal.send_portal_email") as mock_send:
            await client.post("/api/portal/request", json={"email": "send@example.com"})
        assert mock_send.called
        args = mock_send.call_args[0]
        assert args[0] == "send@example.com"


class TestPortalVerify:
    @pytest.mark.asyncio
    async def test_verify_valid_token_returns_projects(self, client, test_db):
        """GET /api/portal/verify?token=xxx → liste des projets de cet email."""
        from core.models import Project, PortalToken
        from datetime import datetime, timedelta

        proj = Project(name="owner@example.com", plan="free",
                       stripe_customer_id="cus_v", stripe_subscription_id="sub_v")
        test_db.add(proj)
        test_db.commit()

        token = PortalToken(
            email="owner@example.com",
            token="valid-token-abc",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        test_db.add(token)
        test_db.commit()

        resp = await client.get("/api/portal/verify?token=valid-token-abc")
        assert resp.status_code == 200
        body = resp.json()
        assert "projects" in body
        assert len(body["projects"]) == 1
        assert body["projects"][0]["name"] == "owner@example.com"
        assert "api_key" in body["projects"][0]
        assert body["projects"][0]["plan"] == "free"

    @pytest.mark.asyncio
    async def test_verify_expired_token_returns_401(self, client, test_db):
        """GET /api/portal/verify?token=expired → 401."""
        from core.models import PortalToken
        from datetime import datetime, timedelta

        token = PortalToken(
            email="exp@example.com",
            token="expired-token",
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        )
        test_db.add(token)
        test_db.commit()

        resp = await client.get("/api/portal/verify?token=expired-token")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_invalid_token_returns_401(self, client):
        """GET /api/portal/verify?token=bad → 401."""
        resp = await client.get("/api/portal/verify?token=totally-fake-token")
        assert resp.status_code == 401
