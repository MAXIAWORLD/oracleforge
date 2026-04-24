"""TDD — Phase 1: DB persistence des runs de missions.

Ces tests sont ROUGES jusqu'à ce que mission_engine.py persiste en DB.

Comportements attendus :
- run_mission() écrit une ligne dans execution_logs
- get_run_history() lit depuis la DB (pas la mémoire)
- L'historique survit au redémarrage du moteur
- Pagination offset/limit
- Filtrage par status
- Fallback gracieux si db_session_factory=None
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import select

from services.mission_engine import MissionDefinition, MissionStep, MissionEngine
from core.models import ExecutionLog as ExecutionLogORM
from core.database import init_db, close_db


# ── Fixtures ──────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_engine():
    engine = await init_db("sqlite+aiosqlite:///:memory:")
    yield engine
    await close_db()


@pytest.fixture
def mock_llm():
    r = MagicMock()
    r.call = AsyncMock(return_value="ok")
    return r


@pytest.fixture
def mock_rag():
    r = MagicMock()
    r.build_rag_context = MagicMock(return_value="ctx")
    return r


@pytest.fixture
def mock_memory():
    return MagicMock()


@pytest.fixture
def mock_http():
    return MagicMock()


@pytest_asyncio.fixture
async def engine_with_db(db_engine, mock_llm, mock_rag, mock_memory, mock_http):
    from core.database import _session_factory

    return MissionEngine(
        llm_router=mock_llm,
        rag_service=mock_rag,
        memory=mock_memory,
        http_client=mock_http,
        db_session_factory=_session_factory,
    )


def _log_mission(name: str = "m", n_steps: int = 1) -> MissionDefinition:
    steps = [MissionStep(action="log", text_template="done")] * n_steps
    return MissionDefinition(name=name, steps=steps)


def _llm_mission(name: str = "m") -> MissionDefinition:
    return MissionDefinition(
        name=name,
        steps=[MissionStep(action="llm_call", prompt="hello")],
    )


# ── Tests : persistence basique ───────────────────────────────────


@pytest.mark.asyncio
async def test_successful_run_creates_db_row(engine_with_db, db_engine):
    """Un run réussi crée une ligne status=success dans execution_logs."""
    engine_with_db.register_mission(_log_mission("success-mission"))
    log = await engine_with_db.run_mission("success-mission")

    assert log.status == "success"

    from core.database import _session_factory

    async with _session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(ExecutionLogORM).where(
                        ExecutionLogORM.mission_name == "success-mission"
                    )
                )
            )
            .scalars()
            .all()
        )

    assert len(rows) == 1
    assert rows[0].status == "success"
    assert rows[0].steps_completed == 1
    assert rows[0].run_id == log.run_id


@pytest.mark.asyncio
async def test_failed_run_creates_db_row_with_error(engine_with_db, db_engine):
    """Un run échoué crée une ligne status=failed avec error_message."""
    engine_with_db._llm.call = AsyncMock(side_effect=RuntimeError("provider down"))
    engine_with_db.register_mission(_llm_mission("fail-mission"))

    log = await engine_with_db.run_mission("fail-mission")
    assert log.status == "failed"

    from core.database import _session_factory

    async with _session_factory() as session:
        row = (
            await session.execute(
                select(ExecutionLogORM).where(
                    ExecutionLogORM.mission_name == "fail-mission"
                )
            )
        ).scalar_one()

    assert row.status == "failed"
    assert row.error_message is not None
    assert "provider down" in row.error_message


@pytest.mark.asyncio
async def test_db_row_has_run_id(engine_with_db, db_engine):
    """La ligne DB contient le run_id unique du run."""
    engine_with_db.register_mission(_log_mission("id-mission"))
    log = await engine_with_db.run_mission("id-mission")

    from core.database import _session_factory

    async with _session_factory() as session:
        row = (
            await session.execute(
                select(ExecutionLogORM).where(ExecutionLogORM.run_id == log.run_id)
            )
        ).scalar_one_or_none()

    assert row is not None
    assert row.run_id == log.run_id


# ── Tests : get_run_history depuis DB ─────────────────────────────


@pytest.mark.asyncio
async def test_get_run_history_reads_from_db(engine_with_db, db_engine):
    """get_run_history retourne les runs persistés en DB."""
    engine_with_db.register_mission(_log_mission("hist-mission"))
    await engine_with_db.run_mission("hist-mission")

    history = await engine_with_db.get_run_history("hist-mission")
    assert len(history) == 1
    assert history[0].status == "success"


@pytest.mark.asyncio
async def test_history_survives_engine_restart(
    db_engine, mock_llm, mock_rag, mock_memory, mock_http
):
    """L'historique est visible depuis un nouveau moteur (pas d'état partagé)."""
    from core.database import _session_factory

    engine1 = MissionEngine(
        llm_router=mock_llm,
        rag_service=mock_rag,
        memory=mock_memory,
        http_client=mock_http,
        db_session_factory=_session_factory,
    )
    engine1.register_mission(_log_mission("restart-mission"))
    first_run = await engine1.run_mission("restart-mission")

    # Nouveau moteur — aucune mémoire partagée avec engine1
    engine2 = MissionEngine(
        llm_router=mock_llm,
        rag_service=mock_rag,
        memory=mock_memory,
        http_client=mock_http,
        db_session_factory=_session_factory,
    )
    engine2.register_mission(_log_mission("restart-mission"))

    history = await engine2.get_run_history("restart-mission")
    assert len(history) == 1
    assert history[0].run_id == first_run.run_id


# ── Tests : pagination ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_history_pagination_limit(engine_with_db, db_engine):
    """Le paramètre limit borne le nombre de résultats."""
    engine_with_db.register_mission(_log_mission("page-mission"))
    for _ in range(5):
        await engine_with_db.run_mission("page-mission")

    page = await engine_with_db.get_run_history("page-mission", limit=3)
    assert len(page) == 3


@pytest.mark.asyncio
async def test_history_pagination_offset(engine_with_db, db_engine):
    """offset + limit permettent de parcourir l'historique sans doublons."""
    engine_with_db.register_mission(_log_mission("offset-mission"))
    for _ in range(6):
        await engine_with_db.run_mission("offset-mission")

    page1 = await engine_with_db.get_run_history("offset-mission", limit=3, offset=0)
    page2 = await engine_with_db.get_run_history("offset-mission", limit=3, offset=3)

    ids1 = {r.run_id for r in page1}
    ids2 = {r.run_id for r in page2}
    assert len(ids1) == 3
    assert len(ids2) == 3
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_history_default_order_is_newest_first(engine_with_db, db_engine):
    """L'historique est trié du plus récent au plus ancien."""
    engine_with_db.register_mission(_log_mission("order-mission"))
    run1 = await engine_with_db.run_mission("order-mission")
    run2 = await engine_with_db.run_mission("order-mission")

    history = await engine_with_db.get_run_history("order-mission")
    # run2 lancé après run1 → doit apparaître en premier
    assert history[0].run_id == run2.run_id
    assert history[1].run_id == run1.run_id


