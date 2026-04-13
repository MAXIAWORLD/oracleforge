# GuardForge Launch Announcement Drafts

Three drafts for distinct audiences. Adapt before posting — these are starting points.

**Before launching**:
1. Replace `guardforge.io` with your actual domain once registered
2. Replace `maxialab.com/guardforge` with the real URL
3. Have the free tier live and the pricing page clickable
4. LemonSqueezy checkout working (even if only Free + one paid tier)
5. A friend or two ready to upvote/comment in the first hour (not fake, actual people who saw the demo)

---

## Draft 1 — HackerNews "Show HN"

**Title (≤80 chars):**
`Show HN: GuardForge – Drop-in PII redaction for OpenAI and Anthropic`

**Post body:**

```
Hi HN — I built GuardForge because every SaaS company I talked to had the
same story: "We'd love to add ChatGPT features, but legal won't let us
ship user data to OpenAI."

GuardForge sits between your app and your LLM provider. You change one
import line:

  # from openai import OpenAI
  from guardforge import OpenAI

and PII stops leaking. Names, IBANs, emails, SSNs, SIRETs, credit cards
(Luhn-validated), and 13 more entity types get replaced with stable
tokens before the message leaves your infrastructure. The LLM response
comes back with tokens still in place, then the SDK restores the real
values on the client side. Your user sees their real name; OpenAI never
did.

Stack: Python 3.12 + FastAPI + SQLAlchemy async + cryptography (Fernet)
for the vault. Next.js 16 + Turbopack + Tailwind 4 + next-intl for the
dashboard (15 languages). Test suite: 161 unit + integration tests at
83% coverage, bandit clean, E2E flow validation.

What's different from Presidio / Nightfall / Private AI:

- Free tier is actually useful: 10,000 scans/month, no credit card.
- EU-hosted by default (GDPR Article 28 DPA + subprocessor list in the repo).
- 13 compliance jurisdictions built in as policy presets: GDPR, EU AI
  Act 2024/1689 (we're first to ship this), HIPAA, PCI-DSS v4, CCPA,
  LGPD, PIPEDA, APPI, PDPA, POPIA, DPDP India, PIPL, Privacy Act AU.
- Self-hosted is priced for startups (299€ / 899€ / 2999€ one-time)
  rather than "contact sales" enterprise pricing.
- Reversible tokenization via an encrypted vault that survives backend
  restarts (found a bug in my own implementation during Phase A and
  fixed it — if your Fernet key isn't persisted, sessions die).

What I intentionally punted on for v0.1:

- ML NER (spaCy-based): regex-only for now. Precision 1.00 and recall
  0.90 on my validation dataset, but if you have unstructured text
  where names appear without titles, you'll miss them. Optional spaCy
  integration is on the roadmap.
- Streaming LLM responses: tokens flow through but detokenization
  needs buffering. Working on a transparent stream wrapper for v0.2.
- Multi-tenant isolation: single-tenant for now, v0.3.
- SOC 2 Type II: 2027, not 2026.

Benchmark on my M1 MacBook vs the same hardware running Presidio:
GuardForge p50 scan 5ms, p95 7ms. Presidio with spaCy small model
p50 ~30ms, p95 ~80ms. (Your mileage will vary.)

Playground: https://maxialab.com/guardforge/playground (no signup)
Comparison vs Presidio / Nightfall / Private AI / Skyflow:
https://maxialab.com/guardforge/compare
Honest limitations doc (not hidden):
https://maxialab.com/guardforge/limitations

I'm the only developer on this. I'll be here all day to answer
questions. Feedback very welcome — particularly on the detection
patterns if you spot false positives or false negatives in languages
I don't speak natively.
```

**Expected questions to prepare for:**
- "Why not just use Presidio?" → honest comparison answer
- "What about ML NER?" → roadmap, trade-off explanation
- "Is the backend source open?" → no, SDK is, backend is proprietary
- "Benchmarks details?" → post the benchmark_results.md
- "Why should I trust you?" → you can run self-hosted, no data leaves, here's the DPA

---

## Draft 2 — Reddit r/programming + r/LocalLLaMA + r/privacy

**Title variations** (pick one per sub):
- r/programming: `I built a drop-in Python wrapper that stops PII from leaking to OpenAI`
- r/LocalLLaMA: `PII redaction proxy for OpenAI/Anthropic — 5ms latency, 13 jurisdictions`
- r/privacy: `Open-source tool to prevent LLM providers from seeing your users' real data`

