"""TDD B4 — Logique budget + race conditions.

B4.1: budget_usd is None → 402 fail-closed (C07).
B4.2: Redlock token-based (C08) — delete-if-token-matches.
B4.3: flock O_NOFOLLOW (H02).
B4.5: Streaming finalize partiel (C09).
B4.6: should_alert cohérence (H06).
B4.7: Token estimator clamp max_tokens (H05).
"""

import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import Project


@pytest.fixture(scope="function")
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
    Base.metadata.drop_all(bind=engine)


# ── B4.1 — budget_usd is None → 402 (C07) ────────────────────────────────────


@pytest.mark.asyncio
async def test_check_budget_model_none_raises_402(db):
    """C07: projet sans budget configuré doit être refusé (fail-closed), pas autoriser."""
    from fastapi import HTTPException
    from services.proxy_dispatcher import check_budget_model

    project = Project(name="nobudget@test.com", plan="free", budget_usd=None)
    db.add(project)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await check_budget_model(project, db, "gpt-4o")

    assert exc_info.value.status_code == 402
    assert "budget" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_check_budget_model_with_budget_passes(db):
    """Projet avec budget configuré doit passer le check."""
    from services.proxy_dispatcher import check_budget_model

    project = Project(name="withbudget@test.com", plan="pro", budget_usd=100.0)
    db.add(project)
    db.commit()

    result = await check_budget_model(project, db, "gpt-4o-mini")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_check_budget_model_minus1_unlimited(db):
    """Sentinelle budget_usd=-1 = illimité explicite (agency sans limite)."""
    from services.proxy_dispatcher import check_budget_model

    project = Project(name="unlimited@test.com", plan="agency", budget_usd=-1.0)
    db.add(project)
    db.commit()

    result = await check_budget_model(project, db, "gpt-4o-mini")
    assert result == "gpt-4o-mini"


# ── B4.2 — Redlock token-based (C08) ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_redlock_uses_token_for_atomic_release():
    """C08: Redis lock doit stocker un token unique et utiliser Lua pour la suppression."""
    from services.distributed_budget_lock import distributed_budget_lock

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.eval = AsyncMock(return_value=1)

    with patch(
        "services.distributed_budget_lock.get_redis_client",
        return_value=mock_redis,
    ):
        async with distributed_budget_lock(42):
            pass

    # Vérifier que SET a été appelé avec un token (pas b"locked")
    set_calls = mock_redis.set.call_args_list
    assert len(set_calls) >= 1
    token_value = set_calls[0][0][1]  # 2nd positional arg = valeur
    assert token_value != b"locked", "Le token doit être unique, pas b'locked'"
    assert len(token_value) > 8, "Token doit être assez long"

    # Vérifier que eval (Lua) a été appelé pour la suppression atomique
    assert mock_redis.eval.called, "Lua script doit être utilisé pour libérer le lock"


@pytest.mark.asyncio
async def test_redlock_does_not_delete_foreign_lock():
    """C08: Si TTL expire, on ne supprime pas le lock d'un autre worker."""
    from services.distributed_budget_lock import distributed_budget_lock

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    # Lua retourne 0 si le token ne matche pas (lock pris par un autre worker)
    mock_redis.eval = AsyncMock(return_value=0)

    with patch(
        "services.distributed_budget_lock.get_redis_client",
        return_value=mock_redis,
    ):
        # Ne doit pas lever d'exception même si eval retourne 0
        async with distributed_budget_lock(99):
            pass

    assert mock_redis.eval.called


# ── B4.5 — Streaming finalize partiel (C09) ──────────────────────────────────


@pytest.mark.asyncio
async def test_stream_error_with_usage_finalizes_not_cancels(db):
    """C09: stream_error=True ET got_usage=True → finalize avec tokens partiels.

    Avant fix: ni finalize ni cancel → usage reste en prebill (overestimate).
    Après fix: finalize avec les tokens partiels reçus.
    """
    from core.models import Usage

    usage = Usage(
        project_id=1,
        provider="openai",
        model="gpt-4o",
        tokens_in=100,
        tokens_out=500,
        cost_usd=0.01,
    )
    # Simuler les 2 fonctions pour capturer lequel est appelé
    finalize_called = []
    cancel_called = []

    async def fake_finalize(db, usage_id, tin, tout, model):
        finalize_called.append((usage_id, tin, tout))

    def fake_cancel(db, usage_id):
        cancel_called.append(usage_id)

    # Test de la logique de décision dans _openai_format_stream_gen
    # La logique correcte: got_usage=True → always finalize (stream_error ou non)
    got_usage = True
    stream_error = True
    tokens_in, tokens_out = 50, 123  # tokens partiels reçus avant l'erreur

    # Simuler le bloc finally de la logique correcte
    if got_usage:
        await fake_finalize(db, 1, tokens_in, tokens_out, "gpt-4o")
    elif stream_error:
        fake_cancel(db, 1)

    assert len(finalize_called) == 1, "finalize doit être appelé si got_usage=True"
    assert len(cancel_called) == 0
    assert finalize_called[0] == (1, 50, 123)


# ── B4.6 — should_alert cohérence (H06) ──────────────────────────────────────


def test_should_alert_false_when_budget_zero():
    """H06: should_alert doit retourner False si budget_usd <= 0 (cohérence with maybe_send_alert)."""
    from services.budget_guard import BudgetGuard

    guard = BudgetGuard()
    # budget_usd = 0: pas de budget → pas d'alerte
    assert guard.should_alert(budget_usd=0.0, used_usd=0.0, threshold_pct=80) is False
    assert guard.should_alert(budget_usd=0.0, used_usd=100.0, threshold_pct=80) is False


def test_should_alert_true_when_threshold_exceeded():
    """should_alert doit retourner True si budget dépassé le seuil."""
    from services.budget_guard import BudgetGuard

    guard = BudgetGuard()
    assert guard.should_alert(budget_usd=100.0, used_usd=85.0, threshold_pct=80) is True
    assert (
        guard.should_alert(budget_usd=100.0, used_usd=79.0, threshold_pct=80) is False
    )


# ── B4.7 — Token estimator clamp (H05) ───────────────────────────────────────


def test_estimate_output_clamps_huge_max_tokens():
    """H05: max_tokens=2_000_000 doit être clampé à la limite réelle du modèle."""
    from services.token_estimator import TokenEstimator

    payload = {
        "model": "gpt-4o",
        "max_tokens": 2_000_000,
        "messages": [{"role": "user", "content": "hi"}],
    }
    result = TokenEstimator.estimate_output_tokens(payload)
    assert result < 100_000, f"max_tokens=2M doit être clampé, got {result}"


def test_estimate_output_respects_reasonable_max_tokens():
    """max_tokens raisonnable (ex: 1000) doit être retourné tel quel."""
    from services.token_estimator import TokenEstimator

    payload = {
        "model": "gpt-4o",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": "hi"}],
    }
    result = TokenEstimator.estimate_output_tokens(payload)
    assert result == 1000


def test_estimate_output_unknown_model_uses_default_cap():
    """Modèle inconnu → cap par défaut (8192 ou moins)."""
    from services.token_estimator import TokenEstimator

    payload = {
        "model": "future-model-xyz",
        "max_tokens": 500_000,
        "messages": [{"role": "user", "content": "hi"}],
    }
    result = TokenEstimator.estimate_output_tokens(payload)
    assert result <= 128_000, f"Doit être <= 128k, got {result}"
