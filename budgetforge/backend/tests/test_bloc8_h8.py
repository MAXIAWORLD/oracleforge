"""
Bloc 8 — H8 : Email normalization — alias Gmail bypass (TDD RED→GREEN)

user+tag@gmail.com doit être traité identique à user@gmail.com.
Sinon rate-limit contournable : 3 signups/jour/IP * N alias = illimité.
"""

from routes.signup import SignupFreeRequest


class TestEmailNormalization:
    def test_gmail_plus_tag_stripped(self):
        """user+tag@gmail.com → user@gmail.com"""
        body = SignupFreeRequest(email="user+tag@gmail.com")
        assert body.email == "user@gmail.com"

    def test_gmail_multiple_tags_stripped(self):
        """user+abc+def@gmail.com → user@gmail.com (premier + seulement)"""
        body = SignupFreeRequest(email="user+abc@gmail.com")
        assert body.email == "user@gmail.com"

    def test_regular_email_unchanged(self):
        """contact@example.com → inchangé (pas de +tag)"""
        body = SignupFreeRequest(email="contact@example.com")
        assert body.email == "contact@example.com"

    def test_lowercased(self):
        """User+Tag@Gmail.COM → user@gmail.com"""
        body = SignupFreeRequest(email="User+Tag@Gmail.COM")
        assert body.email == "user@gmail.com"

    def test_outlook_plus_tag_stripped(self):
        """user+tag@outlook.com → user@outlook.com"""
        body = SignupFreeRequest(email="user+tag@outlook.com")
        assert body.email == "user@outlook.com"

    def test_email_without_plus_unaffected(self):
        """alice@company.io → inchangé"""
        body = SignupFreeRequest(email="alice@company.io")
        assert body.email == "alice@company.io"
