"""TDD — Audit 24/04/2026 : corrections A1→A5 (ship-blockers critiques).

Écrits en ROUGE avant toute implémentation.
"""

import asyncio
import pathlib

import httpx
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock, patch

from main import app
from core.database import Base, get_db
from core.models import Project

# ── Fixtures proxy ────────────────────────────────────────────────────────────


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


FAKE_OPENAI = {
    "id": "x",
    "choices": [{"message": {"role": "assistant", "content": "ok"}}],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
}


# ── A1 — busy_timeout SQLite ──────────────────────────────────────────────────


class TestA1BusyTimeout:
    def test_sqlite_busy_timeout_configured(self):
        """PRAGMA busy_timeout=30000 doit être déclaré dans database.py."""
        db_file = pathlib.Path(__file__).parent.parent / "core" / "database.py"
        content = db_file.read_text()
        assert "busy_timeout" in content, "PRAGMA busy_timeout absent de database.py"
        assert "30000" in content, "Valeur 30000 absente de database.py"

    @pytest.mark.asyncio
    async def test_concurrent_requests_respect_tight_budget(self, client):
        """Avec un budget serré, la 2ème requête concurrente doit être bloquée (429)."""
        proj = (await client.post("/api/projects", json={"name": "race-tight"})).json()
        # Budget très inférieur au coût d'un seul prebill (~$0.00000975 pour gpt-4o-mini)
        await client.put(
            f"/api/projects/{proj['id']}/budget",
            json={"budget_usd": 0.000005, "alert_threshold_pct": 80, "action": "block"},
        )

        async def slow_forward(payload, api_key, **kwargs):
            await asyncio.sleep(0.05)
            return FAKE_OPENAI

        with patch(
            "services.proxy_forwarder.ProxyForwarder.forward_openai", new=slow_forward
        ):
            r1, r2 = await asyncio.gather(
                client.post(
                    "/proxy/openai/v1/chat/completions",
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                    headers={"Authorization": f"Bearer {proj['api_key']}"},
                ),
                client.post(
                    "/proxy/openai/v1/chat/completions",
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                    headers={"Authorization": f"Bearer {proj['api_key']}"},
                ),
            )
        statuses = {r1.status_code, r2.status_code}
        assert 429 in statuses, (
            f"Les deux requêtes ont passé ({statuses}) — race condition non détectée"
        )


# ── A2 — Modèle inconnu → HTTP 400 ───────────────────────────────────────────


