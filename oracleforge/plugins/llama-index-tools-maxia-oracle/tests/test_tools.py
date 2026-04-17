"""Unit tests for the llama-index-tools-maxia-oracle wrappers. Offline."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

from llama_index.core.tools import FunctionTool

from llama_index_tools_maxia_oracle import DISCLAIMER, TOOL_NAMES, get_all_tools


def _fake(payload: dict[str, Any]) -> dict[str, Any]:
    return {"data": payload, "disclaimer": DISCLAIMER}


def test_all_tools_exported() -> None:
    fake = MagicMock()
    tools = get_all_tools(client=fake)
    assert len(tools) == 14
    for tool in tools:
        assert isinstance(tool, FunctionTool)


def test_tool_names_match_expected() -> None:
    fake = MagicMock()
    tools = get_all_tools(client=fake)
    actual = [tool.metadata.name for tool in tools]
    assert actual == list(TOOL_NAMES)
    assert len(set(actual)) == len(actual)
    for name in actual:
        assert name.startswith("maxia_oracle_")


def test_tool_descriptions_contain_disclaimer() -> None:
    fake = MagicMock()
    tools = get_all_tools(client=fake)
    for tool in tools:
        assert DISCLAIMER in tool.metadata.description, (
            f"tool {tool.metadata.name} description must contain the disclaimer"
        )


def test_get_price_tool_dispatches_to_client() -> None:
    fake = MagicMock()
    fake.price.return_value = _fake({"symbol": "BTC", "price": 73999.12})
    tools = {t.metadata.name: t for t in get_all_tools(client=fake)}

    output = tools["maxia_oracle_get_price"].call(symbol="BTC")

    fake.price.assert_called_once_with("BTC")
    parsed = json.loads(output.content)
    assert parsed["data"]["symbol"] == "BTC"


def test_get_prices_batch_tool_dispatches_to_client() -> None:
    fake = MagicMock()
    fake.prices_batch.return_value = _fake({"prices": {"BTC": 74000}})
    tools = {t.metadata.name: t for t in get_all_tools(client=fake)}

    output = tools["maxia_oracle_get_prices_batch"].call(symbols=["BTC", "ETH"])

    fake.prices_batch.assert_called_once_with(["BTC", "ETH"])
    assert "74000" in output.content


def test_sources_status_tool_no_args() -> None:
    fake = MagicMock()
    fake.sources.return_value = _fake({"sources": []})
    tools = {t.metadata.name: t for t in get_all_tools(client=fake)}

    output = tools["maxia_oracle_get_sources_status"].call()

    fake.sources.assert_called_once_with()
    assert DISCLAIMER in output.content


def test_chainlink_onchain_tool_dispatches_to_client() -> None:
    fake = MagicMock()
    fake.chainlink_onchain.return_value = _fake(
        {"symbol": "BTC", "source": "chainlink_base"}
    )
    tools = {t.metadata.name: t for t in get_all_tools(client=fake)}

    output = tools["maxia_oracle_get_chainlink_onchain"].call(symbol="BTC")

    fake.chainlink_onchain.assert_called_once_with("BTC", chain="base")
    assert "chainlink_base" in output.content


def test_chainlink_onchain_tool_propagates_chain_arbitrum() -> None:
    fake = MagicMock()
    fake.chainlink_onchain.return_value = _fake(
        {"symbol": "BTC", "source": "chainlink_arbitrum", "chain": "arbitrum"}
    )
    tools = {t.metadata.name: t for t in get_all_tools(client=fake)}

    output = tools["maxia_oracle_get_chainlink_onchain"].call(
        symbol="BTC", chain="arbitrum"
    )

    fake.chainlink_onchain.assert_called_once_with("BTC", chain="arbitrum")
    assert "chainlink_arbitrum" in output.content


def test_confidence_tool_dispatches_to_client() -> None:
    fake = MagicMock()
    fake.confidence.return_value = _fake(
        {"symbol": "ETH", "divergence_pct": 0.21}
    )
    tools = {t.metadata.name: t for t in get_all_tools(client=fake)}

    output = tools["maxia_oracle_get_confidence"].call(symbol="ETH")

    fake.confidence.assert_called_once_with("ETH")
    assert "0.21" in output.content


def test_health_check_tool_no_args() -> None:
    fake = MagicMock()
    fake.health.return_value = _fake({"status": "ok"})
    tools = {t.metadata.name: t for t in get_all_tools(client=fake)}

    output = tools["maxia_oracle_health_check"].call()

    fake.health.assert_called_once_with()
    parsed = json.loads(output.content)
    assert parsed["data"]["status"] == "ok"
