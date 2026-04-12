"""TDD tests for AuthForge auth_service."""

import pytest
from core.config import Settings
from services.auth_service import AuthService, RateLimiter


@pytest.fixture
def auth() -> AuthService:
    return AuthService(Settings(secret_key="test-secret-key-32-chars-ok!!"))


class TestPasswordHashing:
    def test_hash_and_verify(self, auth) -> None:
        hashed = auth.hash_password("MyP@ssw0rd")
        assert auth.verify_password("MyP@ssw0rd", hashed) is True

    def test_wrong_password_fails(self, auth) -> None:
        hashed = auth.hash_password("correct")
        assert auth.verify_password("wrong", hashed) is False

    def test_different_hashes_for_same_password(self, auth) -> None:
        h1 = auth.hash_password("same")
        h2 = auth.hash_password("same")
        assert h1 != h2  # different salts


class TestJWT:
    def test_create_and_verify_access(self, auth) -> None:
        token = auth.create_access_token(1, "test@example.com", "user")
        payload = auth.verify_token(token, "access")
        assert payload is not None
        assert payload["sub"] == "1"
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "user"

    def test_create_and_verify_refresh(self, auth) -> None:
        token = auth.create_refresh_token(1)
        payload = auth.verify_token(token, "refresh")
        assert payload is not None
        assert payload["sub"] == "1"

    def test_wrong_type_rejected(self, auth) -> None:
        token = auth.create_access_token(1, "test@example.com", "user")
        assert auth.verify_token(token, "refresh") is None

    def test_invalid_token_rejected(self, auth) -> None:
        assert auth.verify_token("garbage.token.here") is None

    def test_token_pair(self, auth) -> None:
        pair = auth.create_token_pair(1, "test@example.com", "admin")
        assert "access_token" in pair
        assert "refresh_token" in pair
        assert pair["token_type"] == "bearer"
        assert pair["expires_in"] > 0


class TestApiKey:
    def test_generate_and_hash(self) -> None:
        raw, key_hash = AuthService.generate_api_key()
        assert raw.startswith("af_")
        assert len(key_hash) == 64
        assert AuthService.hash_api_key(raw) == key_hash


class TestRateLimiter:
    def test_allows_under_limit(self) -> None:
        rl = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert rl.is_allowed("user1") is True

    def test_blocks_over_limit(self) -> None:
        rl = RateLimiter(max_requests=2, window_seconds=60)
        assert rl.is_allowed("user1") is True
        assert rl.is_allowed("user1") is True
        assert rl.is_allowed("user1") is False

    def test_different_keys_independent(self) -> None:
        rl = RateLimiter(max_requests=1, window_seconds=60)
        assert rl.is_allowed("user1") is True
        assert rl.is_allowed("user2") is True
        assert rl.is_allowed("user1") is False

    def test_remaining(self) -> None:
        rl = RateLimiter(max_requests=5, window_seconds=60)
        rl.is_allowed("x")
        assert rl.remaining("x") == 4