# ── Tests : filtrage ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_history_filter_by_status_success(engine_with_db, db_engine):
    """Filtrer par status='success' ne retourne que les runs réussis."""
    engine_with_db.register_mission(_log_mission("filter-mission"))
    await engine_with_db.run_mission("filter-mission")

    engine_with_db._llm.call = AsyncMock(side_effect=RuntimeError("err"))
    engine_with_db.register_mission(_llm_mission("filter-mission"))
    await engine_with_db.run_mission("filter-mission")

    successes = await engine_with_db.get_run_history("filter-mission", status="success")
    assert len(successes) >= 1
    assert all(r.status == "success" for r in successes)


@pytest.mark.asyncio
async def test_history_filter_by_status_failed(engine_with_db, db_engine):
    """Filtrer par status='failed' ne retourne que les runs échoués."""
    engine_with_db.register_mission(_log_mission("filter2-mission"))
    await engine_with_db.run_mission("filter2-mission")

    engine_with_db._llm.call = AsyncMock(side_effect=RuntimeError("err"))
    engine_with_db.register_mission(_llm_mission("filter2-mission"))
    await engine_with_db.run_mission("filter2-mission")

    failures = await engine_with_db.get_run_history("filter2-mission", status="failed")
    assert len(failures) >= 1
    assert all(r.status == "failed" for r in failures)


@pytest.mark.asyncio
async def test_history_filter_by_mission_name(engine_with_db, db_engine):
    """get_run_history filtre par nom de mission."""
    engine_with_db.register_mission(_log_mission("mission-a"))
    engine_with_db.register_mission(_log_mission("mission-b"))
    await engine_with_db.run_mission("mission-a")
    await engine_with_db.run_mission("mission-b")

    history_a = await engine_with_db.get_run_history("mission-a")
    assert all(r.mission_name == "mission-a" for r in history_a)


# ── Tests : fallback sans DB ─────────────────────────────────────


@pytest.mark.asyncio
async def test_engine_without_db_factory_falls_back_to_memory(
    mock_llm, mock_rag, mock_memory, mock_http
):
    """Sans db_session_factory, l'engine utilise la mémoire sans crasher."""
    engine = MissionEngine(
        llm_router=mock_llm,
        rag_service=mock_rag,
        memory=mock_memory,
        http_client=mock_http,
        db_session_factory=None,
    )
    engine.register_mission(_log_mission("no-db-mission"))
    log = await engine.run_mission("no-db-mission")

    history = await engine.get_run_history("no-db-mission")
    assert len(history) == 1
    assert history[0].run_id == log.run_id


@pytest.mark.asyncio
async def test_multiple_runs_accumulate_in_db(engine_with_db, db_engine):
    """Plusieurs runs successifs créent autant de lignes en DB."""
    engine_with_db.register_mission(_log_mission("multi-run"))
    for _ in range(3):
        await engine_with_db.run_mission("multi-run")

    history = await engine_with_db.get_run_history("multi-run", limit=10)
    assert len(history) == 3
