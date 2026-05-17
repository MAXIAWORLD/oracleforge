"""V2.0 — Coverage tests: Chainlink Ethereum fallback for SOL/XRP.

Tests are RED until multi_source.collect_sources() is updated to add
chainlink_ethereum for symbols absent from Chainlink Base.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch


# ── Registry assertions (no mocks needed) ───────────────────────────────────


def test_sol_absent_from_chainlink_base():
    from services.oracle.chainlink_oracle import has_feed

    assert not has_feed("SOL", "base"), (
        "SOL must NOT be on Chainlink Base (no feed deployed)"
    )


def test_sol_present_on_chainlink_ethereum():
    from services.oracle.chainlink_oracle import has_feed

    assert has_feed("SOL", "ethereum"), (
        "SOL must be on Chainlink Ethereum (0x4ffC43a6...)"
    )


def test_xrp_absent_from_chainlink_base():
    from services.oracle.chainlink_oracle import has_feed

    assert not has_feed("XRP", "base"), (
        "XRP must NOT be on Chainlink Base (no feed deployed)"
    )


def test_xrp_present_on_chainlink_ethereum():
    from services.oracle.chainlink_oracle import has_feed

    assert has_feed("XRP", "ethereum"), (
        "XRP must be on Chainlink Ethereum (0xCed2660c...)"
    )


def test_eth_present_on_chainlink_base():
    from services.oracle.chainlink_oracle import has_feed

    assert has_feed("ETH", "base"), "ETH must be on Chainlink Base (primary EVM source)"


# ── collect_sources() logic tests ────────────────────────────────────────────


_PYTH_PRICE_OK = {
    "price": 150.0,
    "age_s": 2,
    "stale": False,
    "confidence_pct": 0.1,
    "source": "pyth",
}

_CHAINLINK_ETH_OK = {
    "price": 150.1,
    "age_s": 10,
    "stale": False,
    "source": "chainlink_ethereum",
    "chain": "ethereum",
}

_CHAINLINK_BASE_OK = {
    "price": 3500.0,
    "age_s": 5,
    "stale": False,
    "source": "chainlink_base",
    "chain": "base",
}


@pytest.mark.asyncio
async def test_collect_sources_sol_includes_chainlink_ethereum():
    """collect_sources('SOL') must include chainlink_ethereum as on-chain source."""
    from services.oracle.multi_source import collect_sources

    with (
        patch(
            "services.oracle.pyth_oracle.get_pyth_price",
            new=AsyncMock(return_value=_PYTH_PRICE_OK),
        ),
        patch(
            "services.oracle.chainlink_oracle.get_chainlink_price",
            new=AsyncMock(return_value=_CHAINLINK_ETH_OK),
        ),
        patch(
            "services.oracle.price_oracle.get_prices",
            new=AsyncMock(
                return_value={"SOL": {"price": 150.2, "source": "coingecko"}}
            ),
        ),
        patch(
            "services.oracle.redstone_oracle.get_redstone_price",
            new=AsyncMock(return_value={"error": "not found"}),
        ),
        patch(
            "services.oracle.pyth_solana_oracle.get_pyth_solana_price",
            new=AsyncMock(
                return_value={
                    "price": 150.05,
                    "age_s": 1,
                    "stale": False,
                    "source": "pyth_solana",
                }
            ),
        ),
    ):
        sources = await collect_sources("SOL")
        names = [s["name"] for s in sources]
        assert "chainlink_ethereum" in names, (
            f"SOL must get Chainlink Ethereum source, got: {names}"
        )


@pytest.mark.asyncio
async def test_collect_sources_xrp_includes_chainlink_ethereum():
    """collect_sources('XRP') must include chainlink_ethereum as on-chain source."""
    from services.oracle.multi_source import collect_sources

    with (
        patch(
            "services.oracle.pyth_oracle.get_pyth_price",
            new=AsyncMock(return_value={**_PYTH_PRICE_OK, "price": 0.51}),
        ),
        patch(
            "services.oracle.chainlink_oracle.get_chainlink_price",
            new=AsyncMock(return_value={**_CHAINLINK_ETH_OK, "price": 0.51}),
        ),
        patch(
            "services.oracle.price_oracle.get_prices",
            new=AsyncMock(return_value={"XRP": {"price": 0.52, "source": "coingecko"}}),
        ),
        patch(
            "services.oracle.redstone_oracle.get_redstone_price",
            new=AsyncMock(
                return_value={
                    "price": 0.51,
                    "age_s": 5,
                    "stale": False,
                    "source": "redstone",
                }
            ),
        ),
        patch(
            "services.oracle.pyth_solana_oracle.has_feed",
            return_value=False,
        ),
    ):
        sources = await collect_sources("XRP")
        names = [s["name"] for s in sources]
        assert "chainlink_ethereum" in names, (
            f"XRP must get Chainlink Ethereum source, got: {names}"
        )


@pytest.mark.asyncio
async def test_collect_sources_eth_does_not_add_chainlink_ethereum():
    """ETH has a Base feed — chainlink_ethereum must NOT appear (no double-counting)."""
    from services.oracle.multi_source import collect_sources

    calls: list[str] = []

    async def mock_chainlink(symbol: str, chain: str = "base") -> dict:
        calls.append(chain)
        return {**_CHAINLINK_BASE_OK, "chain": chain, "source": f"chainlink_{chain}"}

    with (
        patch(
            "services.oracle.pyth_oracle.get_pyth_price",
            new=AsyncMock(return_value={**_PYTH_PRICE_OK, "price": 3500.0}),
        ),
        patch(
            "services.oracle.chainlink_oracle.get_chainlink_price",
            side_effect=mock_chainlink,
        ),
        patch(
            "services.oracle.price_oracle.get_prices",
            new=AsyncMock(
                return_value={"ETH": {"price": 3501.0, "source": "coingecko"}}
            ),
        ),
        patch(
            "services.oracle.redstone_oracle.get_redstone_price",
            new=AsyncMock(return_value={"error": "not found"}),
        ),
        patch(
            "services.oracle.pyth_solana_oracle.get_pyth_solana_price",
            new=AsyncMock(
                return_value={
                    "price": 3500.5,
                    "age_s": 1,
                    "stale": False,
                    "source": "pyth_solana",
                }
            ),
        ),
        patch(
            "services.oracle.uniswap_v3_oracle.get_twap_price",
            new=AsyncMock(
                return_value={
                    "price": 3500.2,
                    "age_s": 0,
                    "stale": False,
                    "source": "uniswap_v3",
                }
            ),
        ),
    ):
        sources = await collect_sources("ETH")
        names = [s["name"] for s in sources]
        assert "chainlink_ethereum" not in names, (
            f"ETH must NOT get chainlink_ethereum (Base already covers it), got: {names}"
        )
        assert "chainlink_base" in names, f"ETH must get chainlink_base, got: {names}"
        assert calls == ["base"], (
            f"Chainlink must only be called for base, got: {calls}"
        )


@pytest.mark.asyncio
async def test_chainlink_ethereum_error_does_not_crash_collect_sources():
    """If Chainlink Ethereum fails, collect_sources() must still return other sources."""
    from services.oracle.multi_source import collect_sources

    with (
        patch(
            "services.oracle.pyth_oracle.get_pyth_price",
            new=AsyncMock(return_value={**_PYTH_PRICE_OK, "price": 0.51}),
        ),
        patch(
            "services.oracle.chainlink_oracle.get_chainlink_price",
            new=AsyncMock(
                return_value={"error": "RPC timeout", "source": "chainlink_ethereum"}
            ),
        ),
        patch(
            "services.oracle.price_oracle.get_prices",
            new=AsyncMock(return_value={"XRP": {"price": 0.52, "source": "coingecko"}}),
        ),
        patch(
            "services.oracle.redstone_oracle.get_redstone_price",
            new=AsyncMock(
                return_value={
                    "price": 0.51,
                    "age_s": 5,
                    "stale": False,
                    "source": "redstone",
                }
            ),
        ),
        patch(
            "services.oracle.pyth_solana_oracle.has_feed",
            return_value=False,
        ),
    ):
        sources = await collect_sources("XRP")
        assert len(sources) >= 1, (
            "Must return at least 1 source even if Chainlink fails"
        )
        names = [s["name"] for s in sources]
        assert "chainlink_ethereum" not in names, (
            "Failed chainlink_ethereum must be dropped"
        )
