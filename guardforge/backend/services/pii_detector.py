"""GuardForge — PII Detection & Anonymisation.

Extracted from MAXIA V12 core/pii_shield.py and enhanced:
- Class-based (no module globals)
- Configurable patterns + languages
- Returns structured entities (type, position, confidence, risk_level)
- Multiple anonymisation strategies (redact, mask, hash)
- Extended EU entity coverage (FR, DE, ES, IT)
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PIIEntity:
    type: str
    value: str
    start: int
    end: int
    confidence: float
    risk_level: str = "medium"


# ── Risk levels per entity type ──────────────────────────────────

RISK_LEVELS: dict[str, str] = {
    "credit_card": "critical",
    "ssn_us": "critical",
    "ssn_fr": "critical",
    "iban": "critical",
    "rib_fr": "critical",
    "codice_fiscale_it": "critical",
    "passport_generic": "high",
    "dni_es": "high",
    "nie_es": "high",
    "steuer_id_de": "high",
    "siret_fr": "high",
    "date_of_birth": "high",
    "siren_fr": "medium",
    "person_name": "medium",
    "email": "medium",
    "phone_international": "medium",
    "ipv4": "low",
}

# Risk level ordering for computing overall risk
_RISK_ORDER: dict[str, int] = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def compute_overall_risk(risk_levels: list[str]) -> str:
    """Return the highest risk level from a list, or 'none' if empty."""
    if not risk_levels:
        return "none"
    return max(risk_levels, key=lambda r: _RISK_ORDER.get(r, 0))


def compute_risk_distribution(risk_levels: list[str]) -> dict[str, int]:
    """Count occurrences per risk level."""
    distribution: dict[str, int] = {}
    for level in risk_levels:
        distribution[level] = distribution.get(level, 0) + 1
    return distribution


# ── Patterns disabled by default (high false-positive rate) ─────
# These can be re-enabled via custom policy / custom patterns.
# siren_fr: any 9-digit number matches (e.g. phone suffixes, zip+4, invoice IDs)
_DISABLED_PATTERNS: frozenset[str] = frozenset({"siren_fr"})

# ── Pre-compiled patterns ────────────────────────────────────────

_PATTERNS: dict[str, re.Pattern[str]] = {
    # Existing entities
    "email": re.compile(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.IGNORECASE
    ),
    "phone_international": re.compile(
        r"\+\d{1,3}[\s.-]?\(?\d{1,4}\)?(?:[\s.-]?\d{2,4}){1,5}"
    ),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "ssn_us": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "ssn_fr": re.compile(r"\b[12]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{2}\b"),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b"),
    "ipv4": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    "date_of_birth": re.compile(r"\b\d{2}/\d{2}/\d{4}\b"),
    # French entities
    "siret_fr": re.compile(r"\b(?:\d{3}\s?){2}\d{3}\s?\d{5}\b"),
    "siren_fr": re.compile(r"\b\d{3}\s?\d{3}\s?\d{3}\b"),
    "rib_fr": re.compile(
        r"\b\d{5}\s?\d{5}\s?[A-Z0-9]{11}\s?\d{2}\b",
        re.IGNORECASE,
    ),
    # German entity
    "steuer_id_de": re.compile(r"\b\d{11}\b"),
    # Spanish entities
    "dni_es": re.compile(r"\b\d{8}[A-HJ-NP-TV-Z]\b"),
    "nie_es": re.compile(r"\b[XYZ]\d{7}[A-HJ-NP-TV-Z]\b"),
    # Italian entity
    "codice_fiscale_it": re.compile(
        r"\b[A-Z]{6}\d{2}[A-EHLMPRST]\d{2}[A-Z]\d{3}[A-Z]\b",
        re.IGNORECASE,
    ),
    # Generic passport
    "passport_generic": re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"),
    # Person names (title + capitalized name)
    "person_name": re.compile(
        r"\b(?:M\.|Mme|Mlle|Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?|Sr\.?|Sra\.?|Herr|Frau|"
        r"Monsieur|Madame|Mademoiselle)\s+[A-ZÀ-Ý][a-zà-ÿ]+(?:\s+[A-ZÀ-Ý][a-zà-ÿ]+)*\b",
    ),
}

# Confidence scores per pattern type
_CONFIDENCE: dict[str, float] = {
    "email": 0.95,
    "phone_international": 0.85,
    "credit_card": 0.90,
    "ssn_us": 0.95,
    "ssn_fr": 0.90,
    "iban": 0.92,
    "ipv4": 0.70,
    "date_of_birth": 0.60,
    "siret_fr": 0.92,
    "siren_fr": 0.75,
    "rib_fr": 0.90,
    "steuer_id_de": 0.70,
    "dni_es": 0.92,
    "nie_es": 0.92,
    "codice_fiscale_it": 0.95,
    "passport_generic": 0.65,
    "person_name": 0.80,
}


def _luhn_check(number: str) -> bool:
    """Validate credit card number with Luhn algorithm."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _deduplicate_overlapping(entities: list[PIIEntity]) -> list[PIIEntity]:
    """Remove overlapping entities, keeping the highest priority one.

    Priority: highest confidence first; on tie, longest span first.
    Two entities overlap when their [start, end) ranges intersect.
    Returns a new list sorted by start position.
    """
    if not entities:
        return entities
    sorted_entities = sorted(
        entities,
        key=lambda e: (-e.confidence, -(e.end - e.start), e.start),
    )
    kept: list[PIIEntity] = []
    for entity in sorted_entities:
        overlaps = any(entity.start < k.end and entity.end > k.start for k in kept)
        if not overlaps:
            kept.append(entity)
    kept.sort(key=lambda e: e.start)
    return kept