class TestA2UnknownModel:
    @pytest.mark.asyncio
    async def test_unknown_model_returns_400(self, client):
        """Un modèle inconnu doit retourner 400, pas cost=0 silencieux."""
        proj = (
            await client.post("/api/projects", json={"name": "unknown-model"})
        ).json()
        await client.put(
            f"/api/projects/{proj['id']}/budget",
            json={"budget_usd": 100.0, "alert_threshold_pct": 80, "action": "block"},
        )
        resp = await client.post(
            "/proxy/openai/v1/chat/completions",
            json={
                "model": "fake-model-xyz-99999",
                "messages": [{"role": "user", "content": "hi"}],
            },
            headers={"Authorization": f"Bearer {proj['api_key']}"},
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"].lower()
        assert "unknown model" in detail or "fake-model-xyz-99999" in detail

    @pytest.mark.asyncio
    async def test_unknown_model_does_not_create_zero_cost_usage(self, client, test_db):
        """Un modèle inconnu ne doit pas créer d'enregistrement Usage cost=0."""
        proj = (
            await client.post("/api/projects", json={"name": "no-free-usage"})
        ).json()
        await client.put(
            f"/api/projects/{proj['id']}/budget",
            json={"budget_usd": 100.0, "alert_threshold_pct": 80, "action": "block"},
        )
        await client.post(
            "/proxy/openai/v1/chat/completions",
            json={
                "model": "absolutely-fake-model-never-exists",
                "messages": [{"role": "user", "content": "hi"}],
            },
            headers={"Authorization": f"Bearer {proj['api_key']}"},
        )
        from core.models import Usage

        count = test_db.query(Usage).filter(Usage.project_id == proj["id"]).count()
        assert count == 0, (
            f"Usage créé ({count}) pour un modèle inconnu — spam $0 possible"
        )


# ── A3 — except trop large dans cost_calculator ───────────────────────────────


class TestA3ExceptTooLarge:
    @pytest.mark.asyncio
    async def test_network_error_propagates_not_swallowed(self):
        """httpx.TimeoutException doit remonter, pas être avalé par le fallback static."""
        from services.cost_calculator import CostCalculator

        with patch(
            "services.cost_calculator.get_dynamic_price",
            side_effect=httpx.TimeoutException("timeout"),
        ):
            with pytest.raises(httpx.TimeoutException):
                await CostCalculator.get_price("gpt-4o")

    @pytest.mark.asyncio
    async def test_unknown_model_still_raises_unknown_model_error(self):
        """Le comportement existant (UnknownModelError pour modèle inconnu) ne doit pas changer."""
        from services.cost_calculator import CostCalculator, UnknownModelError

        with pytest.raises(UnknownModelError):
            await CostCalculator.get_price("non-existent-model-abc-123")


# ── A4 — fail-closed sur JSON corrompu ───────────────────────────────────────


class TestA4FailClosed:
    @pytest.mark.asyncio
    async def test_corrupted_allowed_providers_returns_500(self, client, test_db):
        """allowed_providers JSON corrompu → 500 (pas fail-open permettant tous les providers)."""
        proj = (
            await client.post("/api/projects", json={"name": "corrupt-providers"})
        ).json()
        test_db.query(Project).filter(Project.id == proj["id"]).update(
            {"allowed_providers": "not-valid-json"}
        )
        test_db.commit()

        with patch(
            "services.proxy_forwarder.ProxyForwarder.forward_openai",
            new_callable=AsyncMock,
        ) as mock_fwd:
            mock_fwd.return_value = FAKE_OPENAI
            resp = await client.post(
                "/proxy/openai/v1/chat/completions",
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "hi"}],
                },
                headers={"Authorization": f"Bearer {proj['api_key']}"},
            )
        assert resp.status_code == 500
        assert "corrupted" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_corrupted_downgrade_chain_returns_500(self, client, test_db):
        """downgrade_chain JSON corrompu → 500 (pas fail-open avec chain=None silencieux)."""
        proj = (
            await client.post("/api/projects", json={"name": "corrupt-chain"})
        ).json()
        await client.put(
            f"/api/projects/{proj['id']}/budget",
            json={"budget_usd": 100.0, "alert_threshold_pct": 80, "action": "block"},
        )
        test_db.query(Project).filter(Project.id == proj["id"]).update(
            {"downgrade_chain": "not-valid-json"}
        )
        test_db.commit()

        with patch(
            "services.proxy_forwarder.ProxyForwarder.forward_openai",
            new_callable=AsyncMock,
        ) as mock_fwd:
            mock_fwd.return_value = FAKE_OPENAI
            resp = await client.post(
                "/proxy/openai/v1/chat/completions",
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "hi"}],
                },
                headers={"Authorization": f"Bearer {proj['api_key']}"},
            )
        assert resp.status_code == 500
        assert "corrupted" in resp.json()["detail"].lower()


# ── A5 — STRIPE_WEBHOOK_SECRET dans le guard production ──────────────────────


class TestA5StripeWebhookGuard:
    @pytest.mark.asyncio
    async def test_production_lifespan_fails_if_stripe_webhook_secret_missing(
        self, monkeypatch
    ):
        """En production, STRIPE_WEBHOOK_SECRET absent doit empêcher le démarrage."""
        import main

        monkeypatch.setattr(main.settings, "app_env", "production")
        monkeypatch.setattr(main.settings, "admin_api_key", "admin-key")
        monkeypatch.setattr(main.settings, "portal_secret", "portal-secret")
        monkeypatch.setattr(main.settings, "stripe_webhook_secret", "")
        monkeypatch.setattr(main.settings, "app_url", "https://example.com")

        with pytest.raises(RuntimeError, match="STRIPE_WEBHOOK_SECRET"):
            async with main.lifespan(main.app):
                pass

    @pytest.mark.asyncio
    async def test_production_lifespan_ok_when_all_secrets_present(self, monkeypatch):
        """En production, toutes les variables présentes → démarrage sans erreur."""
        import main

        monkeypatch.setattr(main.settings, "app_env", "production")
        monkeypatch.setattr(main.settings, "admin_api_key", "admin-key")
        monkeypatch.setattr(main.settings, "portal_secret", "portal-secret")
        monkeypatch.setattr(main.settings, "stripe_webhook_secret", "whsec_test")
        monkeypatch.setattr(main.settings, "app_url", "https://example.com")

        async with main.lifespan(main.app):
            pass  # ne doit pas lever d'exception
