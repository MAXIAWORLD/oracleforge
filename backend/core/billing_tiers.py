"""MAXIA Oracle — tier → daily quota mapping (Stripe billing).

Single source of truth for the per-tier daily request limit. Both the
rate limiter (core.rate_limit.check_daily / check_batch) and the Stripe
webhook handler (services.billing.stripe_service.apply_subscription_event)
read from this module. Adding a new paid tier is therefore a one-line change.

Tiers
    free     — 100 req/day        (default at registration)
    dev      — 10_000 req/day     (Stripe $9/month)
    pro      — 100_000 req/day    (Stripe $49/month)

A tier value the DB does not recognise (e.g. left over from a legacy row)
falls back to "free" — never higher — so a corrupted row cannot
silently grant a paid quota.
"""

from __future__ import annotations

from typing import Final

FREE_TIER: Final[str] = "free"
DEV_TIER: Final[str] = "dev"
PRO_TIER: Final[str] = "pro"

TIER_DAILY_LIMITS: Final[dict[str, int]] = {
    FREE_TIER: 100,
    DEV_TIER: 10_000,
    PRO_TIER: 100_000,
}

VALID_TIERS: Final[frozenset[str]] = frozenset(TIER_DAILY_LIMITS.keys())


def quota_for_tier(tier: str | None) -> int:
    """Return the daily request quota for `tier`. Unknown tiers default to free."""
    if tier and tier in TIER_DAILY_LIMITS:
        return TIER_DAILY_LIMITS[tier]
    return TIER_DAILY_LIMITS[FREE_TIER]


def is_paid_tier(tier: str | None) -> bool:
    """Return True if `tier` is a paid tier (dev or pro)."""
    return tier in {DEV_TIER, PRO_TIER}
