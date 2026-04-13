"""TDD tests for services/pii_detector.py."""

from services.pii_detector import PIIDetector, RISK_LEVELS, compute_overall_risk, compute_risk_distribution


class TestDetect:
    def test_detects_email(self) -> None:
        d = PIIDetector()
        entities = d.detect("Contact me at john@example.com please")
        assert len(entities) >= 1
        assert entities[0].type == "email"
        assert entities[0].value == "john@example.com"

    def test_detects_phone(self) -> None:
        d = PIIDetector()
        entities = d.detect("Call +33 6 12 34 56 78")
        assert any(e.type == "phone_international" for e in entities)

    def test_detects_ssn_us(self) -> None:
        d = PIIDetector()
        entities = d.detect("SSN: 123-45-6789")
        assert any(e.type == "ssn_us" for e in entities)

    def test_detects_iban(self) -> None:
        d = PIIDetector()
        entities = d.detect("IBAN: FR7630006000011234567890189")
        assert any(e.type == "iban" for e in entities)

    def test_no_false_positive_on_clean_text(self) -> None:
        d = PIIDetector()
        entities = d.detect("The weather is nice today in Paris")
        assert len(entities) == 0

    def test_confidence_threshold(self) -> None:
        d = PIIDetector(confidence_threshold=0.99)
        entities = d.detect("IP: 192.168.1.1")  # ipv4 has 0.70 confidence
        assert len(entities) == 0


class TestAnonymize:
    def test_redact_strategy(self) -> None:
        d = PIIDetector()
        result = d.anonymize("Email: john@example.com", strategy="redact")
        assert "[EMAIL]" in result
        assert "john@example.com" not in result

    def test_mask_strategy(self) -> None:
        d = PIIDetector()
        result = d.anonymize("Email: john@example.com", strategy="mask")
        assert "***" in result

    def test_hash_strategy(self) -> None:
        d = PIIDetector()
        result = d.anonymize("Email: john@example.com", strategy="hash")
        assert "[hash:" in result

    def test_no_pii_returns_original(self) -> None:
        d = PIIDetector()
        text = "Hello world"
        assert d.anonymize(text) == text


class TestScanAndAnonymize:
    def test_combined_result(self) -> None:
        d = PIIDetector()
        result = d.scan_and_anonymize("Send to john@example.com and SSN 123-45-6789")
        assert result["pii_count"] == 2
        assert "email" in result["pii_types"]
        assert "ssn_us" in result["pii_types"]
        assert "john@example.com" not in result["anonymized_text"]

    def test_overall_risk_in_result(self) -> None:
        d = PIIDetector()
        result = d.scan_and_anonymize("Card 4111111111111111")
        assert "overall_risk" in result
        assert result["overall_risk"] == "critical"

    def test_risk_distribution_in_result(self) -> None:
        d = PIIDetector()
        result = d.scan_and_anonymize("john@example.com")
        assert "risk_distribution" in result
        assert isinstance(result["risk_distribution"], dict)


class TestNewEUEntities:
    def test_detects_siret_fr(self) -> None:
        d = PIIDetector()
        entities = d.detect("SIRET: 12345678901234")
        assert any(e.type == "siret_fr" for e in entities)

    def test_detects_siren_fr(self) -> None:
        d = PIIDetector(confidence_threshold=0.7)
        entities = d.detect("SIREN 123456789")
        assert any(e.type == "siren_fr" for e in entities)

    def test_detects_dni_es(self) -> None:
        d = PIIDetector()
        entities = d.detect("DNI: 12345678Z")
        assert any(e.type == "dni_es" for e in entities)

    def test_detects_nie_es(self) -> None:
        d = PIIDetector()
        entities = d.detect("NIE: X1234567Z")
        assert any(e.type == "nie_es" for e in entities)

    def test_detects_codice_fiscale_it(self) -> None:
        d = PIIDetector()
        entities = d.detect("Codice fiscale: RSSMRA85M01H501Z")
        assert any(e.type == "codice_fiscale_it" for e in entities)

    def test_detects_passport_generic(self) -> None:
        d = PIIDetector(confidence_threshold=0.6)
        entities = d.detect("Passport AB123456")
        assert any(e.type == "passport_generic" for e in entities)

    def test_detects_person_name(self) -> None:
        d = PIIDetector()
        entities = d.detect("Contacter M. Jean Dupont pour plus d'informations")
        assert any(e.type == "person_name" for e in entities)

    def test_detects_steuer_id_de(self) -> None:
        d = PIIDetector(confidence_threshold=0.7)
        entities = d.detect("Steuer-ID: 12345678901")
        assert any(e.type == "steuer_id_de" for e in entities)

    def test_detects_rib_fr(self) -> None:
        d = PIIDetector()
        entities = d.detect("RIB: 12345 12345 12345678901 23")
        assert any(e.type == "rib_fr" for e in entities)

    def test_entity_has_risk_level(self) -> None:
        d = PIIDetector()
        entities = d.detect("john@example.com")
        assert all(hasattr(e, "risk_level") for e in entities)
        assert entities[0].risk_level == "medium"

    def test_credit_card_risk_is_critical(self) -> None:
        d = PIIDetector()
        entities = d.detect("Card: 4111111111111111")
        cc = next((e for e in entities if e.type == "credit_card"), None)
        assert cc is not None
        assert cc.risk_level == "critical"


class TestRiskHelpers:
    def test_compute_overall_risk_empty(self) -> None:
        assert compute_overall_risk([]) == "none"

    def test_compute_overall_risk_max(self) -> None:
        assert compute_overall_risk(["low", "critical", "medium"]) == "critical"

    def test_compute_risk_distribution(self) -> None:
        dist = compute_risk_distribution(["low", "medium", "medium", "critical"])
        assert dist == {"low": 1, "medium": 2, "critical": 1}

    def test_risk_levels_dict_has_all_entities(self) -> None:
        expected = {
            "credit_card", "ssn_us", "ssn_fr", "iban", "rib_fr",
            "codice_fiscale_it", "passport_generic", "dni_es", "nie_es",
            "steuer_id_de", "siret_fr", "siren_fr", "person_name",
            "email", "phone_international", "date_of_birth", "ipv4",
        }
        assert expected.issubset(RISK_LEVELS.keys())


class TestOverlappingDedup:
    """Regression: SIRET (14 digits) and credit_card both matched the same span,
    causing the anonymizer to corrupt the text. Dedup must keep one entity per span."""

    def test_no_duplicate_spans_for_siret_collision(self) -> None:
        d = PIIDetector()
        entities = d.detect("ACME SIRET 12345678901234 done")
        spans = [(e.start, e.end) for e in entities]
        assert len(spans) == len(set(spans)), f"duplicate spans detected: {spans}"

    def test_anonymize_does_not_corrupt_text_around_collision(self) -> None:
        d = PIIDetector()
        text = "ACME SIRET 12345678901234 contact end"
        result = d.anonymize(text, strategy="redact")
        assert "contact end" in result, f"text corrupted: {result!r}"

    def test_higher_confidence_entity_wins_on_collision(self) -> None:
        d = PIIDetector()
        entities = d.detect("ACME SIRET 12345678901234 done")
        types = [e.type for e in entities]
        assert "siret_fr" in types
        assert "credit_card" not in types
