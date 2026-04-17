"""MAXIA Oracle — Agent Intelligence Layer (V1.6).

Computes a unified confidence score (0-100), anomaly flag, and
sources-agreement label from the raw multi-source price data.
These are "agent-native" features: one number tells an LLM whether
it can trust the price and act on it.

All functions are pure (no I/O, no side-effects). The orchestrator
`build_price_context` fans out to `collect_sources` and the TWAP layer,
then assembles the final payload in a single call.
"""
from __future__ import annotations

from typing import Any

from services.oracle import pyth_oracle
from services.oracle.multi_source import collect_sources, compute_divergence


# ── Confidence Score weights (total = 100) ───────────────────────────────────

_W_SOURCES = 40
_W_DIVERGENCE = 30
_W_FRESHNESS = 20
_W_CONFIDENCE = 10


def compute_confidence_score(
    sources: list[dict[str, Any]],
    divergence_pct: float,
) -> int:
    """Return a 0-100 integer confidence score.

    Inputs come from ``collect_sources`` and ``compute_divergence``.
    The formula is deliberately simple and fully documented so agents
    (and their operators) can reason about what the number means.
    """
    score = 0.0

    # A — Source count (more independent sources = more trust)
    n = len(sources)
    if n == 0:
        return 0
    if n == 1:
        score += 15
    elif n == 2:
        score += 25
    elif n == 3:
        score += 32
    else:
        score += _W_SOURCES  # 4+

    # B — Inter-source divergence (lower = better)
    if divergence_pct <= 0.0:
        score += _W_DIVERGENCE
    elif divergence_pct < 0.5:
        score += 25
    elif divergence_pct < 1.0:
        score += 20
    elif divergence_pct < 2.0:
        score += 10
    # else: 0

    # C — Freshness (age of the *freshest* source in seconds)
    ages = [s.get("age_s") for s in sources if s.get("age_s") is not None]
    if ages:
        best_age = min(ages)
        if best_age < 5:
            score += _W_FRESHNESS
        elif best_age < 30:
            score += 15
        elif best_age < 120:
            score += 10
        elif best_age < 600:
            score += 5
    # No age info → 0 freshness points (conservative)

    # D — Pyth confidence spread (tightest source confidence_pct)
    confs = [
        s["confidence_pct"]
        for s in sources
        if s.get("confidence_pct") is not None
    ]
    if confs:
        best_conf = min(confs)
        if best_conf < 1.0:
            score += _W_CONFIDENCE
        elif best_conf < 2.0:
            score += 8
        elif best_conf < 5.0:
            score += 5
    # No confidence data → 0 points

    return min(100, max(0, int(round(score))))


# ── Anomaly detection ────────────────────────────────────────────────────────

_TWAP_ANOMALY_THRESHOLD_PCT = 5.0
_SOURCE_OUTLIER_THRESHOLD_PCT = 10.0


def detect_anomaly(
    symbol: str,
    median_price: float,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return anomaly flag and supporting evidence.

    Two independent triggers:
      1. Spot (median) deviates >5% from the 5-min TWAP.
      2. Any individual source deviates >10% from the median.
    """
    reasons: list[str] = []

    # --- TWAP deviation ---
    twap_info = pyth_oracle.check_twap_deviation(symbol, median_price)
    twap_val = twap_info.get("twap", 0.0)
    twap_dev = twap_info.get("deviation_pct", 0.0)
    twap_reason = twap_info.get("reason")

    if twap_reason != "insufficient_data" and twap_dev > _TWAP_ANOMALY_THRESHOLD_PCT:
        reasons.append(
            f"spot deviates {twap_dev:.2f}% from 5-min TWAP "
            f"(threshold {_TWAP_ANOMALY_THRESHOLD_PCT}%)"
        )

    # --- Source outlier ---
    outliers: list[dict[str, Any]] = []
    if median_price > 0:
        for s in sources:
            p = s.get("price", 0)
            if p <= 0:
                continue
            dev = abs(p - median_price) / median_price * 100
            if dev > _SOURCE_OUTLIER_THRESHOLD_PCT:
                outliers.append({"source": s.get("name", "?"), "deviation_pct": round(dev, 2)})
                reasons.append(
                    f"{s.get('name', '?')} deviates {dev:.2f}% from median "
                    f"(threshold {_SOURCE_OUTLIER_THRESHOLD_PCT}%)"
                )

    return {
        "anomaly": len(reasons) > 0,
        "reasons": reasons,
        "twap_5min": twap_val,
        "twap_deviation_pct": twap_dev,
        "source_outliers": outliers,
    }


# ── Sources agreement label ──────────────────────────────────────────────────

def classify_agreement(divergence_pct: float, source_count: int) -> str:
    """Human-readable label for how well sources agree."""
    if source_count < 2:
        return "single_source"
    if divergence_pct <= 0.1:
        return "strong"
    if divergence_pct <= 0.5:
        return "good"
    if divergence_pct <= 2.0:
        return "moderate"
    return "weak"


# ── Orchestrator ─────────────────────────────────────────────────────────────

async def build_price_context(symbol: str) -> dict[str, Any] | None:
    """One-call endpoint payload: price + confidence + anomaly + agreement.

    Returns None when no source can provide a price (caller returns 404).
    """
    sources = await collect_sources(symbol)
    if not sources:
        return None

    prices = [s["price"] for s in sources]
    median_price = sorted(prices)[len(prices) // 2]
    divergence_pct = compute_divergence(prices)

    confidence_score = compute_confidence_score(sources, divergence_pct)
    anomaly_info = detect_anomaly(symbol, median_price, sources)
    agreement = classify_agreement(divergence_pct, len(sources))

    ages = [s.get("age_s") for s in sources if s.get("age_s") is not None]
    freshest_age_s = min(ages) if ages else None

    return {
        "symbol": symbol,
        "price": round(median_price, 6),
        "confidence_score": confidence_score,
        "anomaly": anomaly_info["anomaly"],
        "anomaly_reasons": anomaly_info["reasons"],
        "sources_agreement": agreement,
        "source_count": len(sources),
        "divergence_pct": divergence_pct,
        "freshest_age_s": freshest_age_s,
        "twap_5min": anomaly_info["twap_5min"],
        "twap_deviation_pct": anomaly_info["twap_deviation_pct"],
        "source_outliers": anomaly_info["source_outliers"],
        "sources": sources,
    }
