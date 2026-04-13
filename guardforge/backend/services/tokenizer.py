"""GuardForge — Reversible PII Tokenizer.

Replaces PII entities with stable, deterministic tokens within a session.
Token format: [ENTITY_TYPE_<4-char-hex>]
Mappings are stored encrypted in the Vault under key 'tokenmap:<session_id>'.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid

from services.pii_detector import PIIDetector, PIIEntity
from services.vault import Vault, VaultUnavailable

logger = logging.getLogger(__name__)

_VAULT_KEY_PREFIX = "tokenmap:"


def _make_token(entity_type: str, value: str) -> str:
    """Create a deterministic token for a given entity type and value."""
    hex_suffix = hashlib.sha256(value.encode()).hexdigest()[:4]
    return f"[{entity_type.upper()}_{hex_suffix}]"


class TokenizerResult:
    """Result of a tokenize operation."""

    def __init__(
        self,
        tokenized_text: str,
        session_id: str,
        mapping: dict[str, str],
        entities: list[PIIEntity],
    ) -> None:
        self.tokenized_text = tokenized_text
        self.session_id = session_id
        self.mapping = mapping  # {token: original_value}
        self.entities = entities


class Tokenizer:
    """Replace PII with stable reversible tokens, backed by encrypted vault."""

    def __init__(self, detector: PIIDetector, vault: Vault) -> None:
        self._detector = detector
        self._vault = vault

    def tokenize(
        self,
        text: str,
        policy: str | None = None,
        session_id: str | None = None,
    ) -> TokenizerResult:
        """Detect PII and replace with tokens.

        Args:
            text: Input text to tokenize.
            policy: Optional policy name (unused at tokenize level, reserved).
            session_id: Existing session UUID to continue; creates new if None.

        Returns:
            TokenizerResult with tokenized_text, session_id, mapping, entities.
        """
        sid = session_id or str(uuid.uuid4())
        entities = self._detector.detect(text)

        # Load existing mapping for this session (if any)
        existing = self._load_mapping(sid)
        new_mapping: dict[str, str] = dict(existing) if existing is not None else {}

        # Process text from end to start to preserve positions
        result = text
        for entity in reversed(entities):
            token = _make_token(entity.type, entity.value)
            new_mapping[token] = entity.value
            result = result[: entity.start] + token + result[entity.end :]

        # Persist updated mapping
        self._save_mapping(sid, new_mapping)

        return TokenizerResult(
            tokenized_text=result,
            session_id=sid,
            mapping=new_mapping,
            entities=entities,
        )

    def detokenize(self, tokenized_text: str, session_id: str) -> str:
        """Reverse tokenization using the stored mapping.

        Args:
            tokenized_text: Text containing [TYPE_hex] tokens.
            session_id: Session UUID whose mapping to use.

        Returns:
            Text with tokens replaced by original values.

        Raises:
            KeyError: If session mapping not found in vault.
        """
        mapping = self._load_mapping(session_id)
        if mapping is None:
            raise KeyError(f"No token mapping found for session '{session_id}'")

        result = tokenized_text
        for token, original in mapping.items():
            result = result.replace(token, original)
        return result

    # ── Private helpers ──────────────────────────────────────────

    def _vault_key(self, session_id: str) -> str:
        return f"{_VAULT_KEY_PREFIX}{session_id}"

    def _load_mapping(self, session_id: str) -> dict[str, str] | None:
        """Load and decrypt mapping from vault.

        Returns:
            dict — mapping (possibly empty) if session exists.
            None — if session/vault key does not exist.
        """
        if not self._vault.is_available:
            logger.warning("[tokenizer] vault unavailable — mapping not persisted")
            return None
        try:
            raw = self._vault.get_secret(self._vault_key(session_id))
            if raw is None:
                return None
            return json.loads(raw)  # type: ignore[no-any-return]
        except (VaultUnavailable, json.JSONDecodeError, Exception) as exc:
            logger.error("[tokenizer] failed to load mapping for session %s: %s", session_id, exc)
            return None

    def _save_mapping(self, session_id: str, mapping: dict[str, str]) -> None:
        """Encrypt and persist mapping to vault."""
        if not self._vault.is_available:
            logger.warning("[tokenizer] vault unavailable — mapping not persisted")
            return
        try:
            self._vault.store_secret(self._vault_key(session_id), json.dumps(mapping))
        except (VaultUnavailable, Exception) as exc:
            logger.error("[tokenizer] failed to save mapping for session %s: %s", session_id, exc)
