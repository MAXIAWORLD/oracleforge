# GuardForge — Known Limitations

**Version:** 0.1.0
**Last updated:** 2026-04-13

This document lists all known limitations of GuardForge in its current release. We publish these openly so buyers can make informed procurement decisions and plan mitigations where relevant.

---

## 1. PII Detection

### 1.1 Regex-based detection only (no ML NER)

GuardForge uses regular expressions and heuristic patterns — **not** a machine-learning named-entity recognition model. This means:

**Strengths:**
- **Zero false positives** on well-formed structured data (measured precision = 1.00 on our validation dataset).
- **Low latency**: p95 <8ms for scan, <12ms for tokenize.
- **Predictable**: given a pattern, you can reason about what matches.
- **No GPU required**, no large model download, no inference costs.

**Trade-offs:**
- **Unstructured person names are missed**: `"John Smith"` without a title (`Mr`, `Dr`, `Mme`, etc.) is not detected. Our person_name regex requires a title prefix.
- **Context is ignored**: `"12345678901"` by itself is ambiguous — could be a Steuer-ID, phone number, or random digits. The regex decides based on length and format only.
- **Domain-specific terms** (medical conditions, product serial numbers, customer IDs) are not detected unless you configure them as custom entities.

**Mitigation**:
- Use the [custom entities CRUD](../backend/routes/entities.py) to add patterns specific to your domain.
- For full-text PII redaction with ML NER, a future release will add optional spaCy integration as a paid enterprise feature.

### 1.2 Confidence threshold filters some entities by default

These entity types have low confidence scores by design (below the default `PII_CONFIDENCE_THRESHOLD=0.7`):

| Entity | Default confidence | Reason |
|---|---|---|
| `ipv4` | 0.70 | Narrowly passes threshold |
| `passport_generic` | 0.65 | Generic pattern (1-2 letters + 6-9 digits) too permissive |
| `date_of_birth` | 0.60 | Dates of birth are indistinguishable from any other date |

**What this means**: by default, these entities are **not detected** because they're more likely to produce false positives than true positives in generic text.

**Mitigation**:
- Lower `PII_CONFIDENCE_THRESHOLD` in backend `.env` to capture these.
- Accept more false positives in return for higher recall.

### 1.3 Potential false positives on SIREN (9-digit numbers)

The `siren_fr` regex matches any 9-digit sequence. Confidence is 0.75 (just above threshold), so it fires. In texts mentioning arbitrary 9-digit numbers (phone extensions, order IDs, etc.), it may produce false positives.

**Mitigation**:
- Raise `PII_CONFIDENCE_THRESHOLD` to 0.80+ to silently drop it.
- Or configure a custom policy that excludes `siren_fr` from `blocked_types`.

### 1.4 Credit card regex accepts 13-16 digits

