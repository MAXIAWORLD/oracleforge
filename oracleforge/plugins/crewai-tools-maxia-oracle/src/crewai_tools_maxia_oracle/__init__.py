"""crewai-tools-maxia-oracle — CrewAI tools for the MAXIA Oracle price feed.

Data feed only. Not investment advice. No custody. No KYC.

Quick start::

    from crewai_tools_maxia_oracle import get_all_tools

    tools = get_all_tools(api_key="mxo_...")
    # pass `tools` to a crewai.Agent(tools=tools, ...)
"""
from __future__ import annotations

from .tools import (
    DISCLAIMER,
    MAXIA_ORACLE_TOOL_CLASSES,
    MaxiaOracleGetCacheStatsTool,
    MaxiaOracleGetChainlinkOnchainTool,
    MaxiaOracleGetConfidenceTool,
    MaxiaOracleGetPriceTool,
    MaxiaOracleGetPricesBatchTool,
    MaxiaOracleGetPythSolanaTool,
    MaxiaOracleGetRedstoneTool,
    MaxiaOracleGetSourcesStatusTool,
    MaxiaOracleHealthCheckTool,
    MaxiaOracleListSupportedSymbolsTool,
    get_all_tools,
)

__version__ = "0.3.0"

__all__ = [
    "__version__",
    "DISCLAIMER",
    "MAXIA_ORACLE_TOOL_CLASSES",
    "MaxiaOracleGetPriceTool",
    "MaxiaOracleGetPricesBatchTool",
    "MaxiaOracleGetSourcesStatusTool",
    "MaxiaOracleGetCacheStatsTool",
    "MaxiaOracleGetConfidenceTool",
    "MaxiaOracleListSupportedSymbolsTool",
    "MaxiaOracleGetChainlinkOnchainTool",
    "MaxiaOracleGetRedstoneTool",
    "MaxiaOracleGetPythSolanaTool",
    "MaxiaOracleHealthCheckTool",
    "get_all_tools",
]
