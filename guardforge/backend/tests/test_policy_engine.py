"""TDD tests for services/policy_engine.py."""

from services.policy_engine import PolicyEngine


class TestPresets:
    def test_strict_blocks_email(self) -> None:
        pe = PolicyEngine(default_policy="strict")
        decision = pe.evaluate(["email"], 1)
        assert decision.allowed is False
        assert decision.action == "block"

    def test_moderate_anonymizes(self) -> None:
        pe = PolicyEngine(default_policy="moderate")
        decision = pe.evaluate(["credit_card"], 1)
        assert decision.allowed is True
        assert decision.action == "anonymize"

    def test_permissive_allows(self) -> None:
        pe = PolicyEngine(default_policy="permissive")
        decision = pe.evaluate(["email", "phone_international"], 2)
        assert decision.allowed is True

    def test_gdpr_anonymizes(self) -> None:
        pe = PolicyEngine()
        decision = pe.evaluate(["ssn_fr"], 1, policy_name="gdpr")
        assert decision.action in ("block", "anonymize")

    def test_no_pii_always_allowed(self) -> None:
        pe = PolicyEngine(default_policy="strict")
        decision = pe.evaluate([], 0)
        assert decision.allowed is True


class TestCustomPolicy:
    def test_load_yaml(self) -> None:
        pe = PolicyEngine()
        yaml_str = """
name: custom
description: Custom policy
pii_action: warn
blocked_types: []
max_pii_count: -1
"""
        policy = pe.load_policy_yaml(yaml_str)
        assert policy["name"] == "custom"
        assert "custom" in [p["name"] for p in pe.list_policies()]

    def test_yaml_size_limit(self) -> None:
        pe = PolicyEngine()
        import pytest
        with pytest.raises(ValueError, match="10KB"):
            pe.load_policy_yaml("x" * 11000)


class TestStats:
    def test_lists_presets(self) -> None:
        pe = PolicyEngine()
        policies = pe.list_policies()
        names = [p["name"] for p in policies]
        assert "strict" in names
        assert "gdpr" in names
        assert "hipaa" in names
        assert "pci_dss" in names
