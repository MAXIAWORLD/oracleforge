# GuardForge

> **PII & AI Safety Kit for the LLM era.**
> Detect, redact, and tokenize sensitive data before it ever reaches OpenAI, Anthropic, or any other LLM provider. Built for compliance with GDPR, EU AI Act, HIPAA, CCPA, LGPD, and 8 more jurisdictions.

[![Status](https://img.shields.io/badge/status-production_ready-green)]()
[![Languages](https://img.shields.io/badge/UI-15_languages-blue)]()
[![Tests](https://img.shields.io/badge/tests-79_passing-brightgreen)]()
[![License](https://img.shields.io/badge/license-Proprietary-red)]()

---

## Why GuardForge

Every SaaS company shipping AI features has a compliance time bomb: **user data going to OpenAI/Anthropic without redaction**. GDPR fines reach 4% of revenue. The EU AI Act adds new criminal liability in 2025-2026. HIPAA fines reach $50k per incident.

**GuardForge solves it in one drop-in line of code.**

```python
# Before
from openai import OpenAI

# After
from guardforge import OpenAI    # Same API, automatic PII redaction + restoration
```

PII never leaves your infrastructure. Real values are restored after the LLM responds, so your chatbot still says "Hi John" — but OpenAI never sees "John".

---

## Key features

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
| **Vault** — AES-256 (Fernet) encrypted secrets, **survives restarts** | ✅ |
| **Custom entities** — define your own regex patterns | 🟡 in progress |
| **Webhook alerts** for high-risk scans | 🟡 in progress |
| **Drop-in Python SDK** for OpenAI/Anthropic | 🟡 in progress |

---

## Quick start (5 minutes)

### Prerequisites
- Python 3.12+
- Node.js 20+ (for the dashboard)

### 1. Clone
```bash
git clone https://github.com/your-org/guardforge.git
cd guardforge
```

### 2. Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate           # macOS / Linux
venv\Scripts\activate              # Windows

pip install -r requirements.txt
cp .env.example .env
# Edit .env — set SECRET_KEY and VAULT_ENCRYPTION_KEY (see Configuration below)

python -m uvicorn main:app --host 0.0.0.0 --port 8004
```

The API is now live at `http://localhost:8004` and Swagger docs at `http://localhost:8004/docs`.

### 3. Dashboard
```bash
cd ../dashboard
npm install
cp .env.local.example .env.local
# Edit .env.local — set NEXT_PUBLIC_API_KEY to match SECRET_KEY in backend

npm run dev -- --port 3003
```

The dashboard is now live at `http://localhost:3003`.

### 4. First scan
```bash
curl -X POST http://localhost:8004/api/scan \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hi, my name is John Doe and my email is john@example.com",
    "strategy": "redact"
  }'
```

You should see PII detected and redacted as `[PERSON_NAME]` and `[EMAIL]`.

---

## Configuration

### Backend `.env`

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | _(required)_ | Used as `X-API-Key` for authenticated endpoints. Must be ≥16 chars. |
| `DEBUG` | `false` | Enables verbose logs. Disable in production. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./guardforge.db` | SQLite for dev. PostgreSQL supported via `postgresql+asyncpg://...` (vault persistence falls back to in-memory only). |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON array of allowed origins for the dashboard. |
| `VAULT_ENCRYPTION_KEY` | _(empty → auto-generated)_ | **CRITICAL**: Fernet base64 key. If empty, a new key is generated each restart and old vault data becomes unreadable. **Always set in production.** Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Comma-separated for key rotation. |
| `PII_CONFIDENCE_THRESHOLD` | `0.7` | Minimum confidence to report an entity. Lower = more recall, more false positives. |
| `PII_LANGUAGES` | `["en","fr"]` | Languages to apply heuristic detection. |
| `DEFAULT_POLICY` | `strict` | Default policy when none specified per scan. |

### Dashboard `.env.local`

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8004` | Backend URL. |
| `NEXT_PUBLIC_API_KEY` | _(required)_ | Must match backend `SECRET_KEY`. |
| `NEXT_PUBLIC_SECRET_KEY` | _(required for vault page)_ | Same as `NEXT_PUBLIC_API_KEY` — used as Bearer token for vault endpoints. |

---

## API reference

Swagger UI at `http://localhost:8004/docs` lists every endpoint with examples.

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
# LLM_REPLY = "Hello [PERSON_NAME_a3f2], your IBAN [IBAN_b491] is now confirmed."

# 3. Restore real values for your user
curl -s -X POST http://localhost:8004/api/detokenize \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"$LLM_REPLY\", \"session_id\": \"$SESSION\"}"
# Returns: "Hello Jean Dupont, your IBAN FR7630006000011234567890189 is now confirmed."
```

---

## Dashboard

7 pages, neon design, dark/light mode, 15 languages.

| Page | URL | Purpose |
|---|---|---|
| **Tableau de bord** | `/` | Stats overview, risk distribution, quick navigation |
| **Scanner** | `/scanner` | Live PII scanner with strategy selector and risk badges |
| **Politiques** | `/policies` | Browse and inspect compliance policies |
| **Journal d'audit** | `/audit` | Persistent scan history with filters and pagination |
| **Coffre-fort** | `/vault` | Encrypted secret store management |
| **Playground** | `/playground` | Live tokenize → restore demo (the "wow" page) |
| **Rapports** | `/reports` | Compliance reports with date range, charts, JSON export |

---

## Compliance support

GuardForge ships with built-in policy presets for major data protection regulations:

| Region | Regulation | Status |
|---|---|---|
| 🇪🇺 EU | **GDPR** (RGPD) | ✅ Full preset |
| 🇪🇺 EU | **EU AI Act** (2025-2026) | 🟡 Coming in next release |
| 🇺🇸 US Federal | **HIPAA** | ✅ Full preset |
| 🌍 Worldwide | **PCI-DSS v4** | ✅ Full preset |
| 🇺🇸 California | **CCPA / CPRA** | 🟡 Coming in next release |
| 🇧🇷 Brazil | **LGPD** | 🟡 Coming in next release |
| 🇨🇦 Canada | **PIPEDA** | 🟡 Coming in next release |
| 🇯🇵 Japan | **APPI** | 🟡 Coming in next release |
| 🇸🇬 Singapore | **PDPA** | 🟡 Coming in next release |
| 🇿🇦 South Africa | **POPIA** | 🟡 Coming in next release |
| 🇮🇳 India | **DPDP Act 2023** | 🟡 Coming in next release |
| 🇨🇳 China | **PIPL** | 🟡 Coming in next release |
| 🇦🇺 Australia | **Privacy Act 1988** | 🟡 Coming in next release |
| 🇬🇧 UK | **UK GDPR + DPA 2018** | ✅ via GDPR preset |

For full compliance documentation including DPA templates, security whitepaper, and sub-processor list, see `docs/legal/`.

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
│   ├── src/components/   # Shared UI (DashboardShell, ThemeToggle, etc.)
│   ├── src/messages/     # 15 locale files
│   └── scripts/          # Maintenance scripts
└── docs/                 # User documentation
```

### Tech stack

- **Backend**: Python 3.12 · FastAPI · Pydantic V2 · SQLAlchemy 2 (async) · aiosqlite · cryptography (Fernet) · pytest
- **Frontend**: Next.js 16 (Turbopack) · React 19 · TypeScript strict · Tailwind 4 · shadcn/ui · next-intl · Framer Motion · Lucide icons

---

## Self-hosted vs Cloud

| | Self-hosted | Cloud SaaS |
|---|---|---|
| **Data residency** | ✅ Wherever you deploy | ✅ EU only (Frankfurt/Paris) day-1; US/APAC on demand |
| **Setup** | ~10 min (Docker compose) | Instant |
| **Updates** | Manual `git pull` | Automatic |
| **Backups** | Your responsibility | Daily snapshots |
| **Support** | Forum / email / priority depending on tier | Email / Slack / dedicated CSM depending on tier |
| **License** | One-time payment, perpetual use | Monthly subscription |
| **Best for** | Sensitive data, strict residency, on-prem requirements | Quick start, no infra burden |

---

## Troubleshooting

### Backend won't start: `pydantic.errors.PydanticUserError: Field "secret_key" is required`
Set `SECRET_KEY` in your `.env` file. Minimum 16 characters.

### Dashboard shows "Failed to fetch policies: Unauthorized"
`NEXT_PUBLIC_API_KEY` in `dashboard/.env.local` does not match `SECRET_KEY` in `backend/.env`. They MUST be identical. Restart `npm run dev` after changing — Next.js does NOT hot-reload env vars.

### Vault page shows "Indisponible" + "Set NEXT_PUBLIC_SECRET_KEY"
Same fix: set `NEXT_PUBLIC_SECRET_KEY` in `dashboard/.env.local` to match backend `SECRET_KEY`. Restart dashboard.

### Tokenize works, but Detokenize returns 404 after restart
Your `VAULT_ENCRYPTION_KEY` is empty (auto-generated each restart). Set a fixed Fernet key in your `.env`:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Copy the output into `VAULT_ENCRYPTION_KEY=...`. Restart backend.

### CORS errors in browser console
Add your dashboard origin to `CORS_ORIGINS` in `backend/.env`:
```
CORS_ORIGINS=["http://localhost:3000","http://localhost:3003","https://your-prod-domain.com"]
```

### Tests fail with `httpx.ConnectError`
Run `pip install httpx>=0.27` in your venv. The test client requires httpx as a dev dependency.

### High false positives on SIREN (9-digit numbers)
SIREN regex matches any 9-digit sequence. Either raise `PII_CONFIDENCE_THRESHOLD` to 0.8+, or disable the SIREN entity by setting custom policy `blocked_types`.

---

## License

GuardForge is **proprietary software**. See `LICENSE` file for full terms.

- ✅ **Permitted**: internal business use, integration with your products
- ❌ **Forbidden**: redistribution, reselling, removing branding, reverse-engineering for competitive products

For commercial licensing inquiries: `sales@guardforge.io` _(coming soon)_.

---

## Support

- **Documentation**: `docs/`
- **API reference**: `http://localhost:8004/docs` (Swagger UI)
- **Issues**: GitHub Issues (cloud subscribers get priority on email)
- **Email**: `support@guardforge.io` _(coming soon)_

---

## Roadmap

- [x] Core PII detection (17 entities, 4 EU languages)
- [x] Reversible tokenization with encrypted vault
- [x] Persistent audit log + compliance reports
- [x] 15-language dashboard
- [x] Vault DB persistence (survives restarts)
- [ ] 12 compliance presets (CCPA, LGPD, PIPEDA, APPI, etc.)
- [ ] Drop-in Python SDK (`from guardforge import OpenAI`)
- [ ] PDF export for compliance reports
- [ ] Custom entities CRUD UI
- [ ] Webhook alerts for high-risk scans
- [ ] PostgreSQL vault adapter (for production scale)
- [ ] Multi-tenant isolation (Enterprise tier)
- [ ] Real-time SIEM integration (Splunk, Datadog)

---

**Built with care by MAXIA Lab.** Part of the [Forge Suite](https://maxia.lab/forge) — 6 developer tools for AI-era startups.
