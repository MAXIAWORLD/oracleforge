"""GuardForge — PII Scanner + Vault + Policy + Tokenizer API routes."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from core.config import get_settings
from core.database import get_db
from core.models import ScanLog, Webhook

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["guard"])


# ── Auth dependency ──────────────────────────────────────────────

def _require_auth(x_api_key: str = Header(default="")) -> str:
    """Require X-API-Key header matching SECRET_KEY."""
    settings = get_settings()
    if not x_api_key or x_api_key != settings.secret_key:
        # Fallback: also accept Bearer token for backward compat
        raise HTTPException(401, "Unauthorized — X-API-Key required")
    return x_api_key


def _require_auth_bearer(
    x_api_key: str = Header(default=""),
    authorization: str = Header(default=""),
) -> str:
    """Accept X-API-Key or Bearer token for vault endpoints (backward compat)."""
    settings = get_settings()
    # Try X-API-Key first
    if x_api_key and x_api_key == settings.secret_key:
        return x_api_key
    # Fall back to Bearer
    token = authorization.replace("Bearer ", "").strip()
    if token and token == settings.secret_key:
        return token
    raise HTTPException(401, "Unauthorized — Bearer token or X-API-Key required")


# ── Request / Response models ────────────────────────────────────

class ScanRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="Text to scan for PII. Max 100k characters.",
    )
    policy: str | None = Field(
        default=None,
        description="Policy name to apply (strict, moderate, permissive, gdpr, hipaa, pci_dss). Defaults to backend DEFAULT_POLICY.",
    )
    strategy: str = Field(
        default="redact",
        description="Anonymization strategy: 'redact' replaces with [TYPE], 'mask' with ***, 'hash' with [hash:xxxxx].",
    )
    dry_run: bool = Field(
        default=False,
        description="If true, detect entities without anonymizing the text. Useful for previews.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "text": "Hi, my name is Jean Dupont and my IBAN is FR7630006000011234567890189",
                    "policy": "gdpr",
                    "strategy": "redact",
                    "dry_run": False,
                }
            ]
        }
    }


class VaultStoreRequest(BaseModel):
    key: str = Field(..., min_length=1, description="Unique secret identifier (e.g. 'openai_api_key').")
    value: str = Field(..., min_length=1, description="Plaintext value to encrypt and store.")

    model_config = {
        "json_schema_extra": {
            "examples": [{"key": "openai_api_key", "value": "sk-proj-xxxxxxxxxxxx"}]
        }
    }


class LLMWrapRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50000, description="Text containing PII to strip before sending to an LLM.")
    policy: str | None = Field(default=None, description="Optional policy name.")


class TokenizeRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="Text containing PII to replace with reversible tokens.",
    )
    policy: str | None = Field(default=None, description="Optional policy name (reserved for future use).")
    session_id: str | None = Field(
        default=None,
        description="Existing session UUID to continue. If omitted, a new session is created and returned in the response.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"text": "Contact Jean Dupont at jean@example.fr", "session_id": None}
            ]
        }
    }


class DetokenizeRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="Text containing [TYPE_xxxx] tokens to restore to original values.",
    )
    session_id: str = Field(
        ...,
        min_length=1,
        description="The session UUID returned by the original /api/tokenize call.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "text": "Hello [PERSON_NAME_a3f2], your IBAN [IBAN_b491] is confirmed.",
                    "session_id": "ed814fc5-7e97-4949-87c0-dea5e25cfac7",
                }
            ]
        }
    }


# ── Helpers ──────────────────────────────────────────────────────

async def _maybe_dispatch_webhooks(
    input_hash: str,
    pii_count: int,
    pii_types: list[str],
    policy: str,
    action: str,
    risk_level: str,
) -> None:
    """Fetch enabled webhooks and dispatch a high-risk event if appropriate.

    Runs as a fire-and-forget background task. Failures are logged but never
    propagated to the scan endpoint — webhook delivery must NEVER block or
    break the scan flow.
    """
    logger.info("[webhook] dispatch entry: risk=%s", risk_level)
    if risk_level not in ("critical", "high"):
        return
    try:
        async for db_session in get_db():
            stmt = select(Webhook).where(Webhook.enabled == 1)
            rows = (await db_session.execute(stmt)).scalars().all()
            logger.info("[webhook] found %d enabled webhooks", len(rows))
            if not rows:
                return
            webhooks_data = [
                {
                    "id": w.id,
                    "name": w.name,
                    "url": w.url,
                    "secret": w.secret,
                    "min_risk_level": w.min_risk_level,
                    "enabled": True,
                }
                for w in rows
            ]
            from services.webhook_dispatcher import dispatch_event
            results = await dispatch_event(
                webhooks=webhooks_data,
                event_type=f"scan.{risk_level}_risk",
                risk_level=risk_level,
                payload={
                    "scan_input_hash": input_hash,
                    "pii_count": pii_count,
                    "pii_types": pii_types,
                    "action": action,
                    "policy": policy,
                },
            )
            logger.info("[webhook] dispatch results: %s", results)
            return
    except Exception as exc:
        logger.warning("[webhook] dispatch failed: %s", exc, exc_info=True)


async def _persist_scan_log(
    request: Request,
    input_hash: str,
    pii_count: int,
    pii_types: list[str],
    policy: str,
    action: str,
    risk_level: str,
) -> None:
    """Insert a ScanLog row. Falls back to in-memory log on error."""
    try:
        async for session in get_db():
            log_row = ScanLog(
                input_hash=input_hash,
                pii_found=pii_count,
                pii_types=json.dumps(pii_types),
                policy_applied=policy,
                action_taken=action,
                risk_level=risk_level,
                scanned_at=datetime.now(tz=timezone.utc),
            )
            session.add(log_row)
            await session.commit()
            return
    except Exception as exc:
        logger.error("[scanner] DB audit log failed: %s", exc)
        # Fallback: write to in-memory list
        import time as _time
        audit_log = getattr(request.app.state, "audit_log", None)
        if audit_log is not None:
            audit_log.append({
                "ts": _time.time(),
                "input_hash": input_hash,
                "pii_count": pii_count,
                "pii_types": pii_types,
                "policy": policy,
                "action": action,
                "risk_level": risk_level,
            })
            if len(audit_log) > 1000:
                del audit_log[:-1000]


# ── Endpoints ────────────────────────────────────────────────────

@router.post(
    "/scan",
    summary="Scan text for PII and apply policy",
    description=(
        "Detects all PII entities in the input text using regex-based detection across 17 entity types "
        "(email, phone, SSN US/FR, IBAN, credit card with Luhn validation, SIRET, SIREN, RIB, Steuer-ID, "
        "DNI/NIE, Codice Fiscale, passport, person names, etc.). Applies the requested anonymization "
        "strategy and evaluates against the named policy. Returns the entities with risk levels, the "
        "anonymized text, and the policy decision (allow/block/anonymize/warn). Every scan is logged "
        "to the persistent audit trail for compliance reporting."
    ),
    responses={
        200: {"description": "Scan successful — see entities, anonymized_text, overall_risk, policy_decision."},
        401: {"description": "Missing or invalid X-API-Key."},
        422: {"description": "Invalid request body (e.g. text exceeds 100k chars)."},
        429: {"description": "Rate limit exceeded (60 req/min default)."},
    },
)
async def scan_text(req: ScanRequest, request: Request) -> dict:
    """Scan text for PII, evaluate policy, and optionally anonymize."""
    detector = request.app.state.pii_detector
    policy_engine = request.app.state.policy_engine

    if req.dry_run:
        # Dry run: detect only, no anonymisation
        entities = detector.detect(req.text)
        pii_types = list({e.type for e in entities})
        risk_levels = [e.risk_level for e in entities]
        decision = policy_engine.evaluate(pii_types, len(entities), req.policy)
        from services.pii_detector import compute_overall_risk, compute_risk_distribution
        result: dict = {
            "original_length": len(req.text),
            "pii_count": len(entities),
            "pii_types": pii_types,
            "entities": [
                {
                    "type": e.type,
                    "start": e.start,
                    "end": e.end,
                    "confidence": e.confidence,
                    "risk_level": e.risk_level,
                }
                for e in entities
            ],
            "anonymized_text": None,
            "dry_run": True,
            "overall_risk": compute_overall_risk(risk_levels),
            "risk_distribution": compute_risk_distribution(risk_levels),
        }
    else:
        result = detector.scan_and_anonymize(req.text, strategy=req.strategy)
        pii_types = result["pii_types"]
        decision = policy_engine.evaluate(pii_types, result["pii_count"], req.policy)
        result["dry_run"] = False

    overall_risk = result.get("overall_risk", "none")
    input_hash = hashlib.sha256(req.text.encode()).hexdigest()[:16]

    await _persist_scan_log(
        request=request,
        input_hash=input_hash,
        pii_count=result["pii_count"],
        pii_types=result["pii_types"],
        policy=req.policy or "default",
        action=decision.action,
        risk_level=overall_risk,
    )

    # Fire-and-forget webhook dispatch for high-risk events
    asyncio.create_task(_maybe_dispatch_webhooks(
        input_hash=input_hash,
        pii_count=result["pii_count"],
        pii_types=result["pii_types"],
        policy=req.policy or "default",
        action=decision.action,
        risk_level=overall_risk,
    ))

    return {**result, "policy_decision": {
        "allowed": decision.allowed,
        "action": decision.action,
        "reason": decision.reason,
        "policy": decision.policy_name,
    }}


@router.post(
    "/llm/wrap",
    summary="Strip PII before sending text to an LLM",
    description=(
        "Lightweight one-shot endpoint that detects and redacts PII in text intended for an LLM call. "
        "Returns the safe text, the count of PII items stripped, and the list of PII types found. "
        "Use `/api/tokenize` instead if you need to **restore** the original values after the LLM "
        "responds — `/llm/wrap` is one-way (redact-only)."
    ),
    responses={
        200: {"description": "Returns safe_text, pii_stripped count, pii_types list."},
        401: {"description": "Missing or invalid X-API-Key."},
        422: {"description": "Invalid request body."},
    },
)
async def llm_wrap(req: LLMWrapRequest, request: Request) -> dict:
    """Strip PII before sending to LLM, return safe text."""
    detector = request.app.state.pii_detector
    result = detector.scan_and_anonymize(req.text, strategy="redact")
    return {
        "safe_text": result["anonymized_text"],
        "pii_stripped": result["pii_count"],
        "pii_types": result["pii_types"],
    }


@router.post(
    "/tokenize",
    summary="Replace PII with reversible tokens",
    description=(
        "Detects PII in the input text and replaces each unique value with a stable, deterministic "
        "token of the form `[ENTITY_TYPE_xxxx]` (where `xxxx` is a 4-character hash of the original "
        "value). The mapping `{token: original_value}` is encrypted (AES-256 / Fernet) and persisted "
        "in the vault under `tokenmap:<session_id>` — it survives backend restarts.\n\n"
        "**Workflow**: tokenize → send tokens to OpenAI/Anthropic → receive LLM response (still containing tokens) "
        "→ call `/api/detokenize` with the same `session_id` to restore the real values for your end user.\n\n"
        "PII never leaves your infrastructure."
    ),
    responses={
        200: {"description": "Returns tokenized_text, session_id, token_count, entities."},
        401: {"description": "Missing or invalid X-API-Key."},
        422: {"description": "Invalid request body."},
    },
)
async def tokenize_text(
    req: TokenizeRequest,
    request: Request,
    _: str = Depends(_require_auth),
) -> dict:
    """Replace PII with reversible tokens, backed by encrypted vault."""
    from services.tokenizer import Tokenizer

    tokenizer = Tokenizer(
        detector=request.app.state.pii_detector,
        vault=request.app.state.vault,
    )
    tr = tokenizer.tokenize(req.text, policy=req.policy, session_id=req.session_id)

    input_hash = hashlib.sha256(req.text.encode()).hexdigest()[:16]
    risk_levels = [e.risk_level for e in tr.entities]
    from services.pii_detector import compute_overall_risk
    overall_risk = compute_overall_risk(risk_levels)
    pii_types = list({e.type for e in tr.entities})

    await _persist_scan_log(
        request=request,
        input_hash=input_hash,
        pii_count=len(tr.entities),
        pii_types=pii_types,
        policy=req.policy or "default",
        action="tokenize",
        risk_level=overall_risk,
    )

    return {
        "tokenized_text": tr.tokenized_text,
        "session_id": tr.session_id,
        "token_count": len(tr.mapping),
        "entities": [
            {
                "type": e.type,
                "start": e.start,
                "end": e.end,
                "confidence": e.confidence,
                "risk_level": e.risk_level,
            }
            for e in tr.entities
        ],
    }


@router.post(
    "/detokenize",
    summary="Restore original PII values from tokens",
    description=(
        "Reverses tokenization using the encrypted mapping stored under the given `session_id`. "
        "Pass the LLM's response (which still contains `[TYPE_xxxx]` tokens) and the same `session_id` "
        "you got back from `/api/tokenize`. Returns the text with all tokens replaced by their original "
        "PII values.\n\n"
        "**Important**: the vault must be persistent (set `VAULT_ENCRYPTION_KEY` in `.env`) for sessions "
        "to survive backend restarts. Without it, sessions are lost on every restart."
    ),
    responses={
        200: {"description": "Returns original_text with tokens restored."},
        401: {"description": "Missing or invalid X-API-Key."},
        404: {"description": "No mapping found for the given session_id (session expired or vault key changed)."},
        422: {"description": "Invalid request body."},
    },
)
async def detokenize_text(
    req: DetokenizeRequest,
    request: Request,
    _: str = Depends(_require_auth),
) -> dict:
    """Reverse tokenization using the stored session mapping."""
    from services.tokenizer import Tokenizer

    tokenizer = Tokenizer(
        detector=request.app.state.pii_detector,
        vault=request.app.state.vault,
    )
    try:
        original_text = tokenizer.detokenize(req.text, session_id=req.session_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc

    return {"original_text": original_text}


@router.get(
    "/policies",
    summary="List all available policies",
    description=(
        "Returns all currently loaded compliance policies (built-in presets + any custom YAML policies). "
        "Each entry includes the name, default action, and an empty description (descriptions are "
        "translated client-side via the dashboard's i18n files for multi-language support)."
    ),
)
async def list_policies(request: Request) -> dict:
    engine = request.app.state.policy_engine
    return {"policies": engine.list_policies()}


@router.get(
    "/audit",
    summary="Get persistent scan audit log",
    description=(
        "Returns the last N scan operations from the persistent audit trail (default 50, max 500). "
        "Each entry contains the input hash (not the original text), pii_count, pii_types (parsed array), "
        "policy applied, action taken, risk level, and timestamp. Used by the dashboard `/audit` page "
        "and by external SIEM/compliance tools.\n\n"
        "**Persistence**: entries are stored in the `scan_logs` table and survive restarts."
    ),
)
async def get_audit_log(request: Request, limit: int = 50) -> dict:
    """Get recent scan audit trail from DB (fallback: in-memory)."""
    if limit < 1:
        limit = 1
    if limit > 500:
        limit = 500

    try:
        async for session in get_db():
            stmt = (
                select(ScanLog)
                .order_by(ScanLog.scanned_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            entries = []
            for r in rows:
                try:
                    parsed_types = json.loads(r.pii_types) if r.pii_types else []
                except (ValueError, TypeError):
                    parsed_types = []
                entries.append({
                    "id": r.id,
                    "input_hash": r.input_hash,
                    "pii_count": r.pii_found,
                    "pii_types": parsed_types,
                    "policy": r.policy_applied,
                    "action": r.action_taken,
                    "risk_level": r.risk_level,
                    "timestamp": r.scanned_at.isoformat() if r.scanned_at else None,
                    "dry_run": False,
                })
            return {"entries": entries, "total": len(entries)}
    except Exception as exc:
        logger.error("[audit] DB read failed, falling back to in-memory: %s", exc)

    # Fallback: in-memory list
    audit_log = getattr(request.app.state, "audit_log", [])
    return {"entries": list(reversed(audit_log[-limit:])), "total": len(audit_log)}


@router.post(
    "/vault/store",
    summary="Encrypt and store a secret in the vault",
    description=(
        "Encrypts the value using AES-256 (Fernet) with the configured `VAULT_ENCRYPTION_KEY` and "
        "persists it to the database. Survives backend restarts. Used internally by the tokenizer "
        "to store reversible mappings, but you can also use it for your own application secrets "
        "(API keys, credentials, etc.)."
    ),
)
async def vault_store(
    req: VaultStoreRequest,
    request: Request,
    _: str = Depends(_require_auth_bearer),
) -> dict:
    vault = request.app.state.vault
    if not vault.is_available:
        raise HTTPException(503, "Vault not available")
    vault.store_secret(req.key, req.value)
    return {"stored": True, "key": req.key}


@router.get(
    "/vault/get/{key}",
    summary="Retrieve and decrypt a vault secret",
    description="Returns the plaintext value for the given key, or 404 if not found.",
)
async def vault_get(
    key: str,
    request: Request,
    _: str = Depends(_require_auth_bearer),
) -> dict:
    vault = request.app.state.vault
    if not vault.is_available:
        raise HTTPException(503, "Vault not available")
    value = vault.get_secret(key)
    if value is None:
        raise HTTPException(404, f"Key '{key}' not found")
    return {"key": key, "value": value}


@router.delete(
    "/vault/delete/{key}",
    summary="Delete a vault secret",
    description="Removes the secret from both the in-memory cache and the persistent storage. Returns whether the key existed.",
)
async def vault_delete(
    key: str,
    request: Request,
    _: str = Depends(_require_auth_bearer),
) -> dict:
    vault = request.app.state.vault
    existed = vault.delete_secret(key)
    return {"deleted": existed, "key": key}


@router.get(
    "/vault/keys",
    summary="List all stored vault keys (no values)",
    description="Returns the list of secret keys without exposing their plaintext values. Useful for inventory and audit purposes.",
)
async def vault_keys(
    request: Request,
    _: str = Depends(_require_auth_bearer),
) -> dict:
    vault = request.app.state.vault
    keys = vault.list_keys()
    return {"keys": keys, "count": len(keys)}
