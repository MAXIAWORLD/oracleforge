"""TDD tests for services/pii_detector.py."""

from services.pii_detector import PIIDetector


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
