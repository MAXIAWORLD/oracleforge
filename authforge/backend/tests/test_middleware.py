"""Tests for ApiKeyAuth, RateLimit, and SecurityHeaders middleware."""

from __future__ import annotations



class TestApiKeyMiddleware:
    async def test_protected_route_without_key_rejected(self, no_key_client) -> None:
        r = await no_key_client.post(
            "/api/auth/login",
            json={
                "email": "x@x.com",
                "password": "password123",
            },
        )
        assert r.status_code == 401

    async def test_protected_route_with_wrong_key_rejected(self, no_key_client) -> None:
        r = await no_key_client.post(
            "/api/auth/login",
            json={"email": "x@x.com", "password": "password123"},
            headers={"X-API-Key": "totally-wrong-key"},
        )
        assert r.status_code == 401

    async def test_health_accessible_without_key(self, no_key_client) -> None:
        r = await no_key_client.get("/health")
        assert r.status_code == 200

    async def test_docs_accessible_without_key(self, no_key_client) -> None:
        r = await no_key_client.get("/docs")
        assert r.status_code == 200

    async def test_openapi_accessible_without_key(self, no_key_client) -> None:
        r = await no_key_client.get("/openapi.json")
        assert r.status_code == 200


class TestSecurityHeaders:
    async def test_x_content_type_options(self, client) -> None:
        r = await client.get("/health")
        assert r.headers.get("x-content-type-options") == "nosniff"

    async def test_x_frame_options(self, client) -> None:
        r = await client.get("/health")
        assert r.headers.get("x-frame-options") == "DENY"

    async def test_referrer_policy(self, client) -> None:
        r = await client.get("/health")
        assert r.headers.get("referrer-policy") == "no-referrer"

    async def test_headers_on_auth_routes(self, client) -> None:
        r = await client.post(
            "/api/auth/login", json={"email": "x@x.com", "password": "p"}
        )
        assert r.headers.get("x-content-type-options") == "nosniff"
        assert r.headers.get("x-frame-options") == "DENY"


class TestRateLimiterMiddleware:
    async def test_unit_allows_under_limit(self) -> None:
        from services.auth_service import RateLimiter

        rl = RateLimiter(max_requests=3, window_seconds=60)
        assert all(rl.is_allowed("ip1") for _ in range(3))

    async def test_unit_blocks_over_limit(self) -> None:
        from services.auth_service import RateLimiter

        rl = RateLimiter(max_requests=2, window_seconds=60)
        rl.is_allowed("ip1")
        rl.is_allowed("ip1")
        assert rl.is_allowed("ip1") is False

    async def test_unit_different_ips_independent(self) -> None:
        from services.auth_service import RateLimiter

        rl = RateLimiter(max_requests=1, window_seconds=60)
        assert rl.is_allowed("ip1") is True
        assert rl.is_allowed("ip2") is True
        assert rl.is_allowed("ip1") is False
