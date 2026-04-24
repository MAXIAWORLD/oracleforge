"""MissionForge MCP — server factory and tool registration."""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp import types
from mcp.server.lowlevel import Server

from . import tools

logger = logging.getLogger("missionforge.mcp.server")

SERVER_NAME = "missionforge"
SERVER_VERSION = "0.1.0"
SERVER_INSTRUCTIONS = (
    "MissionForge is a YAML-based AI agent framework. "
    "Use these tools to list, run, and monitor autonomous missions. "
    "Each mission is a pipeline of steps: RAG retrieval, LLM calls, webhooks, and memory storage."
)

_TOOL_DEFINITIONS: list[types.Tool] = [
    types.Tool(
        name="list_missions",
        description=(
            "List all registered missions available in MissionForge. "
            "Returns mission names, descriptions, schedules, step counts and LLM tiers."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    types.Tool(
        name="run_mission",
        description=(
            "Execute a mission by name and return the full execution result. "
            "Runs all steps sequentially (RAG, LLM calls, webhooks, memory). "
            "Use list_missions first to discover available mission names."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Mission name (exact match, case-sensitive).",
                }
            },
            "required": ["name"],
        },
    ),
    types.Tool(
        name="get_mission_history",
        description=(
            "Return recent execution history for a mission. "
            "Shows run IDs, statuses, token usage and duration."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Mission name to get history for.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of runs to return (default 10, max 50).",
                    "default": 10,
                },
            },
            "required": ["name"],
        },
    ),
    types.Tool(
        name="chat",
        description=(
            "Send a message to the MissionForge assistant and get a RAG-grounded reply. "
            "The assistant knows about your ingested documents and mission configurations."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Your question or message.",
                }
            },
            "required": ["message"],
        },
    ),
    types.Tool(
        name="get_observability",
        description=(
            "Return a summary of system metrics: number of missions loaded, "
            "LLM usage stats (calls, cost, latency by tier), and RAG knowledge base stats."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
]

_TOOL_MAP = {t.name: t for t in _TOOL_DEFINITIONS}


def build_server(
    engine: Any = None,
    rag: Any = None,
    llm: Any = None,
) -> Server:
    """Return a configured MCP Server instance.

    The engine/rag/llm dependencies are injected here so both the SSE
    transport and the stdio transport can reuse the same factory.
    When called without dependencies (e.g. for the streamable HTTP manager),
    they are resolved lazily from app state inside each tool handler.
    """
    server = Server(SERVER_NAME)
    server.instructions = SERVER_INSTRUCTIONS

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return _TOOL_DEFINITIONS

    @server.call_tool()
    async def _call_tool(
        name: str, arguments: dict[str, Any]
    ) -> list[types.TextContent]:
        result = await _dispatch(name, arguments, engine=engine, rag=rag, llm=llm)
        return [
            types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))
        ]

    return server


async def _dispatch(
    name: str,
    arguments: dict[str, Any],
    *,
    engine: Any,
    rag: Any,
    llm: Any,
) -> dict[str, Any]:
    """Route a tool call to its implementation."""
    if name == "list_missions":
        return await tools.tool_list_missions(engine=engine)

    if name == "run_mission":
        mission_name = arguments.get("name", "")
        return await tools.tool_run_mission(name=mission_name, engine=engine)

    if name == "get_mission_history":
        mission_name = arguments.get("name", "")
        limit = min(int(arguments.get("limit", 10)), 50)
        return await tools.tool_get_mission_history(
            name=mission_name, limit=limit, engine=engine
        )

    if name == "chat":
        message = arguments.get("message", "")
        return await tools.tool_chat(message=message, engine=engine, rag=rag, llm=llm)

    if name == "get_observability":
        return await tools.tool_get_observability(engine=engine, rag=rag, llm=llm)

    return {"error": f"Unknown tool: {name}"}
