# GuardForge

> Local PII redaction & tokenization for LLM pipelines — GDPR/HIPAA/PCI-DSS, 17 entity types, self-hosted, no signup

[![Status](https://img.shields.io/badge/status-production_ready-green)]()
[![Languages](https://img.shields.io/badge/UI-15_languages-blue)]()
[![Tests](https://img.shields.io/badge/tests-79_passing-brightgreen)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)]()

---

## Quick Start (3 commands)

```bash
git clone https://github.com/MAXIAWORLD/guardforge.git
cd guardforge
cp backend/.env.example backend/.env
docker compose up
```

→ Dashboard: http://localhost:3003
→ API: http://localhost:8004
→ API docs: http://localhost:8004/docs (dev mode only — requires `DEBUG=true`)

---

## What it does

Every team shipping AI features has a compliance time bomb: **user data going to OpenAI/Anthropic without redaction**. GDPR fines reach 4% of revenue. HIPAA fines reach $50k per incident.

**GuardForge solves it in one drop-in line of code.**

```python
# Before
from openai import OpenAI

# After
from guardforge import OpenAI    # Same API, automatic PII redaction + restoration
```

PII never leaves your infrastructure. Real values are restored after the LLM responds, so your chatbot still says "Hi John" — but OpenAI never sees "John".

### Key features

| Feature | Status |
|---|---|
| **17 PII entity types** (email, phone, SSN US/FR, IBAN, credit card, SIRET, RIB, Steuer-ID, DNI/NIE, Codice Fiscale, passport, person names, etc.) | ✅ |
| **Reversible tokenization** — replace PII with stable tokens, restore real values from encrypted vault | ✅ |
| **5 anonymization strategies** — redact, mask, hash, tokenize, dry-run | ✅ |
| **Risk scoring** per entity (critical / high / medium / low) + overall scan risk | ✅ |
| **6 built-in policies** — strict, moderate, permissive, GDPR, HIPAA, PCI-DSS | ✅ |
| **Compliance reports** — JSON + PDF export by date range, top entities, action distribution | ✅ |
| **Persistent audit log** — every scan logged in DB, exportable for auditors | ✅ |
| **15-language dashboard** — EN, FR, DE, ES, IT, PT, NL, PL, RU, TR, AR, HI, JA, KO, ZH | ✅ |
| **Vault** — AES-256 (Fernet) encrypted secrets, survives restarts | ✅ |
| **Custom entities** — define your own regex patterns | 🟡 in progress |
| **Webhook alerts** for high-risk scans | 🟡 in progress |
| **Drop-in Python SDK** for OpenAI/Anthropic | 🟡 in progress |

---

## Configuration

### Backend `backend/.env`

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | _(required)_ | Used as `X-API-Key` for authenticated endpoints. Must be ≥16 chars. |
| `DEBUG` | `false` | Enables verbose logs and `/docs`. **Disable in production.** |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/guardforge.db` | SQLite for local. PostgreSQL: `postgresql+asyncpg://...` (vault falls back to in-memory). |
| `CORS_ORIGINS` | `["http://localhost:3003"]` | JSON array of allowed origins for the dashboard. |
| `VAULT_ENCRYPTION_KEY` | _(empty → **error in prod**)_ | **CRITICAL**: Fernet base64 key. Required when `DEBUG=false`. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Comma-separated for key rotation. |
| `PII_CONFIDENCE_THRESHOLD` | `0.7` | Minimum confidence to report an entity. |
| `PII_LANGUAGES` | `["en","fr"]` | Languages to apply heuristic detection. |
| `DEFAULT_POLICY` | `strict` | Default policy when none specified per scan. |

### Dashboard environment

The dashboard reads `NEXT_PUBLIC_API_URL` from docker-compose (`http://localhost:8004` by default). For custom setups, edit the `environment` section in `docker-compose.yml`.

---

## API reference

Swagger UI at `http://localhost:8004/docs` (requires `DEBUG=true` in `.env`).

### Core endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/scan` | Detect + anonymize PII in text. Returns entities, risk levels, anonymized text, policy decision. |
| `POST` | `/api/tokenize` | Replace PII with reversible tokens, store mapping in encrypted vault. Returns `session_id`. |
| `POST` | `/api/detokenize` | Reverse tokens back to original values using `session_id`. |
| `POST` | `/api/llm/wrap` | Strip PII for LLM, return safe text + metadata. |
| `GET` | `/api/policies` | List all available policies. |
| `GET` | `/api/audit?limit=50` | Get persisted scan history with risk levels and timestamps. |
| `GET` | `/api/reports/summary?from_date=&to_date=` | Compliance summary: total scans, PII by type, action distribution, risk distribution. |
| `GET` | `/api/reports/timeline?granularity=day\|hour` | Time-series of scans for charts. |

### Vault endpoints (Bearer auth)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/vault/store` | Encrypt and store a secret. |
| `GET` | `/api/vault/get/{key}` | Decrypt a secret. |
| `DELETE` | `/api/vault/delete/{key}` | Remove a secret. |
| `GET` | `/api/vault/keys` | List stored secret keys (no values). |

### Example: tokenize → call OpenAI → restore

```bash
# 1. Tokenize
RESPONSE=$(curl -s -X POST http://localhost:8004/api/tokenize \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hi, I am Jean Dupont, my IBAN is FR7630006000011234567890189"}')

SESSION=$(echo $RESPONSE | jq -r '.session_id')
SAFE_TEXT=$(echo $RESPONSE | jq -r '.tokenized_text')
# SAFE_TEXT = "Hi, I am [PERSON_NAME_a3f2], my IBAN is [IBAN_b491]"

# 2. Send the safe text to OpenAI (no PII leaks)
LLM_REPLY=$(call_openai "$SAFE_TEXT")

# 3. Restore real values for your user
curl -s -X POST http://localhost:8004/api/detokenize \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"$LLM_REPLY\", \"session_id\": \"$SESSION\"}"
```

---

## Dashboard

7 pages, neon design, dark/light mode, 15 languages.

| Page | URL | Purpose |
|---|---|---|
| **Overview** | `/` | Stats overview, risk distribution, quick navigation |
| **Scanner** | `/scanner` | Live PII scanner with strategy selector and risk badges |
| **Policies** | `/policies` | Browse and inspect compliance policies |
| **Audit log** | `/audit` | Persistent scan history with filters and pagination |
| **Vault** | `/vault` | Encrypted secret store management |
| **Playground** | `/playground` | Live tokenize → restore demo |
| **Reports** | `/reports` | Compliance reports with date range, charts, JSON export |

---

## Compliance support

| Region | Regulation | Status |
|---|---|---|
| EU | **GDPR** | ✅ Full preset |
| EU | **EU AI Act** | 🟡 Coming |
| US | **HIPAA** | ✅ Full preset |
| Worldwide | **PCI-DSS v4** | ✅ Full preset |
| California | **CCPA / CPRA** | 🟡 Coming |
| Brazil | **LGPD** | 🟡 Coming |

---

## Architecture

```
guardforge/
├── backend/              # FastAPI + Pydantic V2 + SQLAlchemy async
│   ├── main.py
│   ├── core/             # Config, DB, models, middleware
│   ├── services/         # PII detector, vault, policy engine, tokenizer
│   ├── routes/           # API endpoints (scanner, reports)
│   └── tests/            # 79 pytest tests
├── dashboard/            # Next.js 16 + Tailwind 4 + shadcn/ui + next-intl
│   ├── src/app/          # 7 pages, App Router
│   ├── src/components/   # Shared UI
│   └── src/messages/     # 15 locale files
├── sdk/python/           # Drop-in OpenAI/Anthropic wrappers
└── docker-compose.yml
```

**Tech stack**: Python 3.12 · FastAPI · Pydantic V2 · SQLAlchemy 2 async · aiosqlite · cryptography (Fernet) · Next.js 16 · React 19 · TypeScript strict · Tailwind 4 · shadcn/ui · next-intl

---

## Troubleshooting

**`pydantic.errors.PydanticUserError: Field "secret_key" is required`**
Set `SECRET_KEY` in `backend/.env` (min 16 chars).

**`RuntimeError: VAULT_ENCRYPTION_KEY must be set in production`**
Set `DEBUG=true` for local dev, or generate a key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

**Dashboard shows "Unauthorized"**
`NEXT_PUBLIC_API_KEY` in `dashboard/.env.local` must match `SECRET_KEY` in `backend/.env`. Restart containers after change.

**Detokenize returns 404 after restart**
`VAULT_ENCRYPTION_KEY` is empty (auto-generated each restart in dev mode). Set a fixed key in `backend/.env`.

**CORS errors in browser**
Add your origin to `CORS_ORIGINS` in `backend/.env`: `CORS_ORIGINS=["http://localhost:3003"]`.

**High false positives on SIREN (9-digit numbers)**
SIREN is disabled by default. It can be re-enabled via `enabled_patterns={"siren_fr"}` in the PIIDetector constructor or by raising `PII_CONFIDENCE_THRESHOLD` to 0.8+.

---

## License

Apache 2.0 — see [LICENSE](LICENSE)

---

**Built by [MAXIA Lab](https://maxiaworld.app).** Part of the [Forge Suite](https://maxiaworld.app) — developer tools for AI-era teams.
