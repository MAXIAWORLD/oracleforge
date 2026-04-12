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

PRESETS: dict[str, dict] = {
    "strict": {
        "name": "strict",
        "description": "Block all PII — maximum safety",
        "pii_action": "block",
        "blocked_types": ["email", "phone_international", "credit_card", "ssn_us", "ssn_fr", "iban"],
        "max_pii_count": 0,
    },
    "moderate": {
        "name": "moderate",
        "description": "Anonymize PII before processing",
        "pii_action": "anonymize",
        "blocked_types": ["credit_card", "ssn_us", "ssn_fr"],
        "max_pii_count": 5,
    },
    "permissive": {
        "name": "permissive",
        "description": "Warn on PII but allow processing",
        "pii_action": "warn",
        "blocked_types": [],
        "max_pii_count": -1,  # unlimited
    },
    "gdpr": {
        "name": "gdpr",
        "description": "GDPR compliance — anonymize personal data",
        "pii_action": "anonymize",
        "blocked_types": ["ssn_fr", "iban"],
        "max_pii_count": 0,
    },
    "hipaa": {
        "name": "hipaa",
        "description": "HIPAA compliance — block all health-related PII",
        "pii_action": "block",
        "blocked_types": ["email", "phone_international", "ssn_us", "date_of_birth"],
        "max_pii_count": 0,
    },
    "pci_dss": {
        "name": "pci_dss",
        "description": "PCI-DSS compliance — block payment data",
        "pii_action": "block",
        "blocked_types": ["credit_card", "iban"],
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
        """List all available policies."""
        return [
            {"name": p["name"], "description": p.get("description", ""), "action": p.get("pii_action", "block")}
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