**Post body (general, adapt per sub):**

```
Hi folks,

I spent the last few weeks building GuardForge, a tool that lets you add
GPT-4/Claude features to your SaaS app without shipping your users'
names, emails, IBANs, or SSNs to OpenAI or Anthropic.

The integration is literally one line:

    from guardforge import OpenAI

Everything else works exactly like the official OpenAI SDK. Behind the
scenes, GuardForge detects PII in every message, replaces it with
reversible tokens stored encrypted in a local vault, sends the tokenized
text to OpenAI, and restores the real values in the response before
returning it to your code.

The end user sees their real name in the answer. OpenAI never did.

What's in it:
• 17 built-in PII entity types (email, phone, SSN US+FR, IBAN, credit
  card with Luhn check, SIRET, SIREN, RIB, Steuer-ID, DNI, NIE, Codice
  Fiscale, passport, person names, etc.)
• 13 compliance jurisdictions as policy presets (GDPR, EU AI Act,
  HIPAA, PCI-DSS, CCPA, LGPD, PIPEDA, APPI, PDPA, POPIA, DPDP, PIPL,
  Privacy Act AU)
• Custom regex entities you can add via API or dashboard
• Dashboard with compliance reports (PDF export for auditors)
• Webhooks with HMAC-SHA256 signatures for high-risk alerts
• 15-language dashboard (EN, FR, DE, ES, IT, PT, NL, PL, RU, TR, AR,
  HI, JA, KO, ZH)

Free tier: 10,000 scans/month. No credit card. Self-hosted starts at
299€ one-time (real one-time, perpetual, not a trial).

Honest comparison with Presidio / Nightfall / Private AI / Skyflow:
[link]

I publish all known limitations publicly: [link]. The main one is
that detection is regex-based, not ML. It catches structured PII
reliably (precision 1.00 on my dataset) but misses unstructured names
without titles. ML NER is on the roadmap.

Feedback, criticism, bug reports all welcome. I'm a solo dev and I
built this because I got tired of compliance teams blocking AI
features. Hope it helps you ship.
```

---

## Draft 3 — Twitter/X thread (10 tweets)

**1/10** (hook):
```
I shipped a Python wrapper that stops user PII from ever reaching OpenAI.

One line of code changes:

from openai import OpenAI  →  from guardforge import OpenAI

Here's how it works and why every B2B SaaS shipping AI features
needs something like it. 🧵
```

**2/10** (problem):
```
The dirty secret of every "ChatGPT-powered" feature in SaaS:

user data flows through OpenAI's servers unredacted.

GDPR fines reach 4% of revenue.
HIPAA fines hit $50k per incident.
The EU AI Act adds criminal liability in 2025-2026.

Your compliance team knows.
```

**3/10** (solution):
```
GuardForge sits between your app and OpenAI.

Your code:
client = OpenAI(api_key="sk-...")
client.chat.completions.create(
  messages=[{"role":"user", "content": "Hi, I'm Jean Dupont, IBAN FR76..."}]
)

What OpenAI actually sees:
"[PERSON_NAME_a3f2], IBAN [IBAN_b491]..."

What your user sees: their real name + IBAN in the response.
```

**4/10** (how):
```
The trick: reversible tokenization.

1. Detect PII in the message (17 entity types, Luhn-validated cards,
   IBAN, SSN US/FR, SIRET, DNI, Codice Fiscale, etc.)
2. Replace each unique value with a stable token
3. Store the mapping encrypted (AES-256) in a session vault
4. Send tokens to OpenAI
5. Restore real values in the response before returning
```

**5/10** (compliance):
```
Compliance isn't an afterthought:

🇪🇺 GDPR — full preset
🇪🇺 EU AI Act 2024/1689 — first to ship this
🇺🇸 HIPAA + CCPA — full
🌍 PCI-DSS v4 — full
🇧🇷 LGPD 🇨🇦 PIPEDA 🇯🇵 APPI 🇸🇬 PDPA 🇿🇦 POPIA 🇮🇳 DPDP 🇨🇳 PIPL 🇦🇺 Privacy Act

13 jurisdictions. Not marketing — actual policy presets in code.
```

**6/10** (latency):
```
Fast enough to not care:

/api/scan: p50 5ms, p95 7ms, p99 8ms
/api/tokenize: p50 9ms, p95 11ms, p99 13ms

Adds ~10ms to your LLM call. OpenAI's own API latency is 500-2000ms,
so you won't notice.

Measured on commodity hardware, 1000-req benchmark, numbers published.
```