The Luhn check **is** applied — only numbers with a valid checksum are detected. But this means:
- 14-digit SIRET numbers that happen to pass Luhn (like `73282932000074`) can collide with `credit_card`.
- The [span deduplication logic](../backend/services/pii_detector.py#L144) handles this by keeping the higher-confidence match (SIRET 0.92 > credit_card 0.90).

**Status**: known quirk, dedup logic in place, regression-tested.

### 1.5 Multi-language detection is pattern-based, not language-aware

GuardForge ships patterns for FR, DE, ES, IT, EN jurisdictions but does NOT do language identification first. The patterns run on every input regardless of language. Practical implications:
- A French SIRET pattern applied to English text still works if the format matches.
- A "Mr" vs "M." title applies regardless of surrounding language.
- No accent normalization — "Mme Müller" must match on exact Unicode characters.

**Mitigation**: test your specific content — validation metrics are in `tests/validation_report.md`.

---

## 2. Vault & Persistence

### 2.1 Vault persistence is SQLite-only

The `Vault` class uses a **synchronous sqlite3** write-through cache. For the Cloud Edition or self-hosted deployments using PostgreSQL (`DATABASE_URL=postgresql+asyncpg://...`), the vault silently **falls back to in-memory mode** and secrets are **lost on restart**.

**Status**: design limitation. PostgreSQL vault adapter is on the roadmap.

**Mitigation for now**:
- Use SQLite (default) for single-node deployments.
- If you need PostgreSQL, expect tokenization sessions to be lost on backend restart — either accept this, or run SQLite alongside PostgreSQL for the vault.

### 2.2 Vault encryption key rotation is manual

`VAULT_ENCRYPTION_KEY` supports comma-separated keys (newest first) for rotation, but:
- There's no UI for key rotation.
- There's no automatic re-encryption of existing vault entries with a new key.
- Old entries remain encrypted with the key they were written with.

**Mitigation**: documented manual rotation procedure in `docs/legal/SECURITY_WHITEPAPER.md`.

### 2.3 Vault does not support TTL / expiry

Tokenization session mappings accumulate indefinitely in the vault until manually deleted via `DELETE /api/vault/delete/{key}`. There is no automatic TTL or cleanup job.

**Mitigation**: implement a cron job that deletes `tokenmap:*` keys older than your session retention policy.

---

## 3. LLM SDK Wrappers

### 3.1 Streaming responses (`stream=True`) are not detokenized

Both the OpenAI and Anthropic wrappers bypass detokenization when streaming is enabled. Tokens flow through to your client but are **not restored**.

**Status**: documented in `sdk/python/README.md` and in the wrapper source code.

**Roadmap**: v0.2 will support streaming detokenization via a transparent stream wrapper.

### 3.2 Async clients are not wrapped

`openai.AsyncOpenAI` and `anthropic.AsyncAnthropic` are NOT wrapped by GuardForge yet. Use the sync versions (`OpenAI`, `Anthropic`) for now.

**Roadmap**: v0.2.

### 3.3 Multimodal content passes through untouched

Image, audio, and file content in chat messages are forwarded as-is. Only **string text content** is scanned for PII. If you send an image with embedded PII, it goes to the LLM unredacted.

**Mitigation**: do not rely on GuardForge for image PII. Use a specialized OCR+redaction pipeline for visual content.

### 3.4 Tool call arguments are not scanned

If a user message triggers a function call whose arguments contain PII, the arguments are forwarded to the LLM without tokenization.

**Mitigation**: tokenize the user message upstream — function call arguments are derived from the user's request.

### 3.5 OpenAI system prompts via `chat.completions.create` are not auto-tokenized

The wrapper tokenizes messages in the `messages` list, but if you pass a system message via `messages=[{"role":"system", "content":"..."}, ...]`, that content **IS** tokenized. However, the OpenAI Responses API `instructions=` parameter is not yet hooked.

**Status**: minor edge case. Primary chat flow covers 95% of usage.

---

## 4. Backend Architecture

### 4.1 Rate limiting is per-process, not distributed

The in-memory rate limiter tracks requests per IP in a dict. In a multi-worker or multi-node deployment, rate limits are **per-worker**, not global. A client hitting 3 workers sees 3× the stated limit.

**Mitigation**:
- Use a single-worker deployment for strict rate limiting.
- Or front the backend with a Redis-backed rate limiter (nginx ratelimit, cloudflare, etc.).

**Roadmap**: Redis-backed distributed rate limiter for the Business and Enterprise tiers.

### 4.2 No multi-tenant isolation

The current release is **single-tenant**: all audit logs, custom entities, webhooks, and vault entries share one database. The API key grants full access to the entire dataset.

**Mitigation**: run one backend instance per tenant (self-hosted customers) or wait for the Enterprise multi-tenant release.

**Roadmap**: tenant_id column across all tables + scoped queries, slated for v0.3.

### 4.3 No user management / RBAC

A single API key gates access. No multi-user, no roles, no per-user audit trails of who triggered a scan. This is acceptable for backend-to-backend integration but limits collaboration.

**Mitigation**: use separate API keys per team member via environment variables.

**Roadmap**: full RBAC with SSO integration for the Enterprise tier.

### 4.4 Webhook dispatch is not truly isolated

Webhooks are fired via `asyncio.create_task` from the scan handler. This is fire-and-forget on the same event loop. If a registered webhook points to a dead URL, the httpx connection attempt (~3s timeout) consumes an event loop slot and can add latency to subsequent scans under sustained load.

**Evidence**: our initial benchmark showed p50 jumping from 5ms to 113ms on the scan endpoint when a dead-URL webhook was registered. Deleting the webhook restored p50 to 5ms.

**Mitigation**:
- Use only webhooks that actually respond fast.
- Disable or delete dead webhooks. The `failure_count` column tracks bad webhooks.
- For enterprise deployments, externalize webhook dispatch to a separate worker process.

**Roadmap**: dedicated webhook dispatch worker with durable queue for Business tier.

### 4.5 In-memory custom entity patterns

Custom entities are reloaded from DB into an in-memory list after every create/delete. In a multi-worker deployment, other workers will see stale patterns until their own reload endpoint is called, or they restart.

**Mitigation**: single-worker for now, or call `POST /api/entities/reload` on each worker after a CRUD operation.

### 4.6 `/docs` Swagger UI is not disabled in production

FastAPI's `/docs` endpoint is currently always enabled. In production, you may want to disable it or require authentication.

**Mitigation**: set `FASTAPI_DOCS_URL=` to empty or restrict via reverse proxy. See hardening guide in `SECURITY_WHITEPAPER.md`.

---

## 5. Dashboard

### 5.1 Next.js 16 Turbopack is a breaking release

The dashboard runs on Next.js 16 with Turbopack, which differs from prior Next.js versions in ways not covered by general Next.js tutorials. When modifying the dashboard, always consult `node_modules/next/dist/docs/` before applying patterns from older documentation.

### 5.2 No loading skeletons on tables

Tables show a spinner while loading, not shimmer skeletons. This is cosmetic only — functionality works correctly. Polish item for a future release.

### 5.3 No toast notifications

Success and error feedback uses inline banners that don't auto-dismiss. Clicking another action clears them manually. A proper Toast component is on the roadmap.

### 5.4 Language switching requires full page reload in some cases

The next-intl locale switching occasionally requires a hard refresh to fully apply on pages that cache translation strings in component state. Known issue, not a data-loss bug.

---

## 6. Testing & Validation

### 6.1 No browser automation tests

The E2E tests in `tests/test_e2e.py` are HTTP integration tests — they exercise the full API contract but do not drive a real browser. Visual regression, form submission, and dashboard interaction are not covered by automated tests.

**Mitigation**: we manually test each dashboard page after every release. Playwright-based browser tests are on the roadmap for C-class releases.

### 6.2 Benchmark is timer-limited on Windows

The initial benchmark run showed p50 latencies of 0.0ms due to the 15.6ms resolution of `time.monotonic()` on Windows. The updated benchmark uses `time.perf_counter()` (microsecond resolution) for accurate measurements.

**Impact**: none going forward. Old results in `tests/benchmark_results.md` are from the fixed version.

### 6.3 Validation dataset is small and synthetic

Our PII validation dataset has 31 examples across 5 languages. It's representative but not exhaustive. Real-world data from your domain may expose patterns we haven't tested.

**Mitigation**: add your own validation cases to `tests/pii_validation_dataset.json` and run `python tests/validate_precision_recall.py`.

---

## 7. Operational

### 7.1 SQLite is not recommended for >10k scans/day

SQLite is excellent for dev and small deployments but has write-locking constraints at high concurrency. For production workloads above a few thousand scans per day, switch to PostgreSQL:

```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/guardforge
```

**Caveat**: see §2.1 — vault persistence falls back to in-memory for PostgreSQL.

### 7.2 No built-in backup / restore tooling

Backup the `guardforge.db` file (SQLite) or use standard PostgreSQL dump tools. No GuardForge-specific backup utility exists yet.

### 7.3 Phone-home telemetry for self-hosted (not yet implemented)

The LICENSE document mentions a phone-home component for self-hosted license validation. This is **not yet implemented** in v0.1.0. License enforcement relies on manual distribution for now.

**Roadmap**: v0.2 will add the phone-home component.

---

## 8. Compliance

### 8.1 Tier 2 jurisdictions use GDPR baseline

CCPA (tier 1 now), LGPD (tier 1 now), PIPEDA, APPI, PDPA Singapore, POPIA, DPDP India, PIPL China, Privacy Act Australia — the tier 2 presets all use the GDPR-equivalent PII type list. Jurisdiction-specific entity mappings (e.g., Japanese My Number, Indian Aadhaar) are planned.

### 8.2 GuardForge is a tool, not a compliance program

Using GuardForge does **not** automatically make your application GDPR/HIPAA/CCPA compliant. It provides building blocks — detection, redaction, audit trail, reports. You still need:
- A data protection officer (DPO) or equivalent accountability role.
- Legal agreements (DPA with your customers, sub-processor disclosures).
- Data retention and deletion policies.
- Breach notification procedures.
- Privacy impact assessments for high-risk processing.

See `docs/legal/` for DPA and privacy policy templates to start with.

---

## Priority of fixes

The limitations are ordered roughly by severity:

| Priority | Item |
|---|---|
| **High** | 2.1 PostgreSQL vault, 4.1 Distributed rate limiting, 4.2 Multi-tenant isolation |
| **Medium** | 3.1 Streaming detokenization, 1.1 Optional ML NER, 4.3 RBAC |
| **Low** | 5.x Dashboard polish, 4.6 /docs restriction, 7.3 Phone-home |

Items at the bottom are addressable with configuration; items at the top are architectural and will land in v0.2-v0.3.
