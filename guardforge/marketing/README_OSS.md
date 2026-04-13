# GuardForge

> **Drop-in PII redaction for LLM apps.** One line of code stops your users' data from leaking to OpenAI, Anthropic, and any other LLM provider.

[![Website](https://img.shields.io/badge/website-guardforge.io-00e5ff)](https://maxialab.com/guardforge)
[![Docs](https://img.shields.io/badge/docs-available-b44aff)](https://maxialab.com/guardforge/docs)
[![License](https://img.shields.io/badge/license-Proprietary-red)](#license)
[![Languages](https://img.shields.io/badge/dashboard-15_languages-0afe7e)](#dashboard)

---

## What is GuardForge?

A PII detection + reversible tokenization service designed specifically for SaaS companies shipping AI features. It sits between your application and your LLM provider, redacting 17+ types of personally identifiable information before they leave your infrastructure, and restoring the real values in the LLM's response.

**Built for compliance with:** GDPR, EU AI Act 2024/1689, HIPAA, PCI-DSS, CCPA, LGPD, and 8 more jurisdictions — all as built-in policy presets.

```python
# Before
# from openai import OpenAI

# After
from guardforge import OpenAI

client = OpenAI(api_key="sk-...")
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hi, I am Jean Dupont, IBAN FR7630006000011234567890189"}],
)
# response.choices[0].message.content has real IBAN restored
# But OpenAI only saw tokenized placeholders
```

---

## Why

Every company shipping ChatGPT-like features has the same compliance time bomb: **user data flowing unredacted to OpenAI/Anthropic**. GDPR fines reach 4% of annual revenue. The EU AI Act adds criminal liability for high-risk AI systems in 2025-2026. HIPAA fines hit $50k per incident.

GuardForge solves this in one line of code. No proxy to deploy. No middleware to configure. Just replace the import.

---

## Key features

- **17 PII entity types**: email, phone, SSN US/FR, IBAN, credit card (Luhn-validated), SIRET/SIREN/RIB (FR), Steuer-ID (DE), DNI/NIE (ES), Codice Fiscale (IT), passport, person names, and more
- **Reversible tokenization**: replace with `[PERSON_NAME_a3f2]` tokens, restore real values after the LLM responds
- **13 compliance jurisdictions**: GDPR, EU AI Act, HIPAA, CCPA, LGPD, PCI-DSS + 7 baseline (PIPEDA, APPI, PDPA, POPIA, DPDP, PIPL, Privacy Act AU)
- **Persistent audit log**: every scan recorded in the database, exportable as PDF for GDPR Article 30
- **15-language dashboard**: EN, FR, DE, ES, IT, PT, NL, PL, RU, TR, AR, HI, JA, KO, ZH
- **Python SDK**: `pip install guardforge` — drop-in wrapper for OpenAI and Anthropic
- **Custom entities**: define your own regex patterns via API or dashboard
- **Webhooks**: high-risk alerts with HMAC-SHA256 signed payloads
- **Vault**: AES-256 encrypted secret storage, survives restarts
- **Sub-10ms latency**: p50 5ms scan, p95 7ms, 178 req/sec on commodity hardware

---

## Editions

GuardForge comes in two flavors:

### Cloud SaaS (EU-hosted)
Start free with 10k scans/month. Scale up to 5M+ scans without infrastructure work.

| Tier | Price | Scans/mo | Support |
|---|---|---|---|
| **Free** | 0€ | 10,000 | Community |
| **Starter** | 39€/mo | 100,000 | Email 48h |
| **Pro** ⭐ | 129€/mo | 1,000,000 | Priority 24h |
| **Business** | 349€/mo | 5,000,000 | Slack + SLA |
| **Enterprise** | from 999€/mo | Unlimited | CSM + SSO |

[**→ Start free at maxialab.com/guardforge**](https://maxialab.com/guardforge)

### Self-Hosted
One-time payment, perpetual use, your infrastructure.

| Tier | Price | Instances | Updates |
|---|---|---|---|
| **Self-host Starter** | 299€ | 1 | 6 months |
| **Self-host Pro** ⭐ | 899€ | 5 | 12 months |
| **Self-host Enterprise** | 2999€ | Unlimited | 24 months + source |

[**→ Buy self-hosted licenses**](https://maxialab.com/guardforge/self-hosted)

---

## This repository

This is a **limited public mirror** of GuardForge designed for evaluation and integration. It includes:

- ✅ **Python SDK** (`sdk/python/`) — full open access, use it freely to prototype
- ✅ **API reference documentation** (`docs/`)
- ✅ **Dashboard screenshots and feature tour** (`docs/screenshots/`)
- ✅ **Compliance templates** (`docs/legal/`) — DPA, Privacy Policy, Security Whitepaper drafts
- ❌ The backend server source code is **not** in this repository — it's delivered with your Cloud subscription or Self-Hosted license.

If you want to evaluate GuardForge **without subscribing**, the free tier gives you 10k scans per month against our hosted backend, and you only need the SDK from here.

---

## Install the SDK

```bash
# OpenAI wrapper
pip install guardforge[openai]

# Anthropic wrapper
pip install guardforge[anthropic]

# Both
pip install guardforge[all]
```

Then configure the backend URL and API key:

```bash
export GUARDFORGE_API_URL=https://api.guardforge.io
export GUARDFORGE_API_KEY=your-api-key-from-dashboard
```

See [`sdk/python/README.md`](./sdk/python/README.md) for full SDK documentation.

---

## Quick example

```python
from guardforge import OpenAI

client = OpenAI(api_key="sk-your-openai-key")

response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "Help me with my account. My IBAN is FR7630006000011234567890189 and my email is alice@example.com"}
    ],
)

print(response.choices[0].message.content)
# Output: something referencing alice@example.com and the real IBAN
# But OpenAI only saw: "[EMAIL_xxxx]" and "[IBAN_yyyy]"
```

---

## Demo

[**→ Try the live playground**](https://maxialab.com/guardforge/playground) — no signup required.

Paste any text, see PII detected, tokenize it, restore it. All via real API calls.

---

## Comparisons

We publish an honest comparison with Microsoft Presidio, Nightfall AI, Private AI, and Skyflow.

[**→ Read the full comparison**](https://maxialab.com/guardforge/compare)

**Short version**: if you want a free OSS regex detector, use Presidio. If you have a $100k+ enterprise budget, Nightfall or Private AI may fit. If you want a polished SaaS at 40-65% the price with EU residency and 13 jurisdictions built-in, use us.

---

## Compliance

Built-in policy presets for:

- 🇪🇺 **GDPR** (RGPD) — full mapping
- 🇪🇺 **EU AI Act 2024/1689** — first on the market
- 🇺🇸 **HIPAA** — US healthcare
- 🌍 **PCI-DSS v4** — payment data
- 🇺🇸 **CCPA / CPRA** — California
- 🇧🇷 **LGPD** — Brazil
- 🇨🇦 **PIPEDA** — Canada (baseline)
- 🇯🇵 **APPI** — Japan (baseline)
- 🇸🇬 **PDPA** — Singapore (baseline)
- 🇿🇦 **POPIA** — South Africa (baseline)
- 🇮🇳 **DPDP Act** — India (baseline)
- 🇨🇳 **PIPL** — China (baseline, block by default)
- 🇦🇺 **Privacy Act 1988** — Australia (baseline)

**Disclaimer**: GuardForge is a tool, not a complete compliance program. You still need a DPO, legal agreements, retention policies, and breach procedures. We provide templates in `docs/legal/` to help you get started.

---

## Limitations

We publish every known limitation in [`docs/LIMITATIONS.md`](https://maxialab.com/guardforge/limitations). Highlights:

- **Regex-only detection** (no ML NER yet — on roadmap). Works great for structured PII (emails, IBANs, SSNs) but misses unstructured names without titles.
- **Streaming LLM responses** are not yet auto-detokenized (v0.2 target).
- **Async clients** (AsyncOpenAI, AsyncAnthropic) are not yet wrapped.
- **Single-tenant** by default (multi-tenant Enterprise tier on roadmap).
- **Vault persistence is SQLite-only** (PostgreSQL falls back to in-memory mode).

Most competitors do not publish limitations publicly. We do, because buyers deserve it.

---

## License

GuardForge is **proprietary software**. See [LICENSE](./LICENSE) for terms.

- ✅ The Python SDK in this repository can be used for free to integrate with your Cloud subscription or Self-Hosted installation
- ❌ The backend server may not be redistributed, resold, or offered as a competing service
- For commercial licensing inquiries: `contact@maxialab.com`

---

## Links

- **Website**: https://maxialab.com/guardforge
- **Documentation**: https://maxialab.com/guardforge/docs
- **API reference**: https://api.guardforge.io/docs (Swagger UI)
- **Pricing**: https://maxialab.com/guardforge/#pricing
- **Sales**: contact@maxialab.com
- **Support**: support@guardforge.io _(coming soon)_
- **Security**: security@guardforge.io _(coming soon)_

---

**Part of the [Forge Suite](https://maxialab.com) by MAXIA Lab** — six developer tools for AI-era startups.
