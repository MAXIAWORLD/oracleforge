# GuardForge — HANDOFF

**Dernière mise à jour** : 2026-04-29
**Statut** : Pivot vers Open Source / Portfolio piece
**Budget** : 0€ (10€ domaine maximum)

---

## Décision stratégique

**Abandonné** : monétisation SaaS commerciale frontale (concurrence Nightfall/Private AI/Lakera trop bien financée, distribution solo trop dure sans capital).

**Adopté** : open-sourcing complet sous **Apache 2.0**, positionnement portfolio technique pour landing un job 60–120k€ chez Mistral AI, Doctolib, Qonto, Spendesk, Alan, Particula, Securitize, Tokeny, Bitpanda, Stripe, Anthropic Paris, ou cabinet crypto/compliance.

**Logique** : 95% des candidats juniors-mid n'ont pas d'équivalent à GuardForge en signal de maturité ingé. Vendre en pré-revenue rapporte 5–15k€ ; landing un CDI rapporte 60–120k€/an. ROI clair.

---

## État actuel (avril 2026)

### Ce qui est fait
- Backend FastAPI 3.12 + SQLAlchemy async + Pydantic V2
- Dashboard Next.js 16 Turbopack + Tailwind 4 + shadcn/ui + next-intl 15 langues
- 17 entités PII détectées (regex + heuristiques)
- Tokenisation réversible (Fernet AES-256), vault DB persistant SQLite
- 6 policies built-in (strict, moderate, permissive, GDPR, HIPAA, PCI-DSS)
- 161 tests, 83% coverage, bandit clean
- Benchmarks publiés : scan p50 5ms / p95 7ms, tokenize p50 9ms / p95 11ms
- Endpoints scan, tokenize, detokenize, audit, reports, vault, webhooks, entities
- Docs légaux : DPA, Privacy Policy, ToS, Sub-processors, Security Whitepaper
- LIMITATIONS.md honnête (atout, pas faiblesse)
- Marketing drafts : Show HN, Reddit r/programming + r/LocalLLaMA + r/privacy, X thread 10 tweets
- Pricing strategy défini (mais sera ignoré pour OSS)

### Ce qui n'est PAS fait (et on ne fera PAS pour le pivot OSS)
- ML NER (regex-only suffisant, limitation documentée)
- PostgreSQL vault adapter
- Multi-tenant isolation
- RBAC / SSO
- Streaming detokenization
- Async clients wrapping
- Phone-home telemetry
- Jurisdictions tier 2 (CCPA, LGPD, PIPEDA, APPI, PDPA, POPIA, DPDP, PIPL, Privacy Act AU)
- SIEM integration

→ Tout ça reste en LIMITATIONS, ne sont PAS des blockers pour le release OSS.

---

## Plan d'exécution — 3 semaines, 10€

### Semaine 1 — Stabilisation (15h estimées)

Fixes critiques uniquement :

1. **SIREN false positive** (`backend/services/pii_detector.py` §1.3 LIMITATIONS) : désactiver par défaut, ré-activable via custom policy
2. **Webhook dispatch p50 jump 113ms** (§4.4) : timeout strict 1s + circuit breaker simple sur dead URLs
3. **`/docs` Swagger en prod** (§4.6) : désactiver via env `ENV=production`
4. **Vault auto-key** : raise exception explicite si `VAULT_ENCRYPTION_KEY` absent en prod (pas de génération silencieuse qui détruit les sessions au restart)
5. **Streaming wrapper** (§3.1) : `raise NotImplementedError("stream=True not yet supported, see LIMITATIONS.md")` au lieu de comportement silent dans `sdk/python/`
6. **Cleanup repo** :
   - `git rm dashboard/AGENTS.md dashboard/CLAUDE.md`
   - Audit git history pour secrets : `git log -p | grep -iE "key=|secret=|password=|token="`
   - Si secret trouvé : `git filter-repo` ou repo neuf
7. **README** : remplacer `your-org/guardforge` par chemin réel

### Semaine 2 — Open source readiness (15h)

