# GuardForge Security Whitepaper

**Version:** 1.0
**Last updated:** 2026
**Audience:** CISOs, DPOs, security architects evaluating GuardForge for production use.

---

## Executive summary

GuardForge is a PII detection and tokenization service designed to prevent personally identifiable information from leaking to third-party LLM providers. It is built with security and compliance as first-class concerns, supporting GDPR, EU AI Act, HIPAA, PCI-DSS, and 9 other major regulations.

This whitepaper describes the technical and organizational security measures implemented by MAXIA Lab to protect customer data when using GuardForge.

---

## 1. Architecture overview

GuardForge consists of two main components:

- **Backend API** (FastAPI / Python 3.12) — Detection, anonymization, tokenization, vault, policy engine, audit log
- **Dashboard** (Next.js 16 / React 19) — Administrative UI, compliance reports, vault management

Both components communicate over HTTPS in production. The backend persists data in a relational database (SQLite for development, PostgreSQL recommended for production at scale).

### Deployment models

| Model | Data residency | Operator |
|---|---|---|
| **Cloud Edition** | EU (Frankfurt, Paris) by default | MAXIA Lab |
| **Self-Hosted Edition** | Customer-controlled (anywhere in the world) | Customer |

---

## 2. Data flows

### 2.1 Scan operation
1. Client sends `POST /api/scan` with text payload over HTTPS.
2. API validates the API key (X-API-Key header).
3. PII detector identifies entities using regex patterns.
4. Policy engine evaluates the scan against the requested policy.
5. Anonymized text is returned to the client.
6. Audit log entry is persisted (input is hashed SHA-256, never stored in plaintext).

### 2.2 Tokenize operation
1. Client sends `POST /api/tokenize` with text payload.
2. PII is replaced with deterministic tokens of form `[ENTITY_TYPE_xxxx]`.
3. The mapping `{token: original_value}` is encrypted (AES-256 Fernet) and stored in the vault under `tokenmap:<session_id>`.
4. Tokenized text and session_id are returned.
5. Audit log entry is persisted.

### 2.3 Detokenize operation
1. Client sends `POST /api/detokenize` with tokenized text and session_id.
2. The encrypted mapping is fetched from the vault and decrypted.
3. Tokens are replaced with original values.
4. Original text is returned. The mapping is NOT logged.

---

## 3. Cryptography

### 3.1 Encryption at rest

- **Vault**: AES-256-CBC with HMAC-SHA256 authentication (Fernet, from the `cryptography` library). Each secret is encrypted with the master key configured via `VAULT_ENCRYPTION_KEY`.
- **Key rotation**: Multiple keys can be configured (comma-separated). Decryption tries each key in order. New writes use the first key.
- **Database**: SQLite database files should be stored on encrypted filesystems in production (LUKS, BitLocker, FileVault, EBS encryption). PostgreSQL deployments should use TDE (Transparent Data Encryption).

### 3.2 Encryption in transit

- TLS 1.2+ enforced for all API and dashboard traffic in production
- HTTP Strict Transport Security (HSTS) headers
- TLS termination at the reverse proxy (nginx, Caddy, or cloud load balancer)
- For Cloud Edition: Let's Encrypt managed certificates with auto-renewal

### 3.3 Key management

- Master vault encryption keys are stored in environment variables (`VAULT_ENCRYPTION_KEY`)
- For production, customers should use a secrets manager (AWS Secrets Manager, HashiCorp Vault, Azure Key Vault) and inject the key at container startup
- Keys must be base64-encoded 32-byte Fernet keys
- Key rotation is supported via comma-separated keys

---

## 4. Authentication and authorization

### 4.1 API authentication

- All non-public endpoints require an `X-API-Key` header matching the backend `SECRET_KEY`
- Vault endpoints additionally accept `Authorization: Bearer <token>` for backward compatibility
- API keys are checked at the middleware layer, before any business logic
- Failed authentication returns `401 Unauthorized` with no information leakage

### 4.2 Public endpoints

The following endpoints are intentionally public (no auth required):
- `GET /health` — Liveness probe for load balancers and uptime monitors
- `GET /docs` — Swagger UI (production deployments should restrict this)
- `GET /openapi.json` — OpenAPI schema (production deployments should restrict this)

### 4.3 Multi-user RBAC

Multi-user role-based access control is on the roadmap for the Enterprise tier. Day-1, the Service operates with a single API key.

---

## 5. Network security

### 5.1 Rate limiting

- 60 requests per minute per IP by default (configurable)
- Sliding-window algorithm
- Returns `429 Too Many Requests` when exceeded
- For production, customers should additionally deploy a Web Application Firewall (WAF) or use Cloudflare/AWS Shield for DDoS protection

### 5.2 CORS

