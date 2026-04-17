"""Unit tests for the langchain-maxia-oracle tool wrappers.

The tests never hit the network: they inject a ``unittest.mock.MagicMock``
in place of a real :class:`maxia_oracle.MaxiaOracleClient` and assert the
dispatch routing + argument forwarding.
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from langchain_maxia_oracle import (
    DISCLAIMER,
    MAXIA_ORACLE_TOOL_CLASSES,
    MaxiaOracleGetCacheStatsTool,
    MaxiaOracleGetChainlinkOnchainTool,
    MaxiaOracleGetConfidenceTool,
    MaxiaOracleGetMetadataTool,
    MaxiaOracleGetPriceContextTool,
    MaxiaOracleGetPriceHistoryTool,
    MaxiaOracleGetPriceTool,
    MaxiaOracleGetPricesBatchTool,
    MaxiaOracleGetPythSolanaTool,
    MaxiaOracleGetRedstoneTool,
    MaxiaOracleGetSourcesStatusTool,
    MaxiaOracleGetTwapTool,
    MaxiaOracleHealthCheckTool,
    MaxiaOracleListSupportedSymbolsTool,
    get_all_tools,
)


def _fake_response(payload: dict[str, Any]) -> dict[str, Any]:
    return {"data": payload, "disclaimer": DISCLAIMER}


def test_all_tools_exported() -> None:
    assert len(MAXIA_ORACLE_TOOL_CLASSES) == 14
    expected = {
        MaxiaOracleGetPriceTool,
        MaxiaOracleGetPricesBatchTool,
        MaxiaOracleGetSourcesStatusTool,
        MaxiaOracleGetCacheStatsTool,
        MaxiaOracleGetConfidenceTool,
        MaxiaOracleListSupportedSymbolsTool,
        MaxiaOracleGetChainlinkOnchainTool,
        MaxiaOracleGetRedstoneTool,
        MaxiaOracleGetPythSolanaTool,
        MaxiaOracleGetTwapTool,
        MaxiaOracleGetPriceContextTool,
        MaxiaOracleGetMetadataTool,
        MaxiaOracleGetPriceHistoryTool,
        MaxiaOracleHealthCheckTool,
    }
    assert set(MAXIA_ORACLE_TOOL_CLASSES) == expected


def test_tool_names_unique_and_namespaced() -> None:
    names = [cls.model_fields["name"].default for cls in MAXIA_ORACLE_TOOL_CLASSES]
    assert len(names) == len(set(names)), "tool names must be unique"
    for name in names:
        assert name.startswith("maxia_oracle_"), (
            f"tool name {name!r} must be prefixed with 'maxia_oracle_' "
            "to avoid collisions with other LangChain tools"
        )


def test_tool_descriptions_contain_disclaimer() -> None:
    for cls in MAXIA_ORACLE_TOOL_CLASSES:
        description = cls.model_fields["description"].default
        assert DISCLAIMER in description, (
            f"{cls.__name__} description must contain the disclaimer "
            "(non-investment-advice notice)"
        )


def test_get_all_tools_shares_a_single_client() -> None:
    fake = MagicMock(name="MaxiaOracleClient")
    tools = get_all_tools(client=fake)
    assert len(tools) == 14
    for tool in tools:
        assert tool.client is fake, (
            "get_all_tools must inject the same client instance into every tool"
        )


def test_get_price_tool_dispatches_to_client() -> None:
    fake = MagicMock()
    fake.price.return_value = _fake_response({"symbol": "BTC", "price": 73999.12})
    tool = MaxiaOracleGetPriceTool(client=fake)

    result = tool.invoke({"symbol": "BTC"})

    fake.price.assert_called_once_with("BTC")
    parsed = json.loads(result)
    assert parsed["data"]["symbol"] == "BTC"
    assert parsed["disclaimer"] == DISCLAIMER


def test_get_prices_batch_tool_dispatches_to_client() -> None:
    fake = MagicMock()
    fake.prices_batch.return_value = _fake_response(
        {"prices": {"BTC": 74000, "ETH": 2500}}
    )
    tool = MaxiaOracleGetPricesBatchTool(client=fake)

    result = tool.invoke({"symbols": ["BTC", "ETH"]})

    fake.prices_batch.assert_called_once_with(["BTC", "ETH"])
    parsed = json.loads(result)
    assert "BTC" in parsed["data"]["prices"]


def test_get_sources_status_tool_has_no_args() -> None:
    fake = MagicMock()
    fake.sources.return_value = _fake_response({"sources": []})
    tool = MaxiaOracleGetSourcesStatusTool(client=fake)

    result = tool.invoke({})

    fake.sources.assert_called_once_with()
    assert DISCLAIMER in result


def test_chainlink_onchain_tool_dispatches_to_client() -> None:
    fake = MagicMock()
    fake.chainlink_onchain.return_value = _fake_response(
        {"symbol": "BTC", "price": 73980.0, "source": "chainlink_base"}
    )
    tool = MaxiaOracleGetChainlinkOnchainTool(client=fake)

    result = tool.invoke({"symbol": "BTC"})

    fake.chainlink_onchain.assert_called_once_with("BTC", chain="base")
    parsed = json.loads(result)
    assert parsed["data"]["source"] == "chainlink_base"


def test_chainlink_onchain_tool_propagates_chain_ethereum() -> None:
    fake = MagicMock()
    fake.chainlink_onchain.return_value = _fake_response(
        {"symbol": "BTC", "price": 73900.0, "source": "chainlink_ethereum", "chain": "ethereum"}
    )
    tool = MaxiaOracleGetChainlinkOnchainTool(client=fake)

    result = tool.invoke({"symbol": "BTC", "chain": "ethereum"})

    fake.chainlink_onchain.assert_called_once_with("BTC", chain="ethereum")
    parsed = json.loads(result)
    assert parsed["data"]["chain"] == "ethereum"


def test_health_check_tool_has_no_args() -> None:
    fake = MagicMock()
    fake.health.return_value = _fake_response({"status": "ok", "uptime_s": 12.3})
    tool = MaxiaOracleHealthCheckTool(client=fake)

    result = tool.invoke({})

    fake.health.assert_called_once_with()
    parsed = json.loads(result)
    assert parsed["data"]["status"] == "ok"


def test_confidence_tool_dispatches_to_client() -> None:
    fake = MagicMock()
    fake.confidence.return_value = _fake_response(
        {"symbol": "ETH", "source_count": 3, "divergence_pct": 0.21}
    )
    tool = MaxiaOracleGetConfidenceTool(client=fake)

    result = tool.invoke({"symbol": "ETH"})

    fake.confidence.assert_called_once_with("ETH")
    parsed = json.loads(result)
    assert parsed["data"]["divergence_pct"] == 0.21


def test_batch_input_rejects_empty_list() -> None:
    fake = MagicMock()
    tool = MaxiaOracleGetPricesBatchTool(client=fake)

    with pytest.raises(Exception):
        tool.invoke({"symbols": []})

    fake.prices_batch.assert_not_called()


def test_batch_input_rejects_oversized_list() -> None:
    fake = MagicMock()
    tool = MaxiaOracleGetPricesBatchTool(client=fake)

    with pytest.raises(Exception):
        tool.invoke({"symbols": [f"SYM{i}" for i in range(51)]})

    fake.prices_batch.assert_not_called()
