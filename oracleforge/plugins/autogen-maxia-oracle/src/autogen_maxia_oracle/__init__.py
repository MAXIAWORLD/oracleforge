"""autogen-maxia-oracle — AutoGen tools for the MAXIA Oracle price feed.

Data feed only. Not investment advice. No custody. No KYC.

Quick start::

    from autogen_maxia_oracle import get_all_tools

    tools = get_all_tools(api_key="mxo_...")
    # pass `tools` to an autogen_agentchat.AssistantAgent(tools=tools, ...)
"""
from __future__ import annotations

from .tools import DISCLAIMER, TOOL_NAMES, get_all_tools

__version__ = "0.4.0"

__all__ = [
    "__version__",
    "DISCLAIMER",
    "TOOL_NAMES",
    "get_all_tools",
]
