"""TDD RED — Fix #7: prebill doit utiliser une borne haute conservative quand
max_tokens est absent, sans que check_per_call_cap rejette les petits calls."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.token_estimator import estimate_output_tokens, TokenEstimator
from services.proxy_dispatcher import prebill_usage, check_per_call_cap
from core.models import Project, Usage


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mem_db():
    from core.database import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def project_with_budget(mem_db):
    p = Project(name="test", budget_usd=1.0, action="block")
    mem_db.add(p)
    mem_db.commit()
    mem_db.refresh(p)
    return p


SHORT_PAYLOAD = {"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]}
SHORT_PAYLOAD_MAX = {**SHORT_PAYLOAD, "max_tokens": 50}


# ── Tests estimate_output_tokens conservative ──────────────────────────────────


class TestEstimateOutputTokensConservative:
    def test_conservative_mode_larger_than_default_when_no_max_tokens(self):
        """conservative=True doit retourner plus de tokens que conservative=False
        quand max_tokens est absent — c'est le cœur du fix."""
        default_tokens = estimate_output_tokens(SHORT_PAYLOAD, conservative=False)
        conservative_tokens = estimate_output_tokens(SHORT_PAYLOAD, conservative=True)
        assert conservative_tokens > default_tokens

    def test_conservative_mode_returns_max_tokens_when_specified(self):
        """Quand max_tokens est présent, conservative=True doit retourner max_tokens
        (pas plus — le client a fixé une borne explicite)."""
        result = estimate_output_tokens(SHORT_PAYLOAD_MAX, conservative=True)
        assert result == 50

    def test_default_mode_unchanged_when_no_max_tokens(self):
        """conservative=False (défaut) doit conserver le comportement actuel (×0.75)."""
        input_tokens = TokenEstimator.estimate_input_tokens(SHORT_PAYLOAD)
        expected = min(4096, int(input_tokens * 0.75))
        result = estimate_output_tokens(SHORT_PAYLOAD, conservative=False)
        assert result == expected

    def test_conservative_mode_capped_at_4096(self):
        """conservative=True ne doit pas retourner plus de 4096."""
        result = estimate_output_tokens(SHORT_PAYLOAD, conservative=True)
        assert result <= 4096

    def test_conservative_no_max_tokens_returns_at_least_512(self):
        """Borne minimum raisonnable pour la réservation de budget : 512 tokens."""
        result = estimate_output_tokens(SHORT_PAYLOAD, conservative=True)
        assert result >= 512


# ── Tests check_per_call_cap n'est PAS conservative ───────────────────────────


class TestCheckPerCallCapNotConservative:
    @pytest.mark.asyncio
    async def test_small_call_not_rejected_when_budget_above_optimistic_cost(
        self, project_with_budget, mem_db
    ):
        """check_per_call_cap ne doit PAS rejeter un appel dont le coût optimiste
        est dans le budget — même si le coût conservative serait supérieur."""
        # gpt-4o "Hi" : coût optimiste ≈ $0.000265, budget = $1.0
        # check_per_call_cap doit passer sans HTTPException
        await check_per_call_cap(project_with_budget, SHORT_PAYLOAD, "gpt-4o", mem_db)
        # Si on arrive ici, le test passe (pas d'exception levée)

    @pytest.mark.asyncio
    async def test_call_rejected_when_explicit_cap_exceeded(
        self, project_with_budget, mem_db
    ):
        """check_per_call_cap rejette correctement quand le cap explicite est dépassé."""
        from fastapi import HTTPException

        project_with_budget.max_cost_per_call_usd = 0.000001  # cap micro : $0.000001
        with pytest.raises(HTTPException) as exc_info:
            await check_per_call_cap(
                project_with_budget, SHORT_PAYLOAD, "gpt-4o", mem_db
            )
        assert exc_info.value.status_code == 400


# ── Tests prebill_usage utilise l'estimation conservative ─────────────────────


class TestPrebillUsesConservativeEstimate:
    @pytest.mark.asyncio
    async def test_prebill_tokens_out_greater_than_optimistic_when_no_max_tokens(
        self, project_with_budget, mem_db
    ):
        """prebill_usage doit insérer plus de tokens_out que l'estimation optimiste
        quand max_tokens est absent — protège le budget contre les grosses réponses."""
        optimistic_tokens_out = estimate_output_tokens(
            SHORT_PAYLOAD, conservative=False
        )

        usage_id = await prebill_usage(
            mem_db, project_with_budget, "openai", "gpt-4o", SHORT_PAYLOAD, None
        )

        usage = mem_db.query(Usage).filter(Usage.id == usage_id).first()
        assert usage is not None
        assert usage.tokens_out > optimistic_tokens_out

    @pytest.mark.asyncio
    async def test_prebill_uses_max_tokens_exactly_when_specified(
        self, project_with_budget, mem_db
    ):
        """prebill_usage doit utiliser max_tokens exactement quand spécifié."""
        usage_id = await prebill_usage(
            mem_db, project_with_budget, "openai", "gpt-4o", SHORT_PAYLOAD_MAX, None
        )
        usage = mem_db.query(Usage).filter(Usage.id == usage_id).first()
        assert usage.tokens_out == 50
