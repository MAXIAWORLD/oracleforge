"""GuardForge — PII Scanner + Vault + Policy API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from core.config import get_settings

router = APIRouter(prefix="/api", tags=["guard"])


def _require_auth(authorization: str = Header(default="")) -> str:
    """Require Bearer token matching SECRET_KEY for vault endpoints."""
    settings = get_settings()
    token = authorization.replace("Bearer ", "").strip()
    if not token or token != settings.secret_key:
        raise HTTPException(401, "Unauthorized — Bearer token required")
    return token


class ScanRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100000)
    policy: str | None = None
    strategy: str = "redact"  # redact | mask | hash


class VaultStoreRequest(BaseModel):
    key: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)


class LLMWrapRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50000)
    policy: str | None = None


@router.post("/scan")
async def scan_text(req: ScanRequest, request: Request) -> dict:
    """Scan text for PII, evaluate policy, and return anonymized version."""
    detector = request.app.state.pii_detector
    policy_engine = request.app.state.policy_engine

    result = detector.scan_and_anonymize(req.text, strategy=req.strategy)
    decision = policy_engine.evaluate(
        pii_types_found=result["pii_types"],
        pii_count=result["pii_count"],
        policy_name=req.policy,
    )
    return {**result, "policy_decision": {
        "allowed": decision.allowed,
        "action": decision.action,
        "reason": decision.reason,
        "policy": decision.policy_name,
    }}


@router.post("/llm/wrap")
async def llm_wrap(req: LLMWrapRequest, request: Request) -> dict:
    """Strip PII before sending to LLM, return safe text."""
    detector = request.app.state.pii_detector
    result = detector.scan_and_anonymize(req.text, strategy="redact")
    return {
        "safe_text": result["anonymized_text"],
        "pii_stripped": result["pii_count"],
        "pii_types": result["pii_types"],
    }


@router.get("/policies")
async def list_policies(request: Request) -> dict:
    engine = request.app.state.policy_engine
    return {"policies": engine.list_policies()}


@router.post("/vault/store")
async def vault_store(req: VaultStoreRequest, request: Request, _: str = Depends(_require_auth)) -> dict:
    vault = request.app.state.vault
    if not vault.is_available:
        raise HTTPException(503, "Vault not available")
    vault.store_secret(req.key, req.value)
    return {"stored": True, "key": req.key}


@router.get("/vault/get/{key}")
async def vault_get(key: str, request: Request, _: str = Depends(_require_auth)) -> dict:
    vault = request.app.state.vault
    if not vault.is_available:
        raise HTTPException(503, "Vault not available")
    value = vault.get_secret(key)
    if value is None:
        raise HTTPException(404, f"Key '{key}' not found")
    return {"key": key, "value": value}


@router.delete("/vault/delete/{key}")
async def vault_delete(key: str, request: Request, _: str = Depends(_require_auth)) -> dict:
    vault = request.app.state.vault
    existed = vault.delete_secret(key)
    return {"deleted": existed, "key": key}


@router.get("/vault/keys")
async def vault_keys(request: Request, _: str = Depends(_require_auth)) -> dict:
    vault = request.app.state.vault
    keys = vault.list_keys()
    return {"keys": keys, "count": len(keys)}