**7/10** (honest limits):
```
What I'm NOT pretending:

❌ Regex-only (no ML NER yet) → misses "John Smith" without a title
❌ Streaming LLM responses need manual buffering
❌ AsyncOpenAI not yet wrapped (use sync for now)
❌ Single-tenant (multi-tenant in v0.3)

Full limitations doc published. I value your trust more than a shiny
feature list.
```

**8/10** (pricing):
```
Free: 10k scans/month (no CC, forever)
Starter: 39€/mo (100k scans)
Pro: 129€/mo (1M scans, 5 users, SDK, webhooks)
Business: 349€/mo (5M, multi-tenant, SLA)
Enterprise: 999€/mo+ (SSO, CSM)

40-65% cheaper than Nightfall / Private AI.
Self-hosted from 299€ one-time.
```

**9/10** (demo):
```
Try it without signing up:

→ Live playground: [link]
→ Honest comparison with Presidio / Nightfall / Private AI: [link]
→ Full limitations doc: [link]
→ Pricing: [link]

161 tests, 83% coverage, bandit clean, OpenAPI docs, 15-language
dashboard. Built by a solo dev. Made in France 🇫🇷 🇪🇺
```

**10/10** (CTA):
```
If you're shipping AI features and your compliance team is nervous,
try GuardForge.

If you're NOT shipping AI features because of compliance, GuardForge
is probably why you can.

Feedback welcome. Bugs welcome. Retweets very welcome.

→ maxialab.com/guardforge
```

---

## Timing and sequencing tips

**Day 0 (launch day):**
- 09:00 CET — post to Show HN
- 10:00 CET — check responses, be in the thread
- 12:00 CET — post Twitter thread (EU lunch break, US morning)
- 14:00 CET — post to r/programming
- 16:00 CET — post to r/LocalLLaMA
- 18:00 CET — post to r/privacy
- 20:00 CET — post Twitter quote-tweets with customer replies to the main thread

**Day 1:**
- Reply to every comment on HN
- Post a "we got X signups, here's what broke" follow-up on day 2

**Day 7:**
- Write a "what we learned from Show HN" blog post
- Post it again to different subreddits
- DM everyone who signed up — ask what was confusing

---

## What NOT to do

- ❌ Don't post the same text on multiple subreddits — moderators ban cross-posts.
- ❌ Don't use "revolutionary" "game-changing" "disrupt" — dev communities hate marketing words.
- ❌ Don't hide limitations — someone will find them and crucify you.
- ❌ Don't argue with critics — thank them, note the feedback, move on.
- ❌ Don't pretend you have customers you don't have.
- ❌ Don't use AI-generated screenshots or demos — people notice.
- ❌ Don't run fake upvote rings — you will get shadowbanned.
- ❌ Don't buy ads on launch day — organic traffic looks more credible.

---

## Response templates for common comments

**"Why not use Presidio?"**
> Presidio is great if you want free, self-host only, no dashboard, no support, no compliance presets, and you're comfortable writing config files. GuardForge is for the teams that need a polished product with sub-10ms latency, a drop-in SDK, EU data residency, and 13 jurisdictional presets — and are willing to pay 39-129€/month for not having to build that themselves.

**"Is this just a thin wrapper around regex?"**
> Yes, the detection is regex + heuristics. I'm upfront about that. Recall is 90%, precision is 100% on my validation dataset. For most B2B SaaS use cases (email, IBAN, SSN, SIRET, credit cards), regex is sufficient. For unstructured free text with natural person names, optional ML NER is on the roadmap.

**"What happens if the backend goes down?"**
> The SDK fails closed by default: if GuardForge can't tokenize, your OpenAI call is aborted. That's intentional — I'd rather you see an error than leak PII. You can configure fail-open for non-critical paths, but the default is safety.

**"Self-hosted source code?"**
> Partial source code is included with the Enterprise Self-Hosted tier (2999€) under a separate Source Code Addendum. Standard and Pro Self-Hosted get binaries only. This is a business model trade-off — happy to discuss alternative licensing if you have a specific need.

**"Why should I trust you with my compliance?"**
> You shouldn't trust me with your compliance — nobody can outsource that. GuardForge is a tool that makes your compliance work easier, not a substitute for a DPO, DPA with your customers, or a retention policy. I provide templates in the docs/legal/ folder to help you start.
