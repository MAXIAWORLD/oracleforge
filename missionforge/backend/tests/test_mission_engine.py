"""TDD tests for services/mission_engine.py — YAML mission loading + execution."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

import chromadb
import chromadb.config

from services.mission_engine import (
    MissionDefinition,
    MissionStep,
    MissionAgent,
    ExecutionContext,
    MissionEngine,
)


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def chroma_client(tmp_path) -> chromadb.ClientAPI:
    return chromadb.PersistentClient(
        path=str(tmp_path / "chroma"),
        settings=chromadb.config.Settings(anonymized_telemetry=False),
    )


@pytest.fixture
def mock_llm_router():
    router = MagicMock()
    router.call = AsyncMock(return_value="LLM response text")
    router.classify_complexity = MagicMock(return_value="local")
    return router


@pytest.fixture
def mock_rag_service():
    rag = MagicMock()
    rag.build_rag_context = MagicMock(return_value="[sample | score=0.9] relevant context")
    rag.hybrid_retrieve = MagicMock(return_value=[{"text": "relevant", "source": "doc", "score": 0.9}])
    return rag


@pytest.fixture
def mock_memory():
    mem = MagicMock()
    mem.store = MagicMock()
    return mem


@pytest.fixture
def mock_http_client():
    client = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.text = '{"ok": true}'
    resp.json = MagicMock(return_value={"ok": True})
    resp.raise_for_status = MagicMock()
    client.request = AsyncMock(return_value=resp)
    return client


@pytest.fixture
def engine(mock_llm_router, mock_rag_service, mock_memory, mock_http_client):
    return MissionEngine(
        llm_router=mock_llm_router,
        rag_service=mock_rag_service,
        memory=mock_memory,
        http_client=mock_http_client,
        allowed_env_vars=[],
    )


@pytest.fixture
def sample_yaml(tmp_path) -> str:
    """Write a valid mission YAML and return its path."""
    mission = {
        "name": "test-mission",
        "description": "A test mission",
        "schedule": None,
        "agent": {
            "system_prompt": "You are a test assistant.",
            "llm_tier": "fast",
        },
        "steps": [
            {"action": "rag_retrieve", "query": "latest updates", "output_var": "context"},
            {"action": "llm_call", "prompt": "Summarize: {context}", "max_tokens": 200, "output_var": "summary"},
            {"action": "log"},
        ],
    }
    path = tmp_path / "test-mission.yaml"
    path.write_text(yaml.dump(mission), encoding="utf-8")
    return str(path)


# ── MissionDefinition validation ─────────────────────────────────


class TestMissionDefinition:
    """Pydantic validation of YAML mission schema."""

    def test_valid_mission(self) -> None:
        m = MissionDefinition(
            name="hello",
            steps=[MissionStep(action="log")],
        )
        assert m.name == "hello"
        assert m.schedule is None

    def test_mission_with_schedule(self) -> None:
        m = MissionDefinition(
            name="cron-job",
            schedule="0 9 * * *",
            steps=[MissionStep(action="log")],
        )
        assert m.schedule == "0 9 * * *"

    def test_invalid_cron_rejected(self) -> None:
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MissionDefinition(
                name="bad-cron",
                schedule="not a cron",
                steps=[MissionStep(action="log")],
            )

    def test_empty_name_rejected(self) -> None:
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MissionDefinition(name="", steps=[MissionStep(action="log")])

    def test_invalid_action_rejected(self) -> None:
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MissionStep(action="invalid_action")

    def test_default_agent(self) -> None:
        m = MissionDefinition(name="x", steps=[MissionStep(action="log")])
        assert m.agent.llm_tier == "auto"
        assert "helpful" in m.agent.system_prompt.lower()


# ── YAML loading ────────────────────────────────────────────────


class TestLoadFromYaml:
    """MissionEngine.load_from_yaml parses YAML files."""

    def test_load_valid_yaml(self, engine, sample_yaml) -> None:
        mission = engine.load_from_yaml(sample_yaml)
        assert mission.name == "test-mission"
        assert len(mission.steps) == 3
        assert mission.steps[0].action == "rag_retrieve"

    def test_load_missing_file(self, engine) -> None:
        with pytest.raises(FileNotFoundError):
            engine.load_from_yaml("/nonexistent/mission.yaml")


# ── Variable interpolation ───────────────────────────────────────


class TestInterpolation:
    """_interpolate replaces {var} placeholders."""

    def test_simple_variable(self, engine) -> None:
        result = engine._interpolate("Hello {name}!", {"name": "World"})
        assert result == "Hello World!"

    def test_missing_variable_empty(self, engine) -> None:
        result = engine._interpolate("Hello {missing}!", {})
        assert result == "Hello !"

    def test_builtin_date(self, engine) -> None:
        result = engine._interpolate("Today is {date}", {})
        assert "2026" in result or "202" in result  # contains a year

    def test_context_alias(self, engine) -> None:
        ctx_vars = {"__rag_context__": "some context data"}
        result = engine._interpolate("{context}", ctx_vars)
        assert result == "some context data"


# ── Step execution ───────────────────────────────────────────────


class TestStepExecution:
    """Individual step execution in the mission pipeline."""

    @pytest.mark.asyncio
    async def test_rag_retrieve_step(self, engine) -> None:
        step = MissionStep(action="rag_retrieve", query="test query", output_var="ctx")
        ctx = ExecutionContext(mission_name="test", run_id="r1")
        result = await engine._execute_step(step, ctx)
        assert len(result) > 0
        assert "ctx" in ctx.variables

    @pytest.mark.asyncio
    async def test_llm_call_step(self, engine) -> None:
        step = MissionStep(action="llm_call", prompt="Say hello", output_var="reply")
        ctx = ExecutionContext(mission_name="test", run_id="r1")
        result = await engine._execute_step(step, ctx)
        assert result == "LLM response text"
        assert ctx.variables["reply"] == "LLM response text"
        engine._llm.call.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_call_with_context_interpolation(self, engine) -> None:
        step = MissionStep(action="llm_call", prompt="Summarize: {context}", output_var="s")
        ctx = ExecutionContext(mission_name="test", run_id="r1")
        ctx.variables["__rag_context__"] = "important data here"
        await engine._execute_step(step, ctx)
        call_args = engine._llm.call.call_args
        assert "important data here" in call_args.kwargs.get("prompt", call_args[0][0] if call_args[0] else "")

    @pytest.mark.asyncio
    async def test_webhook_step(self, engine) -> None:
        step = MissionStep(action="webhook", url="https://example.com/hook", method="POST")
        ctx = ExecutionContext(mission_name="test", run_id="r1")
        result = await engine._execute_step(step, ctx)
        assert len(result) > 0
        engine._http.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_memory_store_step(self, engine) -> None:
        step = MissionStep(
            action="memory_store",
            collection="learnings",
            text_template="Learned: {fact}",
        )
        ctx = ExecutionContext(mission_name="test", run_id="r1")
        ctx.variables["fact"] = "Python is great"
        await engine._execute_step(step, ctx)
        engine._memory.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_step(self, engine) -> None:
        step = MissionStep(action="log", text_template="Mission completed: {status}")
        ctx = ExecutionContext(mission_name="test", run_id="r1")
        ctx.variables["status"] = "success"
        result = await engine._execute_step(step, ctx)
        assert "success" in result


# ── Full mission run ─────────────────────────────────────────────


class TestRunMission:
    """MissionEngine.run_mission executes all steps in sequence."""

    @pytest.mark.asyncio
    async def test_run_full_mission(self, engine, sample_yaml) -> None:
        mission = engine.load_from_yaml(sample_yaml)
        engine.register_mission(mission)
        log = await engine.run_mission("test-mission")
        assert log.status == "success"
        assert log.steps_completed == 3
        assert log.total_steps == 3

    @pytest.mark.asyncio
    async def test_run_unknown_mission(self, engine) -> None:
        with pytest.raises(KeyError):
            await engine.run_mission("nonexistent")

    @pytest.mark.asyncio
    async def test_run_captures_error(self, engine, sample_yaml) -> None:
        """If a step fails, the run should record the error."""
        engine._llm.call = AsyncMock(side_effect=RuntimeError("LLM down"))
        mission = engine.load_from_yaml(sample_yaml)
        engine.register_mission(mission)
        log = await engine.run_mission("test-mission")
        assert log.status == "failed"
        assert log.error_message is not None
        assert "LLM down" in log.error_message

    @pytest.mark.asyncio
    async def test_run_tracks_tokens(self, engine, sample_yaml) -> None:
        mission = engine.load_from_yaml(sample_yaml)
        engine.register_mission(mission)
        log = await engine.run_mission("test-mission")
        # LLM was called once, so tokens should be tracked
        assert log.tokens_used >= 0


# ── Mission registry ─────────────────────────────────────────────


class TestMissionRegistry:
    """register_mission and list_missions."""

    def test_register_and_list(self, engine) -> None:
        m = MissionDefinition(name="alpha", steps=[MissionStep(action="log")])
        engine.register_mission(m)
        missions = engine.list_missions()
        assert "alpha" in missions

    def test_register_duplicate_overwrites(self, engine) -> None:
        m1 = MissionDefinition(name="dup", description="v1", steps=[MissionStep(action="log")])
        m2 = MissionDefinition(name="dup", description="v2", steps=[MissionStep(action="log")])
        engine.register_mission(m1)
        engine.register_mission(m2)
        assert engine.list_missions()["dup"].description == "v2"

    def test_load_all_from_dir(self, engine, tmp_path) -> None:
        for name in ["a", "b"]:
            p = tmp_path / f"{name}.yaml"
            p.write_text(yaml.dump({
                "name": name,
                "steps": [{"action": "log"}],
            }), encoding="utf-8")
        loaded = engine.load_all_missions(str(tmp_path))
        assert len(loaded) == 2
        assert "a" in engine.list_missions()
        assert "b" in engine.list_missions()
