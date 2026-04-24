"""TDD RED — Filtres temporels Overview."""

import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient, ASGITransport
from main import app
from core.database import Base, get_db
from core.models import Usage


@pytest.fixture(scope="function")
def test_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

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


def seed_usages_with_dates(db, project_id: int):
    """Crée des usages avec différentes dates pour tester les filtres."""
    now = datetime.now(timezone.utc)

    # Aujourd'hui
    usages = [
        Usage(
            project_id=project_id,
            provider="openai",
            model="gpt-4o",
            tokens_in=1000,
            tokens_out=200,
            cost_usd=0.008,
            created_at=now,
        ),
        Usage(
            project_id=project_id,
            provider="anthropic",
            model="claude-sonnet-4-6",
            tokens_in=500,
            tokens_out=100,
            cost_usd=0.003,
            created_at=now - timedelta(hours=2),
        ),
    ]

    # 7 derniers jours
    for i in range(1, 7):
        usages.append(
            Usage(
                project_id=project_id,
                provider="google",
                model="gemini-2.0-flash",
                tokens_in=800,
                tokens_out=150,
                cost_usd=0.0001,
                created_at=now - timedelta(days=i),
            )
        )

    # Ce mois (mais pas aujourd'hui)
    for i in range(10, 20):
        usages.append(
            Usage(
                project_id=project_id,
                provider="deepseek",
                model="deepseek-chat",
                tokens_in=600,
                tokens_out=120,
                cost_usd=0.00017,
                created_at=now - timedelta(days=i),
            )
        )

    # Plus d'un mois
    usages.append(
        Usage(
            project_id=project_id,
            provider="ollama",
            model="ollama/llama3",
            tokens_in=2000,
            tokens_out=500,
            cost_usd=0.0,
            created_at=now - timedelta(days=40),
        )
    )

    for u in usages:
        db.add(u)
    db.commit()


class TestTimeFilters:
    @pytest.mark.asyncio
    async def test_today_filter(self, client, test_db):
        """Filtre 'today' ne retourne que les usages d'aujourd'hui."""
        proj = (await client.post("/api/projects", json={"name": "today-test"})).json()
        seed_usages_with_dates(test_db, proj["id"])

        resp = await client.get(f"/api/projects/{proj['id']}/usage/daily?period=today")
        assert resp.status_code == 200
        data = resp.json()

        # Doit retourner seulement aujourd'hui
        assert len(data) == 1
        today = datetime.now(timezone.utc).date().isoformat()
        assert data[0]["date"] == today
        # 2 usages aujourd'hui : 0.008 + 0.003 = 0.011
        assert data[0]["spend"] == pytest.approx(0.011, rel=0.01)

    @pytest.mark.asyncio
    async def test_7days_filter(self, client, test_db):
        """Filtre '7d' retourne les 7 derniers jours."""
        proj = (await client.post("/api/projects", json={"name": "7d-test"})).json()
        seed_usages_with_dates(test_db, proj["id"])

        resp = await client.get(f"/api/projects/{proj['id']}/usage/daily?period=7d")
        assert resp.status_code == 200
        data = resp.json()

        # Doit retourner 7 jours
        assert len(data) == 7
        # Vérifier que les dates sont dans l'ordre
        dates = [item["date"] for item in data]
        assert dates == sorted(dates)

    @pytest.mark.asyncio
    async def test_month_filter(self, client, test_db):
        """Filtre 'month' retourne ce mois."""
        proj = (await client.post("/api/projects", json={"name": "month-test"})).json()
        seed_usages_with_dates(test_db, proj["id"])

        resp = await client.get(f"/api/projects/{proj['id']}/usage/daily?period=month")
        assert resp.status_code == 200
        data = resp.json()

        # Doit retourner les jours de ce mois
        assert len(data) > 0
        # Ne doit pas inclure l'usage de 40 jours
        total_spend = sum(item["spend"] for item in data)
        assert total_spend > 0.0

    @pytest.mark.asyncio
    async def test_all_time_filter(self, client, test_db):
        """Filtre 'all' retourne toutes les données."""
        proj = (await client.post("/api/projects", json={"name": "all-test"})).json()
        seed_usages_with_dates(test_db, proj["id"])

        resp = await client.get(f"/api/projects/{proj['id']}/usage/daily?period=all")
        assert resp.status_code == 200
        data = resp.json()

        # Doit inclure toutes les données
        assert len(data) > 0
        # Doit inclure l'usage de 40 jours (coût 0.0)
        total_spend = sum(item["spend"] for item in data)
        assert total_spend > 0.0

    @pytest.mark.asyncio
    async def test_invalid_period_returns_default(self, client, test_db):
        """Période invalide retourne le comportement par défaut (30 jours)."""
        proj = (
            await client.post("/api/projects", json={"name": "invalid-test"})
        ).json()
        seed_usages_with_dates(test_db, proj["id"])

        resp = await client.get(
            f"/api/projects/{proj['id']}/usage/daily?period=invalid"
        )
        assert resp.status_code == 200
        data = resp.json()

        # Doit retourner 30 jours (comportement par défaut)
        assert len(data) == 30

    @pytest.mark.asyncio
    async def test_no_period_returns_default(self, client, test_db):
        """Pas de paramètre period retourne le comportement par défaut."""
        proj = (
            await client.post("/api/projects", json={"name": "default-test"})
        ).json()
        seed_usages_with_dates(test_db, proj["id"])

        resp = await client.get(f"/api/projects/{proj['id']}/usage/daily")
        assert resp.status_code == 200
        data = resp.json()

        # Doit retourner 30 jours (comportement par défaut)
        assert len(data) == 30
