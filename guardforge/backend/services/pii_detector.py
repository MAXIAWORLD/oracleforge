"""GuardForge — PII Detection & Anonymisation.

Extracted from MAXIA V12 core/pii_shield.py and enhanced:
- Class-based (no module globals)
- Configurable patterns + languages
- Returns structured entities (type, position, confidence)
- Multiple anonymisation strategies (redact, mask, hash)
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


# ── Pre-compiled patterns ────────────────────────────────────────

_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.IGNORECASE),
    "phone_international": re.compile(r"\+\d{1,3}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{2,4}[\s.-]?\d{2,4}"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "ssn_us": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "ssn_fr": re.compile(r"\b[12]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{2}\b"),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b"),
    "ipv4": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    "date_of_birth": re.compile(r"\b\d{2}/\d{2}/\d{4}\b"),
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


class PIIDetector:
    """Detect and anonymise PII in text."""

    def __init__(self, confidence_threshold: float = 0.7) -> None:
        self._threshold = confidence_threshold

    def detect(self, text: str) -> list[PIIEntity]:
        """Scan text and return all PII entities above confidence threshold."""
        entities: list[PIIEntity] = []
        for pii_type, pattern in _PATTERNS.items():
            confidence = _CONFIDENCE.get(pii_type, 0.8)
            if confidence < self._threshold:
                continue
            for match in pattern.finditer(text):
                value = match.group()
                # Extra validation for credit cards
                if pii_type == "credit_card":
                    clean = re.sub(r"[^0-9]", "", value)
                    if not _luhn_check(clean):
                        continue
                entities.append(PIIEntity(
                    type=pii_type,
                    value=value,
                    start=match.start(),
                    end=match.end(),
                    confidence=confidence,
                ))
        entities.sort(key=lambda e: e.start)
        return entities

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
            result = result[:entity.start] + replacement + result[entity.end:]
        return result

    def scan_and_anonymize(self, text: str, strategy: str = "redact") -> dict:
        """Detect + anonymise in one call. Returns structured result."""
        entities = self.detect(text)
        anonymized = self.anonymize(text, strategy=strategy, entities=entities)
        return {
            "original_length": len(text),
            "pii_count": len(entities),
            "pii_types": list({e.type for e in entities}),
            "entities": [
                {"type": e.type, "value": e.value, "start": e.start, "end": e.end, "confidence": e.confidence}
                for e in entities
            ],
            "anonymized_text": anonymized,
        }
