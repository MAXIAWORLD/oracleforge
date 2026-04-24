"""Integration tests — HTTP routes. TDD: written before verifying full green."""

from __future__ import annotations


_REG = {
    "email": "alice@example.com",
    "password": "SecureP@ss1",
    "display_name": "Alice",
}


class TestHealth:
    async def test_health_ok(self, client) -> None:
        r = await client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "version" in body

    async def test_health_accessible_without_api_key(self, no_key_client) -> None:
        r = await no_key_client.get("/health")
        assert r.status_code == 200


class TestRegister:
    async def test_register_success(self, client) -> None:
        r = await client.post("/api/auth/register", json=_REG)
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0

    async def test_register_duplicate_email(self, client) -> None:
        await client.post("/api/auth/register", json=_REG)
        r = await client.post("/api/auth/register", json=_REG)
        assert r.status_code == 409

    async def test_register_password_too_short(self, client) -> None:
        r = await client.post(
            "/api/auth/register",
            json={
                "email": "bob@example.com",
                "password": "short",
            },
        )
        assert r.status_code == 422

    async def test_register_missing_email(self, client) -> None:
        r = await client.post("/api/auth/register", json={"password": "SecureP@ss1"})
        assert r.status_code == 422

    async def test_register_without_display_name(self, client) -> None:
        r = await client.post(
            "/api/auth/register",
            json={
                "email": "carol@example.com",
                "password": "SecureP@ss1",
            },
        )
        assert r.status_code == 200

    async def test_register_sets_user_role(self, client) -> None:
        reg = await client.post("/api/auth/register", json=_REG)
        access = reg.json()["access_token"]
        me = await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {access}"}
        )
        assert me.json()["role"] == "user"


class TestLogin:
    async def test_login_success(self, client) -> None:
        await client.post("/api/auth/register", json=_REG)
        r = await client.post(
            "/api/auth/login",
            json={
                "email": _REG["email"],
                "password": _REG["password"],
            },
        )
        assert r.status_code == 200
        assert "access_token" in r.json()

    async def test_login_wrong_password(self, client) -> None:
        await client.post("/api/auth/register", json=_REG)
        r = await client.post(
            "/api/auth/login",
            json={
                "email": _REG["email"],
                "password": "WrongPassword!",
            },
        )
        assert r.status_code == 401

    async def test_login_unknown_email(self, client) -> None:
        r = await client.post(
            "/api/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "SomePass1!",
            },
        )
        assert r.status_code == 401

    async def test_login_inactive_user(self, client, db) -> None:
        from sqlalchemy import update
        from core.models import User

        await client.post("/api/auth/register", json=_REG)
        await db.execute(
            update(User).where(User.email == _REG["email"]).values(is_active=False)
        )
        await db.commit()

        r = await client.post(
            "/api/auth/login",
            json={
                "email": _REG["email"],
                "password": _REG["password"],
            },
        )
        assert r.status_code == 403


class TestRefresh:
    async def test_refresh_success(self, client) -> None:
        reg = await client.post("/api/auth/register", json=_REG)
        refresh = reg.json()["refresh_token"]
        r = await client.post(
            "/api/auth/refresh", headers={"Authorization": f"Bearer {refresh}"}
        )
        assert r.status_code == 200
        assert "access_token" in r.json()

    async def test_refresh_invalid_token(self, client) -> None:
        r = await client.post(
            "/api/auth/refresh", headers={"Authorization": "Bearer not.a.real.token"}
        )
        assert r.status_code == 401

    async def test_refresh_missing_token(self, client) -> None:
        r = await client.post("/api/auth/refresh")
        assert r.status_code == 401

    async def test_refresh_rejects_access_token(self, client) -> None:
        reg = await client.post("/api/auth/register", json=_REG)
        access = reg.json()["access_token"]
        r = await client.post(
            "/api/auth/refresh", headers={"Authorization": f"Bearer {access}"}
        )
        assert r.status_code == 401


class TestMe:
    async def test_me_success(self, client) -> None:
        reg = await client.post("/api/auth/register", json=_REG)
        access = reg.json()["access_token"]
        r = await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {access}"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == _REG["email"]
        assert body["role"] == "user"
        assert "user_id" in body

    async def test_me_invalid_token(self, client) -> None:
        r = await client.get(
            "/api/auth/me", headers={"Authorization": "Bearer garbage.token"}
        )
        assert r.status_code == 401

    async def test_me_missing_token(self, client) -> None:
        r = await client.get("/api/auth/me")
        assert r.status_code == 401

    async def test_me_refresh_token_rejected(self, client) -> None:
        reg = await client.post("/api/auth/register", json=_REG)
        refresh = reg.json()["refresh_token"]
        r = await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {refresh}"}
        )
        assert r.status_code == 401


class TestOAuth:
    async def test_oauth_google_url_unconfigured(self, client) -> None:
        r = await client.get("/api/auth/oauth/google/url")
        assert r.status_code == 503

    async def test_oauth_google_callback_unconfigured(self, client) -> None:
        r = await client.get("/api/auth/oauth/google/callback?code=fake")
        assert r.status_code == 503
