"""Unit tests for the autogen-maxia-oracle wrappers. Offline."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from autogen_core import CancellationToken
from autogen_core.tools import FunctionTool

from autogen_maxia_oracle import DISCLAIMER, TOOL_NAMES, get_all_tools


def _fake(payload: dict[str, Any]) -> dict[str, Any]:
    return {"data": payload, "disclaimer": DISCLAIMER}


def test_all_tools_exported() -> None:
    fake = MagicMock()
    tools = get_all_tools(client=fake)
    assert len(tools) == 12
    for tool in tools:
        assert isinstance(tool, FunctionTool)


def test_tool_names_match_expected() -> None:
    fake = MagicMock()
    tools = get_all_tools(client=fake)
    actual = [tool.name for tool in tools]
    assert actual == list(TOOL_NAMES)
    assert len(set(actual)) == len(actual)
    for name in actual:
        assert name.startswith("maxia_oracle_")


def test_tool_descriptions_contain_disclaimer() -> None:
    fake = MagicMock()
    tools = get_all_tools(client=fake)
    for tool in tools:
        assert DISCLAIMER in tool.description, (
            f"tool {tool.name} description must contain the disclaimer"
        )


@pytest.mark.asyncio
async def test_get_price_tool_dispatches_to_client() -> None:
    fake = MagicMock()
    fake.price.return_value = _fake({"symbol": "BTC", "price": 73999.12})
    tools = {t.name: t for t in get_all_tools(client=fake)}

    result = await tools["maxia_oracle_get_price"].run_json(
        {"symbol": "BTC"}, CancellationToken()
    )

    fake.price.assert_called_once_with("BTC")
    parsed = json.loads(result)
    assert parsed["data"]["symbol"] == "BTC"


@pytest.mark.asyncio
async def test_get_prices_batch_tool_dispatches_to_client() -> None:
    fake = MagicMock()
    fake.prices_batch.return_value = _fake({"prices": {"BTC": 74000}})
    tools = {t.name: t for t in get_all_tools(client=fake)}

    result = await tools["maxia_oracle_get_prices_batch"].run_json(
        {"symbols": ["BTC", "ETH"]}, CancellationToken()
    )

    fake.prices_batch.assert_called_once_with(["BTC", "ETH"])
    assert "74000" in result


@pytest.mark.asyncio
async def test_sources_status_tool_no_args() -> None:
    fake = MagicMock()
    fake.sources.return_value = _fake({"sources": []})
    tools = {t.name: t for t in get_all_tools(client=fake)}

    result = await tools["maxia_oracle_get_sources_status"].run_json(
        {}, CancellationToken()
    )

    fake.sources.assert_called_once_with()
    assert DISCLAIMER in result


@pytest.mark.asyncio
async def test_chainlink_onchain_tool_dispatches_to_client() -> None:
    fake = MagicMock()
    fake.chainlink_onchain.return_value = _fake(
        {"symbol": "BTC", "source": "chainlink_base"}
    )
    tools = {t.name: t for t in get_all_tools(client=fake)}

    result = await tools["maxia_oracle_get_chainlink_onchain"].run_json(
        {"symbol": "BTC"}, CancellationToken()
    )

    fake.chainlink_onchain.assert_called_once_with("BTC", chain="base")
    assert "chainlink_base" in result


@pytest.mark.asyncio
async def test_chainlink_onchain_tool_propagates_chain_ethereum() -> None:
    fake = MagicMock()
    fake.chainlink_onchain.return_value = _fake(
        {"symbol": "BTC", "source": "chainlink_ethereum", "chain": "ethereum"}
    )
    tools = {t.name: t for t in get_all_tools(client=fake)}

    result = await tools["maxia_oracle_get_chainlink_onchain"].run_json(
        {"symbol": "BTC", "chain": "ethereum"}, CancellationToken()
    )

    fake.chainlink_onchain.assert_called_once_with("BTC", chain="ethereum")
    assert "chainlink_ethereum" in result


@pytest.mark.asyncio
async def test_confidence_tool_dispatches_to_client() -> None:
    fake = MagicMock()
    fake.confidence.return_value = _fake(
        {"symbol": "ETH", "divergence_pct": 0.21}
    )
    tools = {t.name: t for t in get_all_tools(client=fake)}

    result = await tools["maxia_oracle_get_confidence"].run_json(
        {"symbol": "ETH"}, CancellationToken()
    )

    fake.confidence.assert_called_once_with("ETH")
    assert "0.21" in result


@pytest.mark.asyncio
async def test_health_check_tool_no_args() -> None:
    fake = MagicMock()
    fake.health.return_value = _fake({"status": "ok"})
    tools = {t.name: t for t in get_all_tools(client=fake)}

    result = await tools["maxia_oracle_health_check"].run_json(
        {}, CancellationToken()
    )

    fake.health.assert_called_once_with()
    parsed = json.loads(result)
    assert parsed["data"]["status"] == "ok"
