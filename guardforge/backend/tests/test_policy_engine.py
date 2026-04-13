"""TDD tests for services/policy_engine.py."""

from services.policy_engine import PolicyEngine, PRESETS


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


class TestJurisdictionPresets:
    """Verify the 13 jurisdiction-specific presets are loaded with required metadata."""

    EXPECTED_JURISDICTIONS = {
        "gdpr", "eu_ai_act", "hipaa", "ccpa", "lgpd", "pci_dss",
        "pipeda", "appi", "pdpa_sg", "popia", "dpdp_in", "pipl_cn", "privacy_au",
    }

    def test_all_jurisdictions_loaded(self) -> None:
        pe = PolicyEngine()
        names = {p["name"] for p in pe.list_policies()}
        assert self.EXPECTED_JURISDICTIONS.issubset(names)

    def test_each_has_jurisdiction_field(self) -> None:
        for name in self.EXPECTED_JURISDICTIONS:
            preset = PRESETS[name]
            assert "jurisdiction" in preset, f"{name} missing jurisdiction"
            assert preset["jurisdiction"], f"{name} jurisdiction is empty"

    def test_each_has_regulation_field(self) -> None:
        for name in self.EXPECTED_JURISDICTIONS:
            preset = PRESETS[name]
            assert "regulation" in preset, f"{name} missing regulation"
            assert preset["regulation"], f"{name} regulation is empty"

    def test_pipl_blocks_personal_data(self) -> None:
        """PIPL is stricter than GDPR — should block, not anonymize."""
        pe = PolicyEngine()
        decision = pe.evaluate(["email"], 1, policy_name="pipl_cn")
        assert decision.action == "block"

    def test_eu_ai_act_blocks_high_risk(self) -> None:
        pe = PolicyEngine()
        decision = pe.evaluate(["person_name", "credit_card"], 2, policy_name="eu_ai_act")
        assert decision.action == "block"

    def test_ccpa_anonymizes_consumer_data(self) -> None:
        pe = PolicyEngine()
        decision = pe.evaluate(["email"], 1, policy_name="ccpa")
        assert decision.action == "anonymize"

    def test_list_policies_includes_jurisdiction_metadata(self) -> None:
        pe = PolicyEngine()
        gdpr = next(p for p in pe.list_policies() if p["name"] == "gdpr")
        assert gdpr["jurisdiction"] == "EU"
        assert "Data Protection Regulation" in gdpr["regulation"]
