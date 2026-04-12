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
