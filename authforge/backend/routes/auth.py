"""AuthForge — Auth API routes.

Endpoints:
  POST /api/auth/register    — create account
  POST /api/auth/login       — login, get tokens
  POST /api/auth/refresh     — refresh access token
  GET  /api/auth/me          — current user info
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import RegisterRequest, LoginRequest, TokenResponse, User

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _get_auth(request: Request):
    return request.app.state.auth_service


def _check_rate_limit(request: Request) -> None:
    """Apply rate limiting to sensitive auth endpoints."""
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter:
        client_ip = request.client.host if request.client else "unknown"
        if not limiter.is_allowed(client_ip):
            raise HTTPException(429, "Too many requests. Try again later.")


@router.post("/register", response_model=TokenResponse)
async def register(
    req: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    _check_rate_limit(request)
    auth = _get_auth(request)

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(409, "Email already registered")

    # Create user in DB
    user = User(
        email=req.email,
        hashed_password=auth.hash_password(req.password),
        display_name=req.display_name,
        role="user",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    tokens = auth.create_token_pair(user.id, user.email, user.role)
    return TokenResponse(**tokens)


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    _check_rate_limit(request)
    auth = _get_auth(request)

    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not auth.verify_password(req.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account disabled")

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    tokens = auth.create_token_pair(user.id, user.email, user.role)
    return TokenResponse(**tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    auth = _get_auth(request)
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "Refresh token required")

    payload = auth.verify_token(token, token_type="refresh")
    if not payload:
        raise HTTPException(401, "Invalid or expired refresh token")

    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(401, "User not found")

    tokens = auth.create_token_pair(user.id, user.email, user.role)
    return TokenResponse(**tokens)


@router.get("/me")
async def me(request: Request, authorization: str = Header(default="")) -> dict:
    auth = _get_auth(request)
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "Access token required")

    payload = auth.verify_token(token, token_type="access")
    if not payload:
        raise HTTPException(401, "Invalid or expired token")

    return {
        "user_id": payload["sub"],
        "email": payload["email"],
        "role": payload["role"],
    }


# ── OAuth Google ─────────────────────────────────────────────────

@router.get("/oauth/google/url")
async def oauth_google_url(request: Request) -> dict:
    """Get Google OAuth authorization URL."""
    from urllib.parse import urlencode
    from core.config import get_settings
    settings = get_settings()
    if not settings.oauth_google_client_id:
        raise HTTPException(503, "Google OAuth not configured")
    params = {
        "client_id": settings.oauth_google_client_id,
        "redirect_uri": f"{request.base_url}api/auth/oauth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return {"url": url}


@router.get("/oauth/google/callback")
async def oauth_google_callback(
    code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange Google OAuth code for tokens."""
    import httpx as _httpx
    from core.config import get_settings
    settings = get_settings()
    if not settings.oauth_google_client_id or not settings.oauth_google_client_secret:
        raise HTTPException(503, "Google OAuth not configured")

    # Exchange code for Google tokens
    async with _httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.oauth_google_client_id,
                "client_secret": settings.oauth_google_client_secret,
                "redirect_uri": f"{request.base_url}api/auth/oauth/google/callback",
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code != 200:
            raise HTTPException(400, "Failed to exchange OAuth code")
        token_data = resp.json()

        # Get user info
        resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        if resp.status_code != 200:
            raise HTTPException(400, "Failed to get user info")
        user_info = resp.json()

    email = user_info.get("email", "")
    name = user_info.get("name", "")
    if not email:
        raise HTTPException(400, "No email from Google")

    auth = _get_auth(request)

    # Find or create user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            hashed_password=auth.hash_password(f"oauth_{email}"),  # placeholder
            display_name=name,
            role="user",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    tokens = auth.create_token_pair(user.id, user.email, user.role)
    return TokenResponse(**tokens)
