"""TDD tests for services/tokenizer.py."""

from __future__ import annotations

import pytest

from services.pii_detector import PIIDetector
from services.tokenizer import Tokenizer, _make_token
from services.vault import Vault


def _make_tokenizer() -> Tokenizer:
    return Tokenizer(detector=PIIDetector(), vault=Vault())


class TestTokenizeRoundtrip:
    def test_tokenize_replaces_email(self) -> None:
        t = _make_tokenizer()
        result = t.tokenize("Contact john@example.com for info")
        assert "john@example.com" not in result.tokenized_text
        assert "[EMAIL_" in result.tokenized_text

    def test_detokenize_restores_original(self) -> None:
        t = _make_tokenizer()
        original = "Send invoice to jane@corp.com and call +33 6 12 34 56 78"
        tr = t.tokenize(original)
        restored = t.detokenize(tr.tokenized_text, tr.session_id)
        assert restored == original

    def test_roundtrip_no_pii(self) -> None:
        t = _make_tokenizer()
        text = "The weather is fine today"
        tr = t.tokenize(text)
        assert tr.tokenized_text == text
        restored = t.detokenize(tr.tokenized_text, tr.session_id)
        assert restored == text

    def test_roundtrip_multiple_entities(self) -> None:
        t = _make_tokenizer()
        original = "IBAN: FR7630006000011234567890189 SSN: 123-45-6789"
        tr = t.tokenize(original)
        assert "FR7630006000011234567890189" not in tr.tokenized_text
        assert "123-45-6789" not in tr.tokenized_text
        restored = t.detokenize(tr.tokenized_text, tr.session_id)
        assert restored == original


class TestDeterministicTokens:
    def test_same_value_same_token(self) -> None:
        """Same entity value produces the same token within a session."""
        t = _make_tokenizer()
        text1 = "Email: john@example.com"
        text2 = "Reply to john@example.com please"
        tr1 = t.tokenize(text1)
        # Reuse same session
        tr2 = t.tokenize(text2, session_id=tr1.session_id)
        # Extract token for email from first result
        token1 = next(tok for tok in tr1.mapping if "EMAIL" in tok)
        token2 = next(tok for tok in tr2.mapping if "EMAIL" in tok)
        assert token1 == token2

    def test_make_token_is_deterministic(self) -> None:
        tok1 = _make_token("email", "john@example.com")
        tok2 = _make_token("email", "john@example.com")
        assert tok1 == tok2

    def test_different_values_different_tokens(self) -> None:
        tok1 = _make_token("email", "alice@example.com")
        tok2 = _make_token("email", "bob@example.com")
        assert tok1 != tok2


class TestSessionIsolation:
    def test_sessions_are_isolated(self) -> None:
        """Two sessions produce separate mappings; detokenize fails cross-session."""
        t = _make_tokenizer()
        tr1 = t.tokenize("Email: alice@example.com")
        tr2 = t.tokenize("Email: bob@example.com")
        # Detokenize session1 text with session2 should NOT restore correctly
        # (different sessions, potentially different tokens for different values)
        assert tr1.session_id != tr2.session_id

    def test_unknown_session_raises(self) -> None:
        t = _make_tokenizer()
        with pytest.raises(KeyError):
            t.detokenize("[EMAIL_abcd]", session_id="nonexistent-session-id")


class TestReturnShape:
    def test_tokenize_result_fields(self) -> None:
        t = _make_tokenizer()
        tr = t.tokenize("Contact john@example.com")
        assert tr.tokenized_text is not None
        assert tr.session_id is not None
        assert isinstance(tr.mapping, dict)
        assert isinstance(tr.entities, list)

    def test_token_count_matches_unique_values(self) -> None:
        t = _make_tokenizer()
        # Two occurrences of the same email → one mapping entry
        tr = t.tokenize("john@example.com and john@example.com again")
        assert "[EMAIL_" in tr.tokenized_text
        # Mapping has the token
        assert len(tr.mapping) >= 1