- CORS origins are explicitly whitelisted in `CORS_ORIGINS` environment variable
- Wildcard origins (`*`) are not used by default
- Preflight requests are handled

### 5.3 Security headers

The backend sets the following security headers on all responses:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`

For production, customers should additionally configure at the reverse proxy:
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy: ...`
- `Permissions-Policy: ...`

---

## 6. Audit logging

### 6.1 What is logged

For every scan and tokenize operation:
- Timestamp (UTC)
- Input hash (SHA-256, first 16 chars) — **the raw text is never stored**
- PII count detected
- PII types detected (e.g., `["email", "credit_card"]`)
- Policy applied
- Action taken (block / anonymize / warn / tokenize)
- Risk level (critical / high / medium / low)

### 6.2 What is NOT logged

- The original text (only its hash)
- The values of detected PII entities
- Tokenization mapping contents
- Vault secret values

### 6.3 Retention

- Cloud Edition Free / Starter: 30 days
- Cloud Edition Pro: 1 year
- Cloud Edition Business / Enterprise: unlimited
- Self-Hosted Edition: customer-controlled

### 6.4 Export

Audit logs can be exported via `GET /api/audit?limit=500` and `/api/reports/summary`. Enterprise tier supports SIEM forwarding (Splunk, Datadog, Elastic) — on the roadmap.

---

## 7. Vulnerability management

- **Dependency scanning**: Regular `pip-audit` and `npm audit` runs
- **Static analysis**: `bandit` for Python security issues
- **Code review**: All changes reviewed before merge
- **Penetration testing**: Annual external pentest (planned post-launch)
- **Security advisories**: Subscribed to Python and Node.js security mailing lists
- **Patch management**: Critical security patches applied within 7 days

---

## 8. Incident response

In the event of a security incident or Personal Data Breach:

1. **Detection** (≤ 4 hours): Monitoring and alerting trigger an incident.
2. **Triage** (≤ 8 hours): Severity assessment by on-call team.
3. **Containment** (≤ 24 hours): Affected systems isolated, vulnerabilities patched.
4. **Notification** (≤ 72 hours): Affected customers notified per DPA Article 9.
5. **Remediation**: Root cause analysis, fix deployment, post-mortem.
6. **Communication**: Public disclosure if required by law or affecting many customers.

---

## 9. Data minimization

GuardForge follows the principle of data minimization:

- **Raw text is never persisted** — only SHA-256 hashes of inputs
- **PII values are not logged** — only entity types and counts
- **Vault secrets are encrypted** — plaintext only exists in memory during decryption
- **Tokenization mappings are session-scoped** — can be deleted via `DELETE /api/vault/delete/{key}`

---

## 10. Compliance frameworks

GuardForge ships built-in policy presets for:

| Region | Regulation | Tier |
|---|---|---|
| EU | GDPR (RGPD) | Tier 1 — Full mapping |
| EU | EU AI Act | Tier 1 — Full mapping |
| US Federal | HIPAA | Tier 1 — Full mapping |
| Worldwide | PCI-DSS v4 | Tier 1 — Full mapping |
| US California | CCPA / CPRA | Tier 1 — Full mapping |
| Brazil | LGPD | Tier 1 — Full mapping |
| Canada | PIPEDA | Tier 2 — GDPR baseline |
| Japan | APPI | Tier 2 — GDPR baseline |
| Singapore | PDPA | Tier 2 — GDPR baseline |
| South Africa | POPIA | Tier 2 — GDPR baseline |
| India | DPDP Act 2023 | Tier 2 — GDPR baseline |
| China | PIPL | Tier 2 — GDPR baseline (block-by-default) |
| Australia | Privacy Act 1988 | Tier 2 — GDPR baseline |

GuardForge is **not** a substitute for a complete compliance program. Customers remain responsible for their own data protection obligations.

---

## 11. Certifications and audits

| Item | Status |
|---|---|
| GDPR Article 28 DPA | ✅ Available (`docs/legal/DPA.md`) |
| Sub-processor list | ✅ Available (`docs/legal/SUB_PROCESSORS.md`) |
| SOC 2 Type 1 | 🟡 Planned for 2026 H2 |
| SOC 2 Type 2 | 🟡 Planned for 2027 H1 |
| ISO 27001 | 🔴 Not planned day-1 |

---

## 12. Contact

For security concerns, vulnerability reports, or compliance inquiries:

**Email**: security@maxialab.com _(coming soon — use contact@maxialab.com in the meantime)_
**PGP key**: Will be published on launch.

We follow responsible disclosure practices and aim to acknowledge security reports within 48 hours.

---

*This whitepaper is provided as-is for informational purposes and does not constitute a legally binding warranty. The specific security guarantees applicable to your deployment are governed by your License Agreement and DPA.*
