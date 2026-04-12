"""TDD tests for OutreachForge lead_scorer."""

from services.lead_scorer import LeadScorer


class TestScoring:
    def test_business_email_higher(self) -> None:
        s = LeadScorer()
        biz = s.score("john@company.com", "John Doe", "Acme Inc", "CTO")
        free = s.score("john@gmail.com")
        assert biz.score > free.score

    def test_cto_hot_tier(self) -> None:
        s = LeadScorer()
        result = s.score("cto@company.com", "Jane Smith", "TechCorp", "CTO")
        assert result.tier == "hot"
        assert result.score >= 0.6

    def test_minimal_info_cold(self) -> None:
        s = LeadScorer()
        result = s.score("someone@gmail.com")
        assert result.tier == "cold"
        assert result.score < 0.35

    def test_factors_included(self) -> None:
        s = LeadScorer()
        result = s.score("john@acme.com", "John Doe", "Acme")
        assert "business_email" in result.factors
        assert "full_name" in result.factors
        assert "company" in result.factors

    def test_score_capped_at_1(self) -> None:
        s = LeadScorer()
        result = s.score("ceo@bigcorp.com", "Jane Smith", "BigCorp", "CEO & Founder")
        assert result.score <= 1.0


class TestPersonalizer:
    def test_personalize(self) -> None:
        from services.email_personalizer import EmailPersonalizer
        p = EmailPersonalizer()
        result = p.personalize(
            "Hi {first_name}, I see you work at {company}.",
            {"name": "John Doe", "company": "Acme"},
        )
        assert "John" in result
        assert "Acme" in result

    def test_missing_var_preserved(self) -> None:
        from services.email_personalizer import EmailPersonalizer
        p = EmailPersonalizer()
        result = p.personalize("Hi {first_name}, {unknown} here.", {"name": "Jane"})
        assert "Jane" in result
        assert "{unknown}" in result

    def test_validate_template(self) -> None:
        from services.email_personalizer import EmailPersonalizer
        p = EmailPersonalizer()
        vars_used = p.validate_template("Hello {name}, from {company}")
        assert "name" in vars_used
        assert "company" in vars_used
