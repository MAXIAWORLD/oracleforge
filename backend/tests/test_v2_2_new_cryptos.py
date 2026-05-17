"""V2.2 — 16 new crypto tokens coverage tests.

Tests are RED until pyth_oracle.CRYPTO_FEEDS is populated with
the verified Pyth Hermes feed IDs for each token.

Feed IDs verified live against hermes.pyth.network on 2026-05-05.
"""

from __future__ import annotations

import pytest

# ── Expected feed IDs (verified live 2026-05-05) ────────────────────────────

EXPECTED_FEEDS = {
    # Tier 1 — top 15 market cap
    "BNB": "2f95862b045670cd22bee3114c39763a4a08beeb663b145d283c31d7d1101c4f",
    "ADA": "2a01deaec9e51a579277b34b122399984d0bbf57e2458a7e42fecd2829867a0d",
    "DOGE": "dcef50dd0a4cd2dcc17e45df1676dcb336a11a61c69df7a0299b0150c672d25c",
    "DOT": "ca3eed9b267293f6595901c734c7525ce8ef49adafe8284606ceb307afa2ca5b",
    "LTC": "6e3f3fa8253588df9326580180233eb791e03b443a3ba7a1d892e73874e19a54",
    "TRX": "67aed5a24fdad045475e7195c98a98aea119c763f272d4523f5bac93a4f33c2b",
    # Tier 2 — agent-native ecosystems
    "NEAR": "c415de8d2eba7db216527dff4b60e8f3a5311c740dadb233e13e12547e226750",
    "SUI": "23d7315113f5b1d3ba7a83604c44b94d79f4fd69af77f804fc7f920a6dc65744",
    "APT": "03ae4db29ed4ae33d323568895aa00337e658e348b37509f5372ae51f0af00d5",
    "INJ": "7a5bc1d2b56ad029048cd63964b3ad2776eadf812edc1a43a31406cb54bff592",
    "SEI": "53614f1cb0c031d4af66c04cb9c756234adad0e1cee85303795091499a4084eb",
    # Tier 3 — AI tokens
    "RENDER": "3d4a2bd9535be6ce8059d75eadeba507b043257321aa544717c56fa19b49e35d",
    "FET": "7da003ada32eabbac855af3d22fcf0fe692cc589f0cfd5ced63cf0bdcc742efe",
    "TAO": "410f41de235f2db824e562ea7ab2d3d3d4ff048316c61d629c0b93f58584e1af",
    # Tier 4 — stablecoins / LST
    "DAI": "b0948a5e5313200c632b51bb5ca32f6de0d36e9950a942d19751e833f70dabfd",
    "WSTETH": "6df640f3b8963d8f8358f791f352b8364513f6ab1cca5ed3f1f7b5448980e784",
}


# ── Presence tests ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("symbol,feed_id", EXPECTED_FEEDS.items())
def test_crypto_feed_present(symbol: str, feed_id: str):
    """Each new token must appear in CRYPTO_FEEDS with the verified feed ID."""
    from services.oracle.pyth_oracle import CRYPTO_FEEDS

    assert symbol in CRYPTO_FEEDS, f"{symbol} missing from CRYPTO_FEEDS"
    assert CRYPTO_FEEDS[symbol] == feed_id, (
        f"{symbol} feed ID mismatch: expected {feed_id}, got {CRYPTO_FEEDS[symbol]}"
    )


# ── Confidence tier tests ────────────────────────────────────────────────────


@pytest.mark.parametrize("symbol", ["BNB", "DAI"])
def test_major_tokens_have_tight_threshold(symbol: str):
    """BNB and DAI must use the 'major' confidence tier (threshold = 2.0%)."""
    from services.oracle.pyth_oracle import (
        _MAJOR_TOKENS,
        _CONFIDENCE_TIERS,
        get_confidence_threshold,
    )

    assert symbol in _MAJOR_TOKENS, f"{symbol} must be in _MAJOR_TOKENS"
    assert get_confidence_threshold(symbol) == _CONFIDENCE_TIERS["major"]


@pytest.mark.parametrize("symbol", ["ADA", "DOT", "LTC", "TRX", "TAO", "WSTETH"])
def test_mid_tokens_have_mid_threshold(symbol: str):
    """New mid-cap tokens must use the 'mid' confidence tier (threshold = 5.0%)."""
    from services.oracle.pyth_oracle import (
        _MID_TOKENS,
        _CONFIDENCE_TIERS,
        get_confidence_threshold,
    )

    assert symbol in _MID_TOKENS, f"{symbol} must be in _MID_TOKENS"
    assert get_confidence_threshold(symbol) == _CONFIDENCE_TIERS["mid"]


# ── Feed ID format validation ────────────────────────────────────────────────


@pytest.mark.parametrize("symbol,feed_id", EXPECTED_FEEDS.items())
def test_feed_id_is_valid_hex(symbol: str, feed_id: str):
    """Every feed ID must be a valid 64-char lowercase hex string."""
    from services.oracle.pyth_oracle import _is_valid_feed_id

    assert _is_valid_feed_id(feed_id), (
        f"{symbol} feed ID '{feed_id}' is not a valid 64-char hex string"
    )


# ── ALL_FEEDS index test ─────────────────────────────────────────────────────


@pytest.mark.parametrize("symbol", EXPECTED_FEEDS)
def test_all_feeds_index_includes_new_tokens(symbol: str):
    """ALL_FEEDS must include every new token (used for symbol reverse-lookup)."""
    from services.oracle.pyth_oracle import ALL_FEEDS

    assert symbol in ALL_FEEDS, f"{symbol} missing from ALL_FEEDS"