@dataclass(frozen=True)
class CustomPattern:
    """User-defined PII pattern with metadata."""

    name: str
    regex: re.Pattern[str]
    risk_level: str = "medium"
    confidence: float = 0.85


class PIIDetector:
    """Detect and anonymise PII in text.

    Supports both built-in patterns (17 entity types) and custom user-defined
    patterns added at runtime via add_custom_pattern() / set_custom_patterns().
    """

    def __init__(
        self,
        confidence_threshold: float = 0.7,
        enabled_patterns: set[str] | None = None,
    ) -> None:
        self._threshold = confidence_threshold
        self._custom: list[CustomPattern] = []
        # Patterns explicitly enabled even if in _DISABLED_PATTERNS.
        # Pass e.g. enabled_patterns={"siren_fr"} to re-enable.
        self._enabled_patterns: set[str] = enabled_patterns or set()

    def set_custom_patterns(self, patterns: list[CustomPattern]) -> None:
        """Replace all custom patterns. Used at startup to load from DB."""
        self._custom = list(patterns)

    def add_custom_pattern(self, pattern: CustomPattern) -> None:
        """Add or update a single custom pattern by name."""
        self._custom = [p for p in self._custom if p.name != pattern.name]
        self._custom.append(pattern)

    def remove_custom_pattern(self, name: str) -> bool:
        """Remove a custom pattern by name. Returns True if existed."""
        before = len(self._custom)
        self._custom = [p for p in self._custom if p.name != name]
        return len(self._custom) < before

    def list_custom_patterns(self) -> list[CustomPattern]:
        return list(self._custom)

    def detect(self, text: str) -> list[PIIEntity]:
        """Scan text and return all PII entities above confidence threshold."""
        entities: list[PIIEntity] = []
        for pii_type, pattern in _PATTERNS.items():
            # Skip patterns disabled by default unless explicitly re-enabled
            if (
                pii_type in _DISABLED_PATTERNS
                and pii_type not in self._enabled_patterns
            ):
                continue
            confidence = _CONFIDENCE.get(pii_type, 0.8)
            if confidence < self._threshold:
                continue
            for match in pattern.finditer(text):
                value = match.group()
                if pii_type == "credit_card":
                    clean = re.sub(r"[^0-9]", "", value)
                    if not _luhn_check(clean):
                        continue
                risk_level = RISK_LEVELS.get(pii_type, "medium")
                entities.append(
                    PIIEntity(
                        type=pii_type,
                        value=value,
                        start=match.start(),
                        end=match.end(),
                        confidence=confidence,
                        risk_level=risk_level,
                    )
                )

        # Custom user-defined patterns
        for cp in self._custom:
            if cp.confidence < self._threshold:
                continue
            for match in cp.regex.finditer(text):
                entities.append(
                    PIIEntity(
                        type=cp.name,
                        value=match.group(),
                        start=match.start(),
                        end=match.end(),
                        confidence=cp.confidence,
                        risk_level=cp.risk_level,
                    )
                )

        return _deduplicate_overlapping(entities)

    def anonymize(
        self,
        text: str,
        strategy: str = "redact",
        entities: list[PIIEntity] | None = None,
    ) -> str:
        """Anonymise PII in text.

        Strategies:
          - redact: replace with [PII_TYPE]
          - mask: replace with ***
          - hash: replace with sha256 hash prefix
        """
        if entities is None:
            entities = self.detect(text)
        if not entities:
            return text

        # Process from end to start to preserve positions
        result = text
        for entity in reversed(entities):
            if strategy == "redact":
                replacement = f"[{entity.type.upper()}]"
            elif strategy == "mask":
                replacement = "***"
            elif strategy == "hash":
                h = hashlib.sha256(entity.value.encode()).hexdigest()[:8]
                replacement = f"[hash:{h}]"
            else:
                replacement = f"[{entity.type.upper()}]"
            result = result[: entity.start] + replacement + result[entity.end :]
        return result

    def scan_and_anonymize(self, text: str, strategy: str = "redact") -> dict:
        """Detect + anonymise in one call. Returns structured result."""
        entities = self.detect(text)
        anonymized = self.anonymize(text, strategy=strategy, entities=entities)
        risk_levels = [e.risk_level for e in entities]
        return {
            "original_length": len(text),
            "pii_count": len(entities),
            "pii_types": list({e.type for e in entities}),
            "entities": [
                {
                    "type": e.type,
                    "value": e.value,
                    "start": e.start,
                    "end": e.end,
                    "confidence": e.confidence,
                    "risk_level": e.risk_level,
                }
                for e in entities
            ],
            "anonymized_text": anonymized,
            "overall_risk": compute_overall_risk(risk_levels),
            "risk_distribution": compute_risk_distribution(risk_levels),
        }