1. **Switch licence Apache 2.0** :
   - Remplacer `LICENSE` par texte Apache 2.0 officiel
   - Update README "License: Proprietary" → "License: Apache 2.0"
   - Header SPDX dans fichiers source clés
   - Update `package.json`, `pyproject.toml` champs license

2. **Fichiers OSS standards** :
   - `CONTRIBUTING.md` (setup dev, run tests, code style, PR guidelines)
   - `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1 standard)
   - `SECURITY.md` (process de reporting vulnérabilité)
   - `.github/ISSUE_TEMPLATE/bug_report.md`
   - `.github/ISSUE_TEMPLATE/feature_request.md`
   - `.github/PULL_REQUEST_TEMPLATE.md`
   - `CHANGELOG.md` v0.1.0

3. **CI/CD GitHub Actions** :
   - `.github/workflows/test.yml` : pytest backend + npm test dashboard, sur push + PR
   - `.github/workflows/lint.yml` : ruff + mypy + eslint + prettier
   - `.github/workflows/security.yml` : bandit + safety (Python) + npm audit
   - Badges README : tests, license, Python version, coverage
   - Release workflow auto sur tag `v*.*.*`

4. **Publication SDK PyPI** :
   - `pip install guardforge` doit marcher
   - Version 0.1.0 propre, classifiers, README rendered correctement
   - Workflow `publish.yml` pour release auto

5. **README repolish OSS** :
   - Hero clair 3 lignes
   - "Why" avant "How"
   - Quick start ≤ 5 commandes
   - Demo GIF (Peek/ttygif) ou screenshot
   - Lien playground live + blog post technique

### Semaine 3 — Distribution + signal recruteur (15h)

1. **Production deployment** :
   - Domaine `guardforge.io` (10€/an Namecheap)
   - DNS Cloudflare gratuit
   - Email forwarding `hello@guardforge.io` → mail perso
   - Backend sur Fly.io free tier (FastAPI + SQLite, 256MB RAM suffisant)
   - Dashboard sur Vercel free tier
   - Playground accessible sans signup à `playground.guardforge.io`
   - Statuspage (Better Stack free)

2. **Marketing minimaliste** :
   - Déployer `marketing/index.html` à `guardforge.io`
   - Déployer `marketing/compare.html` à `guardforge.io/compare`
   - LIMITATIONS.md accessible à `guardforge.io/limitations`

3. **Storytelling recruteur** (le vrai signal) :
   - **Article blog technique 2000–3000 mots** : "How I built a production-ready PII redaction tool in 3 weeks"
     - Sections : problème → décisions techniques (regex vs NER trade-off, Fernet, Next.js 16 Turbopack pain, Pydantic V2 migration) → benchmarks → limitations honnêtes
     - Publier sur dev.to + Medium + Substack + cross-post LinkedIn
   - **Loom 3 min** : démo end-to-end golden path
   - **Show HN** (draft existe `marketing/LAUNCH_DRAFTS.md`) : poster lundi 9h CET
   - **Twitter thread** (draft existe) : poster mardi
   - **Reddit r/programming + r/LocalLLaMA** : étalé sur 3 jours

4. **Job hunt en parallèle** :
   - LinkedIn headline : "Software engineer — creator of GuardForge (OSS GenAI compliance)"
   - Section Featured : lien GitHub + playground + blog post
   - Apply 10 jobs/semaine avec lien GuardForge en proof
   - DM 30 CTO/Lead Hiring boîtes cibles via LinkedIn

---

## Décisions techniques actées

| Décision | Choix | Pourquoi |
|---|---|---|
| Licence | **Apache 2.0** sur tout (backend + dashboard + SDK) | Max enterprise-friendly, patent grant, signal de pro |
| ML NER | Reporté indéfiniment | Limitation acceptable, regex precision 1.00 sur dataset validation |
| PostgreSQL vault | Reporté | SQLite suffisant pour OSS demo, doc workaround dans LIMITATIONS §2.1 |
| Multi-tenant | Reporté | Hors scope portfolio, cible solo dev showcase |
| Streaming | Exception explicite | Préempt critique HN sur silent fail |
| Phone-home | Annulé définitivement | OSS = pas de license enforcement remote |
| Hosting prod | Fly.io free + Vercel free | 0€ runway |
| Domaine | guardforge.io ~10€/an | Seul coût cash réel |

---

## Cibles job hunt (semaines 1–6 en parallèle)

### Tier 1 — boîtes les plus alignées
- **Mistral AI** (Paris) : compliance + LLM tooling
- **Doctolib** (Paris/Berlin) : HIPAA-équivalent, 100M utilisateurs santé
- **Particula** (Berlin) : PDARP risk passport, ex-Moody's hire récent
- **Anthropic Paris** : enterprise compliance team
- **Securitize, Tokeny** : tokenization, compliance-heavy

### Tier 2 — fintech EU avec besoin GenAI safety
- Qonto, Spendesk, Pennylane, Alan, Lifen, Lydia
- Bitpanda (Vienne) — Vision Chain équipe
- Stripe (Dublin/Paris) — security platform
- Cabinet crypto/Web3 EU : MME, Bowmans, Adan

### Tier 3 — fallback large
- BigID, OneTrust (data privacy)
- Cloudflare, Datadog (security platform)
- Snyk (Tel Aviv/Londres)
- Toute startup AI-native EU série A/B

---

## Métriques de succès

### À 6 semaines
- ✅ Code OSS publié sous Apache 2.0
- ✅ Playground live, 0 downtime
- ✅ Article blog avec ≥1000 vues
- ✅ Show HN posté (peu importe résultat)
- ✅ ≥30 candidatures envoyées
- ✅ ≥5 entretiens techniques en cours

### À 12 semaines (sortie idéale)
- ✅ Offer signé entre 60–120k€
- ✅ GuardForge cité comme proof dans l'offre

### Plan B si pas d'offer à 12 semaines
- Lancer en SaaS quand même (Lemon Squeezy, suivi des drafts marketing existants)
- OU vendre sur Acquire.com pré-revenue 5–15k€ (Voie 1 archivée des notes de session)
- OU prendre job moins idéal et garder GuardForge comme side project

---

## Ce qu'il NE faut PAS faire

- ❌ Implémenter ML NER pour "rattraper" Presidio → diversion
- ❌ Re-design dashboard, ajouter pages → polish ≠ value recruteur
- ❌ Ajouter jurisdictions tier 2 → personne n'auditera ça
- ❌ Tenter monétisation SaaS pendant la phase OSS → conflit positionnement
- ❌ Cacher les limitations → c'est l'atout #1
- ❌ Tease sans déployer → GitHub vide + playground live > 10 articles d'annonce
- ❌ Pivot vers RWA / autre domaine pendant 6 semaines → focus

---

## Prochaine action immédiate (aujourd'hui, 1h)

1. Acheter `guardforge.io` sur Namecheap (10€)
2. Ajouter `LICENSE` Apache 2.0 (copier de https://www.apache.org/licenses/LICENSE-2.0.txt)
3. Update README ligne `License: Proprietary` → `License: Apache 2.0`
4. `git rm dashboard/AGENTS.md dashboard/CLAUDE.md`
5. Créer compte GitHub public, repo `guardforge` ou `maxia-lab/guardforge`
6. Push initial OSS

→ Si fait dans la journée, semaine 1 démarre demain.

---

## Notes de session

- Conversations précédentes ont couvert RWA brainstorming (compliance DAOs, agent identity, future labor, encrypted compute, ratings RWA, CRM issuers, real estate ops, Web3 corp treasury). Tout archivé, **pas de pivot vers RWA pendant 6 semaines**.
- Voie alternative cession Acquire.com pré-revenue (5–15k€) documentée mais non retenue (ROI inférieur au job + portfolio).
- Vérification avril 2026 : marché RWA ×4 YoY, Particula domine notation on-chain, Bitpanda Vision Chain mainnet 25 mars 2026, MiCA enforcement 1er juillet 2026, GENIUS Act US signé juillet 2025.
- Rappel : 0€ initial → impossible de concurrencer Securitize/Bitpanda/Particula. GuardForge déjà construit = seule option exploitable immédiatement.

---

**À lire en début de session suivante.**
