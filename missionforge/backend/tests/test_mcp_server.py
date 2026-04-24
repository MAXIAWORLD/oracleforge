"""TDD — Phase 5: MCP Server.

Ces tests vérifient :
- build_server() retourne un serveur MCP valide avec les 5 tools attendus
- Chaque tool retourne un dict bien formé (nominal + erreur)
- Les endpoints HTTP /mcp/sse et /mcp existent et requièrent auth
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("SECRET_KEY", "test-secret-key-32-chars-ok!!")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

# ── Tests : build_server ───────────────────────────────────────────


def test_build_server_returns_server_instance():
    """build_server() retourne un objet MCP Server."""
    from mcp_server.server import build_server
    from mcp.server.lowlevel import Server

    server = build_server()
    assert isinstance(server, Server)


def test_server_name_is_missionforge():
    """Le nom du serveur MCP est 'missionforge'."""
    from mcp_server.server import SERVER_NAME

    assert SERVER_NAME == "missionforge"


def test_server_has_5_tools():
    """5 tools MCP sont définis : list_missions, run_mission, get_mission_history, chat, get_observability."""
    from mcp_server.server import _TOOL_DEFINITIONS

    names = {t.name for t in _TOOL_DEFINITIONS}
    expected = {
        "list_missions",
        "run_mission",
        "get_mission_history",
        "chat",
        "get_observability",
    }
    assert names == expected


def test_tool_definitions_have_descriptions():
    """Chaque tool a une description non vide."""
    from mcp_server.server import _TOOL_DEFINITIONS

    for tool in _TOOL_DEFINITIONS:
        assert tool.description, f"Tool '{tool.name}' n'a pas de description"


# ── Tests : tools.py (comportement) ──────────────────────────────


@pytest.fixture
def mock_engine():
    engine = MagicMock()

    mission = MagicMock()
    mission.name = "my-mission"
    mission.description = "test"
    mission.schedule = None
    mission.steps = [MagicMock()]
    mission.agent = MagicMock()
    mission.agent.llm_tier = "auto"

    engine.list_missions.return_value = {"my-mission": mission}
    engine.run_mission = AsyncMock(
        return_value=MagicMock(
            mission_name="my-mission",
            run_id="abc123",
            status="success",
            steps_completed=1,
            total_steps=1,
            tokens_used=50,
            cost_usd=0.001,
            error_message=None,
            logs=["done"],
            finished_at=1000.0,
            started_at=999.0,
        )
    )
    engine.get_run_history = AsyncMock(
        return_value=[
            MagicMock(
                run_id="abc123",
                mission_name="my-mission",
                status="success",
                steps_completed=1,
                total_steps=1,
                tokens_used=50,
                cost_usd=0.001,
                finished_at=1000.0,
                started_at=999.0,
            )
        ]
    )
    return engine


@pytest.fixture
def mock_rag():
    rag = MagicMock()
    rag.stats.return_value = {"chunks": 10, "sources": 2}
    return rag


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.get_stats.return_value = {
        "total_calls": 5,
        "total_cost_usd": 0.01,
        "calls_by_tier": {},
    }
    return llm


@pytest.mark.asyncio
async def test_tool_list_missions_returns_dict(mock_engine):
    """list_missions retourne un dict avec une clé 'missions'."""
    from mcp_server.tools import tool_list_missions

    result = await tool_list_missions(engine=mock_engine)
    assert isinstance(result, dict)
    assert "missions" in result


@pytest.mark.asyncio
async def test_tool_list_missions_includes_mission_names(mock_engine):
    """list_missions liste les noms des missions enregistrées."""
    from mcp_server.tools import tool_list_missions

    result = await tool_list_missions(engine=mock_engine)
    assert "my-mission" in [m["name"] for m in result["missions"]]


@pytest.mark.asyncio
async def test_tool_run_mission_success(mock_engine):
    """run_mission retourne un dict avec status=success pour une mission valide."""
    from mcp_server.tools import tool_run_mission

    result = await tool_run_mission(name="my-mission", engine=mock_engine)
    assert isinstance(result, dict)
    assert result["status"] == "success"
    assert result["run_id"] == "abc123"


@pytest.mark.asyncio
async def test_tool_run_mission_unknown_returns_error(mock_engine):
    """run_mission retourne {'error': ...} pour une mission inconnue (pas d'exception)."""
    mock_engine.run_mission = AsyncMock(side_effect=KeyError("ghost"))
    from mcp_server.tools import tool_run_mission

    result = await tool_run_mission(name="ghost", engine=mock_engine)
    assert "error" in result


@pytest.mark.asyncio
async def test_tool_get_history_returns_runs(mock_engine):
    """get_mission_history retourne un dict avec une clé 'runs'."""
    from mcp_server.tools import tool_get_mission_history

    result = await tool_get_mission_history(
        name="my-mission", limit=5, engine=mock_engine
    )
    assert isinstance(result, dict)
    assert "runs" in result
    assert len(result["runs"]) >= 1


@pytest.mark.asyncio
async def test_tool_get_observability_returns_summary(mock_engine, mock_rag, mock_llm):
    """get_observability retourne un dict avec des métriques."""
    from mcp_server.tools import tool_get_observability

    result = await tool_get_observability(
        engine=mock_engine, rag=mock_rag, llm=mock_llm
    )
    assert isinstance(result, dict)
    assert "missions_loaded" in result or "total_missions" in result


@pytest.mark.asyncio
async def test_tool_chat_returns_reply(mock_engine, mock_rag):
    """chat retourne un dict avec une clé 'reply'."""
    from mcp_server.tools import tool_chat

    mock_llm_router = MagicMock()
    mock_llm_router.call = AsyncMock(return_value="Here is the answer.")
    mock_rag.build_rag_context = MagicMock(return_value="some context")

    result = await tool_chat(
        message="What missions are available?",
        engine=mock_engine,
        rag=mock_rag,
        llm=mock_llm_router,
    )
    assert isinstance(result, dict)
    assert "reply" in result


@pytest.mark.asyncio
async def test_tool_never_raises(mock_engine):
    """Aucun tool ne doit lever d'exception — toujours retourner un dict."""
    mock_engine.run_mission = AsyncMock(side_effect=RuntimeError("crash"))
    from mcp_server.tools import tool_run_mission

    result = await tool_run_mission(name="any", engine=mock_engine)
    assert isinstance(result, dict)
    assert "error" in result


# ── Tests : routes HTTP MCP (via OpenAPI schema) ──────────────────
# On ne connecte PAS réellement au SSE (ça bloquerait le TestClient).
# On vérifie que les routes sont bien enregistrées dans l'app.


def _make_app(tmp_path):
    """Crée une app FastAPI sans démarrer le lifespan complet."""
    import yaml

    missions_dir = tmp_path / "missions"
    missions_dir.mkdir(exist_ok=True)
    (missions_dir / "mcp-test.yaml").write_text(
        yaml.dump(
            {
                "name": "mcp-test",
                "steps": [{"action": "log", "text_template": "mcp ok"}],
            }
        ),
        encoding="utf-8",
    )
    os.environ["MISSIONS_DIR"] = str(missions_dir)
    os.environ["CHROMA_PERSIST_DIR"] = str(tmp_path / "chroma")
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

    from core.config import get_settings

    get_settings.cache_clear()
    from main import create_app

    return create_app()


def test_mcp_sse_route_registered(tmp_path):
    """La route /mcp/sse est enregistrée dans l'app FastAPI."""
    app = _make_app(tmp_path)
    paths = [r.path for r in app.routes]
    assert "/mcp/sse" in paths, f"Route /mcp/sse absente. Routes: {paths}"


def test_mcp_streamable_route_registered(tmp_path):
    """La route /mcp est enregistrée dans l'app FastAPI."""
    app = _make_app(tmp_path)
    paths = [r.path for r in app.routes]
    assert "/mcp" in paths, f"Route /mcp absente. Routes: {paths}"


def test_mcp_sse_requires_api_key(tmp_path):
    """GET /mcp/sse sans X-API-Key → 401 (auth vérifiée avant ouverture SSE)."""
    from fastapi.testclient import TestClient

    app = _make_app(tmp_path)

    # On utilise raise_server_exceptions=False et on coupe la connexion
    # immédiatement — l'auth est vérifiée avant que le stream s'ouvre.
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.get("/mcp/sse", headers={"Accept": "text/event-stream"}, timeout=5)
        assert resp.status_code == 401
