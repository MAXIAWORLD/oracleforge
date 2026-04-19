"""Unit tests for the crewai-tools-maxia-oracle wrappers. Offline."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from crewai_tools_maxia_oracle import (
    DISCLAIMER,
    MAXIA_ORACLE_TOOL_CLASSES,
    MaxiaOracleGetChainlinkOnchainTool,
    MaxiaOracleGetConfidenceTool,
    MaxiaOracleGetPriceTool,
    MaxiaOracleGetPricesBatchTool,
    MaxiaOracleGetSourcesStatusTool,
    MaxiaOracleHealthCheckTool,
    get_all_tools,
)


def _fake(payload: dict[str, Any]) -> dict[str, Any]:
    return {"data": payload, "disclaimer": DISCLAIMER}


def test_all_tools_exported() -> None:
    assert len(MAXIA_ORACLE_TOOL_CLASSES) == 17


def test_tool_names_unique_and_namespaced() -> None:
    names = [cls.model_fields["name"].default for cls in MAXIA_ORACLE_TOOL_CLASSES]
    assert len(names) == len(set(names))
    for name in names:
        assert name.startswith("maxia_oracle_")


def test_tool_descriptions_contain_disclaimer() -> None:
    for cls in MAXIA_ORACLE_TOOL_CLASSES:
        assert DISCLAIMER in cls.model_fields["description"].default


def test_get_all_tools_shares_a_single_client() -> None:
    fake = MagicMock(name="MaxiaOracleClient")
    tools = get_all_tools(client=fake)
    assert len(tools) == 17
    for tool in tools:
        assert tool.client is fake


def test_get_price_tool_dispatches_to_client() -> None:
    fake = MagicMock()
    fake.price.return_value = _fake({"symbol": "BTC", "price": 73999.12})
    tool = MaxiaOracleGetPriceTool(client=fake)

    result = tool.run(symbol="BTC")

    fake.price.assert_called_once_with("BTC")
    parsed = json.loads(result)
    assert parsed["data"]["symbol"] == "BTC"


def test_get_prices_batch_tool_dispatches_to_client() -> None:
    fake = MagicMock()
    fake.prices_batch.return_value = _fake({"prices": {"BTC": 74000}})
    tool = MaxiaOracleGetPricesBatchTool(client=fake)

    result = tool.run(symbols=["BTC", "ETH"])

    fake.prices_batch.assert_called_once_with(["BTC", "ETH"])
    assert "74000" in result


def test_sources_status_tool_no_args() -> None:
    fake = MagicMock()
    fake.sources.return_value = _fake({"sources": []})
    tool = MaxiaOracleGetSourcesStatusTool(client=fake)

    result = tool.run()

    fake.sources.assert_called_once_with()
    assert DISCLAIMER in result


def test_chainlink_onchain_tool_dispatches_to_client() -> None:
    fake = MagicMock()
    fake.chainlink_onchain.return_value = _fake(
        {"symbol": "BTC", "source": "chainlink_base"}
    )
    tool = MaxiaOracleGetChainlinkOnchainTool(client=fake)

    result = tool.run(symbol="BTC")

    fake.chainlink_onchain.assert_called_once_with("BTC", chain="base")
    assert "chainlink_base" in result


def test_chainlink_onchain_tool_propagates_chain_arbitrum() -> None:
    fake = MagicMock()
    fake.chainlink_onchain.return_value = _fake(
        {"symbol": "BTC", "source": "chainlink_arbitrum", "chain": "arbitrum"}
    )
    tool = MaxiaOracleGetChainlinkOnchainTool(client=fake)

    result = tool.run(symbol="BTC", chain="arbitrum")

    fake.chainlink_onchain.assert_called_once_with("BTC", chain="arbitrum")
    assert "chainlink_arbitrum" in result


def test_confidence_tool_dispatches_to_client() -> None:
    fake = MagicMock()
    fake.confidence.return_value = _fake(
        {"symbol": "ETH", "divergence_pct": 0.21}
    )
    tool = MaxiaOracleGetConfidenceTool(client=fake)

    result = tool.run(symbol="ETH")

    fake.confidence.assert_called_once_with("ETH")
    assert "0.21" in result


def test_health_check_tool_no_args() -> None:
    fake = MagicMock()
    fake.health.return_value = _fake({"status": "ok"})
    tool = MaxiaOracleHealthCheckTool(client=fake)

    result = tool.run()

    fake.health.assert_called_once_with()
    parsed = json.loads(result)
    assert parsed["data"]["status"] == "ok"
