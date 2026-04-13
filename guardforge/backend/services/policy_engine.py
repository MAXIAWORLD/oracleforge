"""GuardForge — YAML Policy Engine.

Extracted from MAXIA V12 core/policy_engine.py and simplified:
- Policies define what PII types to detect/block/anonymize
- Industry presets (GDPR, HIPAA, PCI-DSS)
- Evaluation returns allow/deny decision
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    action: str  # allow | block | anonymize | warn
    reason: str
    policy_name: str


# ── Industry presets ─────────────────────────────────────────────

# Built-in PII types used in policy presets
_ALL_PERSONAL = ["email", "phone_international", "person_name", "date_of_birth"]
_ALL_FINANCIAL = ["credit_card", "iban", "rib_fr"]
_ALL_GOV_IDS = [
    "ssn_us", "ssn_fr", "siret_fr", "siren_fr", "dni_es", "nie_es",
    "codice_fiscale_it", "steuer_id_de", "passport_generic",
]


PRESETS: dict[str, dict] = {
    # ── Generic operational presets ─────────────────────────────
    "strict": {
        "name": "strict",
        "pii_action": "block",
        "blocked_types": ["email", "phone_international", "credit_card", "ssn_us", "ssn_fr", "iban"],
        "max_pii_count": 0,
    },
    "moderate": {
        "name": "moderate",
        "pii_action": "anonymize",
        "blocked_types": ["credit_card", "ssn_us", "ssn_fr"],
        "max_pii_count": 5,
    },
    "permissive": {
        "name": "permissive",
        "pii_action": "warn",
        "blocked_types": [],
        "max_pii_count": -1,  # unlimited
    },

    # ── Tier 1 jurisdictions (full mappings) ────────────────────
    "gdpr": {
        "name": "gdpr",
        "jurisdiction": "EU",
        "regulation": "General Data Protection Regulation 2016/679",
        "pii_action": "anonymize",
        "blocked_types": _ALL_PERSONAL + _ALL_FINANCIAL + _ALL_GOV_IDS,
        "max_pii_count": 0,
    },
    "eu_ai_act": {
        "name": "eu_ai_act",
        "jurisdiction": "EU",
        "regulation": "EU Artificial Intelligence Act 2024/1689",
        "pii_action": "block",  # high-risk AI systems must minimize PII
        "blocked_types": _ALL_PERSONAL + _ALL_FINANCIAL + _ALL_GOV_IDS,
        "max_pii_count": 0,
    },
    "hipaa": {
        "name": "hipaa",
        "jurisdiction": "US",
        "regulation": "Health Insurance Portability and Accountability Act",
        "pii_action": "block",
        "blocked_types": ["email", "phone_international", "ssn_us", "date_of_birth", "person_name"],
        "max_pii_count": 0,
    },
    "ccpa": {
        "name": "ccpa",
        "jurisdiction": "US-CA",
        "regulation": "California Consumer Privacy Act / CPRA",
        "pii_action": "anonymize",
        "blocked_types": _ALL_PERSONAL + _ALL_FINANCIAL + ["ssn_us", "passport_generic"],
        "max_pii_count": 0,
    },
    "lgpd": {
        "name": "lgpd",
        "jurisdiction": "BR",
        "regulation": "Lei Geral de Proteção de Dados",
        "pii_action": "anonymize",
        "blocked_types": _ALL_PERSONAL + _ALL_FINANCIAL + _ALL_GOV_IDS,
        "max_pii_count": 0,
    },
    "pci_dss": {
        "name": "pci_dss",
        "jurisdiction": "Worldwide",
        "regulation": "Payment Card Industry Data Security Standard v4",
        "pii_action": "block",
        "blocked_types": ["credit_card", "iban", "rib_fr"],
        "max_pii_count": 0,
    },

    # ── Tier 2 jurisdictions (stubs — same baseline as GDPR) ───
    "pipeda": {
        "name": "pipeda",
        "jurisdiction": "CA",
        "regulation": "Personal Information Protection and Electronic Documents Act",
        "pii_action": "anonymize",
        "blocked_types": _ALL_PERSONAL + _ALL_FINANCIAL + _ALL_GOV_IDS,
        "max_pii_count": 0,
    },
    "appi": {
        "name": "appi",
        "jurisdiction": "JP",
        "regulation": "Act on the Protection of Personal Information",
        "pii_action": "anonymize",
        "blocked_types": _ALL_PERSONAL + _ALL_FINANCIAL + _ALL_GOV_IDS,
        "max_pii_count": 0,
    },
    "pdpa_sg": {
        "name": "pdpa_sg",
        "jurisdiction": "SG",
        "regulation": "Personal Data Protection Act (Singapore)",
        "pii_action": "anonymize",
        "blocked_types": _ALL_PERSONAL + _ALL_FINANCIAL + _ALL_GOV_IDS,
        "max_pii_count": 0,
    },
    "popia": {
        "name": "popia",
        "jurisdiction": "ZA",
        "regulation": "Protection of Personal Information Act",
        "pii_action": "anonymize",
        "blocked_types": _ALL_PERSONAL + _ALL_FINANCIAL + _ALL_GOV_IDS,
        "max_pii_count": 0,
    },
    "dpdp_in": {
        "name": "dpdp_in",
        "jurisdiction": "IN",
        "regulation": "Digital Personal Data Protection Act 2023",
        "pii_action": "anonymize",
        "blocked_types": _ALL_PERSONAL + _ALL_FINANCIAL + _ALL_GOV_IDS,
        "max_pii_count": 0,
    },
    "pipl_cn": {
        "name": "pipl_cn",
        "jurisdiction": "CN",
        "regulation": "Personal Information Protection Law",
        "pii_action": "block",  # PIPL is stricter than GDPR on cross-border transfers
        "blocked_types": _ALL_PERSONAL + _ALL_FINANCIAL + _ALL_GOV_IDS,
        "max_pii_count": 0,
    },
    "privacy_au": {
        "name": "privacy_au",
        "jurisdiction": "AU",
        "regulation": "Privacy Act 1988",
        "pii_action": "anonymize",
        "blocked_types": _ALL_PERSONAL + _ALL_FINANCIAL + _ALL_GOV_IDS,
        "max_pii_count": 0,
    },
}


class PolicyEngine:
    """Evaluate text against a policy to decide allow/block/anonymize."""

    def __init__(self, default_policy: str = "strict") -> None:
        self._policies: dict[str, dict] = dict(PRESETS)
        self._default = default_policy

    def load_policy_yaml(self, yaml_content: str) -> dict:
        """Parse and register a custom YAML policy."""
        if len(yaml_content) > 10240:
            raise ValueError("Policy YAML exceeds 10KB limit")
        policy = yaml.safe_load(yaml_content)
        if not isinstance(policy, dict) or "name" not in policy:
            raise ValueError("Policy must be a dict with 'name' field")
        self._policies[policy["name"]] = policy
        return policy

    def get_policy(self, name: str | None = None) -> dict:
        """Get a policy by name, or the default."""
        name = name or self._default
        return self._policies.get(name, self._policies.get("strict", {}))

    def list_policies(self) -> list[dict]:
        """List all available policies with metadata.

        Descriptions are intentionally empty here — they are translated
        client-side via the dashboard i18n files (messages/*.json) for
        multi-language support across 15 locales.
        """
        return [
            {
                "name": p["name"],
                "description": p.get("description", ""),
                "action": p.get("pii_action", "block"),
                "jurisdiction": p.get("jurisdiction", ""),
                "regulation": p.get("regulation", ""),
            }
            for p in self._policies.values()
        ]

    def evaluate(
        self,
        pii_types_found: list[str],
        pii_count: int,
        policy_name: str | None = None,
    ) -> PolicyDecision:
        """Evaluate PII scan results against a policy."""
        policy = self.get_policy(policy_name)
        name = policy.get("name", "unknown")
        action = policy.get("pii_action", "block")
        blocked_types = set(policy.get("blocked_types", []))
        max_count = policy.get("max_pii_count", 0)

        # Check for blocked PII types
        found_blocked = [t for t in pii_types_found if t in blocked_types]
        if found_blocked:
            if action == "block":
                return PolicyDecision(
                    allowed=False, action="block",
                    reason=f"Blocked PII types found: {', '.join(found_blocked)}",
                    policy_name=name,
                )
            if action == "anonymize":
                return PolicyDecision(
                    allowed=True, action="anonymize",
                    reason=f"PII will be anonymized: {', '.join(found_blocked)}",
                    policy_name=name,
                )

        # Check max PII count
        if max_count >= 0 and pii_count > max_count:
            return PolicyDecision(
                allowed=action != "block", action=action,
                reason=f"PII count {pii_count} exceeds limit {max_count}",
                policy_name=name,
            )

        # No issues
        return PolicyDecision(allowed=True, action="allow", reason="No policy violations", policy_name=name)

    def stats(self) -> dict:
        return {"policies_loaded": len(self._policies), "default": self._default}
