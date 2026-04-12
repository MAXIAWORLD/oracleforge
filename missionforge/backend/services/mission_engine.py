"""MissionForge — YAML mission engine (NET-NEW).

Core product differentiator: define autonomous agent missions in YAML,
execute them as step pipelines with automatic scheduling.

Supported step actions:
  - rag_retrieve: query the RAG knowledge base
  - llm_call: call an LLM provider via the router
  - webhook: HTTP request to an external URL
  - memory_store: persist data in vector memory
  - log: record a message in the execution log
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from glob import glob
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# ── Pydantic models (YAML schema) ───────────────────────────────


class MissionStep(BaseModel):
    """A single step in a mission pipeline."""

    action: Literal["rag_retrieve", "llm_call", "webhook", "memory_store", "log"]

    # rag_retrieve
    query: str | None = None
    k: int = 6

    # llm_call
    prompt: str | None = None
    tier: str | None = None
    max_tokens: int = 500
    system_prompt: str | None = None

    # webhook
    url: str | None = None
    method: str = "POST"
    payload_template: str | None = None

    # memory_store
    collection: str | None = None
    text_template: str | None = None

    # shared
    output_var: str | None = None


class MissionAgent(BaseModel):
    """Agent configuration for a mission."""

    system_prompt: str = "You are a helpful AI assistant."
    llm_tier: str = "auto"


class MissionDefinition(BaseModel):
    """A complete mission loaded from YAML."""

    name: str = Field(..., min_length=1)
    description: str = ""
    schedule: str | None = None
    agent: MissionAgent = MissionAgent()
    steps: list[MissionStep] = []

    @field_validator("schedule")
    @classmethod
    def validate_cron(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            from croniter import croniter
            croniter(v)
        except (ValueError, KeyError) as e:
            raise ValueError(f"Invalid cron expression: {v}") from e
        return v


# ── Execution context ────────────────────────────────────────────


@dataclass
class ExecutionContext:
    """Runtime state for a single mission execution."""

    mission_name: str
    run_id: str
    variables: dict[str, str] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
    tokens_used: int = 0
    cost_usd: float = 0.0


# ── Execution log (returned after run) ───────────────────────────


@dataclass
class ExecutionLog:
    """Result of a mission run."""

    mission_name: str
    run_id: str
    status: str = "running"  # running | success | failed
    steps_completed: int = 0
    total_steps: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0
    error_message: str | None = None
    logs: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None


# ── Safe dict for interpolation ──────────────────────────────────


def _safe_interpolate(template: str, variables: dict[str, str]) -> str:
    """Safe template interpolation using regex substitution.

    Only replaces {simple_name} patterns — no attribute access, no indexing.
    Prevents SSTI via format_map (which allows {obj.__class__} etc.).
    """
    import re

    def replacer(match: re.Match) -> str:
        key = match.group(1)
        return variables.get(key, "")

    return re.sub(r"\{(\w+)\}", replacer, template)


# ── Mission Engine ───────────────────────────────────────────────


class MissionEngine:
    """Load, register, and execute YAML missions."""

    def __init__(
        self,
        llm_router: Any,
        rag_service: Any,
        memory: Any,
        http_client: Any,
        allowed_env_vars: list[str] | None = None,
    ) -> None:
        self._llm = llm_router
        self._rag = rag_service
        self._memory = memory
        self._http = http_client
        self._allowed_env_vars = set(allowed_env_vars or [])
        self._missions: dict[str, MissionDefinition] = {}
        self._running = False
        self._tasks: list[asyncio.Task] = []

    # ── YAML loading ─────────────────────────────────────────────

    def load_from_yaml(self, path: str) -> MissionDefinition:
        """Parse a YAML file into a MissionDefinition."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Mission file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return MissionDefinition(**data)

    def register_mission(self, mission: MissionDefinition) -> None:
        """Register a mission (overwrites if same name exists)."""
        self._missions[mission.name] = mission

    def load_all_missions(self, directory: str) -> list[MissionDefinition]:
        """Load all .yaml/.yml files from a directory."""
        loaded: list[MissionDefinition] = []
        patterns = [
            os.path.join(directory, "*.yaml"),
            os.path.join(directory, "*.yml"),
        ]
        for pattern in patterns:
            for path in sorted(glob(pattern)):
                try:
                    mission = self.load_from_yaml(path)
                    self.register_mission(mission)
                    loaded.append(mission)
                    logger.info("[engine] loaded mission '%s' from %s", mission.name, path)
                except Exception as e:
                    logger.warning("[engine] failed to load %s: %s", path, e)
        return loaded

    def list_missions(self) -> dict[str, MissionDefinition]:
        """Return all registered missions."""
        return dict(self._missions)

    # ── Interpolation ────────────────────────────────────────────

    @staticmethod
    def _validate_webhook_url(url: str) -> None:
        """Block SSRF: reject internal/private network URLs."""
        from urllib.parse import urlparse
        import ipaddress

        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname or ""

        if scheme not in ("http", "https"):
            raise ValueError(f"Webhook URL must use http(s), got: {scheme}")

        # Block known internal hostnames
        blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "[::]", "[::1]"}
        if hostname.lower() in blocked_hosts:
            raise ValueError(f"Webhook URL blocked: {hostname} is internal")

        # Block private/reserved IP ranges
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError(f"Webhook URL blocked: {ip} is a private/reserved address")
        except ValueError:
            pass  # hostname is a domain, not an IP — allow

    def _interpolate(self, template: str | None, variables: dict[str, str]) -> str:
        """Replace {var} placeholders in a template string."""
        if not template:
            return ""

        # Build the variable dict with builtins
        all_vars = dict(variables)
        all_vars["date"] = time.strftime("%Y-%m-%d")
        all_vars["time"] = time.strftime("%H:%M:%S")

        # {context} is an alias for the last RAG result
        if "context" not in all_vars and "__rag_context__" in variables:
            all_vars["context"] = variables["__rag_context__"]

        # {env.VAR} — only whitelisted vars
        for var_name in self._allowed_env_vars:
            all_vars[f"env.{var_name}"] = os.environ.get(var_name, "")

        return _safe_interpolate(template, all_vars)

    # ── Step execution ───────────────────────────────────────────

    async def _execute_step(
        self, step: MissionStep, ctx: ExecutionContext
    ) -> str:
        """Execute a single mission step and return the result."""
        action = step.action
        result = ""

        if action == "rag_retrieve":
            query = self._interpolate(step.query or "", ctx.variables)
            rag_context = self._rag.build_rag_context(query, max_chars=2500)
            ctx.variables["__rag_context__"] = rag_context
            result = rag_context

        elif action == "llm_call":
            prompt = self._interpolate(step.prompt or "", ctx.variables)
            system = self._interpolate(
                step.system_prompt or ctx.variables.get("__system_prompt__", ""),
                ctx.variables,
            )
            tier_val = step.tier if step.tier and step.tier != "auto" else None
            # Import Tier dynamically to avoid circular imports in tests
            tier = None
            if tier_val:
                from services.llm_router import Tier
                try:
                    tier = Tier(tier_val)
                except ValueError:
                    pass

            result = await self._llm.call(
                prompt=prompt,
                tier=tier,
                system=system,
                max_tokens=step.max_tokens,
            )
            # Estimate tokens
            tokens = (len(prompt) + len(system) + len(result)) // 4
            ctx.tokens_used += tokens

        elif action == "webhook":
            url = self._interpolate(step.url or "", ctx.variables)
            self._validate_webhook_url(url)
            method = step.method.upper()
            payload = None
            if step.payload_template:
                import json
                try:
                    payload_str = self._interpolate(step.payload_template, ctx.variables)
                    payload = json.loads(payload_str)
                except (json.JSONDecodeError, Exception):
                    payload = {"text": self._interpolate(step.payload_template, ctx.variables)}

            resp = await self._http.request(method, url, json=payload)
            resp.raise_for_status()
            result = resp.text if hasattr(resp, "text") else str(resp)

        elif action == "memory_store":
            text = self._interpolate(step.text_template or "", ctx.variables)
            collection = step.collection or "learnings"
            self._memory.store(collection, text, {"mission": ctx.mission_name})
            result = text

        elif action == "log":
            text = self._interpolate(
                step.text_template or f"[{ctx.mission_name}] step completed",
                ctx.variables,
            )
            ctx.logs.append(text)
            logger.info("[mission:%s] %s", ctx.mission_name, text)
            result = text

        # Store output variable if requested
        if step.output_var and result:
            ctx.variables[step.output_var] = result

        return result

    # ── Mission run ──────────────────────────────────────────────

    async def run_mission(self, name: str) -> ExecutionLog:
        """Execute all steps of a registered mission sequentially."""
        if name not in self._missions:
            raise KeyError(f"Mission '{name}' not found")

        mission = self._missions[name]
        run_id = uuid.uuid4().hex[:12]
        ctx = ExecutionContext(mission_name=name, run_id=run_id)
        ctx.variables["__system_prompt__"] = mission.agent.system_prompt

        log = ExecutionLog(
            mission_name=name,
            run_id=run_id,
            total_steps=len(mission.steps),
        )

        try:
            for step in mission.steps:
                await self._execute_step(step, ctx)
                log.steps_completed += 1

            log.status = "success"
        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)
            logger.error("[mission:%s] failed at step %d: %s", name, log.steps_completed + 1, e)

        log.tokens_used = ctx.tokens_used
        log.cost_usd = ctx.cost_usd
        log.logs = ctx.logs
        log.finished_at = time.time()

        return log

    # ── Scheduling (async background tasks) ──────────────────────

    async def start(self) -> None:
        """Start cron-scheduled missions as background tasks."""
        self._running = True
        for name, mission in self._missions.items():
            if mission.schedule:
                task = asyncio.create_task(
                    self._safe_task(self._schedule_loop(mission), name)
                )
                self._tasks.append(task)
                logger.info("[engine] scheduled '%s' with cron '%s'", name, mission.schedule)

    async def stop(self) -> None:
        """Cancel all scheduled tasks."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

    async def _schedule_loop(self, mission: MissionDefinition) -> None:
        """Background loop for a single cron-scheduled mission."""
        from croniter import croniter
        from datetime import datetime

        cron = croniter(mission.schedule, datetime.now())
        while self._running:
            next_run = cron.get_next(datetime)
            sleep_secs = (next_run - datetime.now()).total_seconds()
            if sleep_secs > 0:
                await asyncio.sleep(sleep_secs)
            if not self._running:
                break
            try:
                await self.run_mission(mission.name)
            except Exception as e:
                logger.error("[schedule:%s] run failed: %s", mission.name, e)

    @staticmethod
    async def _safe_task(coro, name: str) -> None:
        """Wrap a coroutine so it doesn't crash other tasks on failure."""
        try:
            await coro
        except asyncio.CancelledError:
            logger.info("[engine] task '%s' cancelled", name)
        except Exception as e:
            logger.error("[engine] task '%s' crashed: %s", name, e)
