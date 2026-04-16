"""llama-index-tools-maxia-oracle — LlamaIndex tools for the MAXIA Oracle price feed.

Data feed only. Not investment advice. No custody. No KYC.

Quick start::

    from llama_index_tools_maxia_oracle import get_all_tools

    tools = get_all_tools(api_key="mxo_...")
    # pass `tools` to a llama_index.core.agent.ReActAgent.from_tools(tools, llm=...)
"""
from __future__ import annotations

from .tools import DISCLAIMER, TOOL_NAMES, get_all_tools

__version__ = "0.3.0"

__all__ = [
    "__version__",
    "DISCLAIMER",
    "TOOL_NAMES",
    "get_all_tools",
]
