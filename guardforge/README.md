# GuardForge

**PII & AI Safety Kit** -- Detect, anonymise, and protect sensitive data. Vault encryption. Policy engine with industry presets.

Part of the [Forge Suite](https://maxialab.com) by MAXIA Lab.

## Features

- **PII Detection** -- Email, phone, SSN (US/FR), IBAN, credit card (Luhn validated), IP addresses
- **3 Anonymisation Strategies** -- Redact (`[EMAIL]`), Mask (`***`), Hash (`[hash:a1b2c3]`)
- **AES-256 Vault** -- Fernet encryption with key rotation support
- **YAML Policy Engine** -- Industry presets: GDPR, HIPAA, PCI-DSS, strict, moderate, permissive
- **LLM Wrapper** -- Strip PII before sending to any LLM, restore after

## Quick Start

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --port 8004 --reload
```

## API

```bash
# Scan text for PII
curl -X POST http://localhost:8004/api/scan \
  -d '{"text": "Contact john@example.com or call +33 6 12 34 56 78", "policy": "gdpr"}'

# LLM-safe wrapper
curl -X POST http://localhost:8004/api/llm/wrap \
  -d '{"text": "Send invoice to john@example.com SSN 123-45-6789"}'
# Returns: {"safe_text": "Send invoice to [EMAIL] SSN [SSN_US]", "pii_stripped": 2}

# Vault
curl -X POST http://localhost:8004/api/vault/store -d '{"key": "api_key", "value": "sk-secret"}'
curl http://localhost:8004/api/vault/get/api_key
```

## Tech Stack

Python 3.12, FastAPI, cryptography (Fernet). 27 tests. Proprietary license.
