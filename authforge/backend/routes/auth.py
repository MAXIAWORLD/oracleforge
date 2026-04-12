"""AuthForge — Auth API routes.

Endpoints:
  POST /api/auth/register    — create account
  POST /api/auth/login       — login, get tokens
  POST /api/auth/refresh     — refresh access token
  GET  /api/auth/me          — current user info
  GET  /api/users            — list users (admin only)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Header, Request
from core.models import RegisterRequest, LoginRequest, TokenResponse, UserRead

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _get_auth(request: Request):
    return request.app.state.auth_service


# In-memory user store (replaced by DB in production)
_users: dict[str, dict] = {}
_next_id = 1


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, request: Request) -> TokenResponse:
    global _next_id
    auth = _get_auth(request)

    if req.email in _users:
        raise HTTPException(409, "Email already registered")

    user_id = _next_id
    _next_id += 1
    hashed = auth.hash_password(req.password)
    _users[req.email] = {
        "id": user_id,
        "email": req.email,
        "hashed_password": hashed,
        "display_name": req.display_name,
        "role": "user",
        "is_active": True,
    }

    tokens = auth.create_token_pair(user_id, req.email, "user")
    return TokenResponse(**tokens)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, request: Request) -> TokenResponse:
    auth = _get_auth(request)
    user = _users.get(req.email)
    if not user or not auth.verify_password(req.password, user["hashed_password"]):
        raise HTTPException(401, "Invalid email or password")
    if not user["is_active"]:
        raise HTTPException(403, "Account disabled")

    tokens = auth.create_token_pair(user["id"], user["email"], user["role"])
    return TokenResponse(**tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, authorization: str = Header(default="")) -> TokenResponse:
    auth = _get_auth(request)
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "Refresh token required")

    payload = auth.verify_token(token, token_type="refresh")
    if not payload:
        raise HTTPException(401, "Invalid or expired refresh token")

    user_id = int(payload["sub"])
    # Find user by ID
    user = next((u for u in _users.values() if u["id"] == user_id), None)
    if not user:
        raise HTTPException(401, "User not found")

    tokens = auth.create_token_pair(user["id"], user["email"], user["role"])
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
