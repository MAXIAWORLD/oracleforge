"""OutreachForge — AI-powered Lead Scoring.

Scores prospects based on profile completeness, domain quality, and engagement signals.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreResult:
    score: float  # 0.0 - 1.0
    tier: str  # cold | warm | hot
    factors: dict[str, float]


# Free email domains (lower score for B2B outreach)
_FREE_DOMAINS = frozenset({
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "mail.com", "protonmail.com", "zoho.com",
})

# High-value title keywords
_TITLE_KEYWORDS = {
    "cto": 0.15, "ceo": 0.15, "vp": 0.12, "director": 0.10,
    "head": 0.10, "lead": 0.08, "manager": 0.06, "engineer": 0.05,
    "founder": 0.15, "co-founder": 0.15, "chief": 0.12,
}


class LeadScorer:
    """Score prospects for outreach prioritisation."""

    def score(
        self,
        email: str,
        name: str = "",
        company: str = "",
        title: str = "",
    ) -> ScoreResult:
        factors: dict[str, float] = {}
        total = 0.0

        # Email domain (business vs free)
        domain = email.split("@")[-1].lower() if "@" in email else ""
        if domain and domain not in _FREE_DOMAINS:
            factors["business_email"] = 0.20
            total += 0.20
        elif domain:
            factors["free_email"] = 0.05
            total += 0.05

        # Name completeness
        if name and " " in name:
            factors["full_name"] = 0.15
            total += 0.15
        elif name:
            factors["partial_name"] = 0.05
            total += 0.05

        # Company
        if company:
            factors["company"] = 0.20
            total += 0.20

        # Title scoring
        if title:
            title_lower = title.lower()
            best_match = 0.0
            for keyword, score in _TITLE_KEYWORDS.items():
                if keyword in title_lower:
                    best_match = max(best_match, score)
            if best_match > 0:
                factors["title_quality"] = best_match
                total += best_match
            else:
                factors["title_present"] = 0.03
                total += 0.03

        # Email format validation
        if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            factors["valid_email"] = 0.10
            total += 0.10

        score = min(1.0, total)

        # Tier assignment
        if score >= 0.6:
            tier = "hot"
        elif score >= 0.35:
            tier = "warm"
        else:
            tier = "cold"

        return ScoreResult(score=round(score, 3), tier=tier, factors=factors)
