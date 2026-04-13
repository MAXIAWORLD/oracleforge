# GuardForge — Plan exécution complète "Guard"

> Décidé : 13 avril 2026
> Objectif : produit niveau professionnel, vendable day-1, casse le marché PII redaction
> Durée totale estimée : ~25h cumulées sur 5-7 sessions Claude Code

---

## 1. PRICING FINAL (verrouillé)

### Cloud SaaS (mensuel — récurrent, anti-revente)

| Tier | Prix | Quotas / Features | Vs marché |
|---|---|---|---|
| **Free** | **0€** | 10k scans/mois · 3 langues (EN/FR/DE) · 1 user · communauté | Tue Presidio + acquisition |
| **Starter** | **39€/mo** | 100k scans · 15 langues · 1 user · custom entities (5) · email support 48h · audit 30j | -60% vs Private AI ($99) |
| **Pro** ⭐ | **129€/mo** | 1M scans · 5 users · webhooks · custom entities ∞ · PDF export · SDK Python · audit 1 an · support 24h | -57% vs Nightfall (~$300) |
| **Business** | **349€/mo** | 5M scans · 20 users · multi-tenant · SLA 99.9% · Slack support · SIEM integration · audit illimité | -65% vs Nightfall mid (~$1000) |
| **Enterprise** | **dès 999€/mo** (contact) | Illimité · SSO SAML · CSM dédié · audit logs export · SLA custom · cloud dédié region | -50 à -70% vs Skyflow/Tonic |

### Self-hosted (one-time, licence proprietary + phone-home)

| Tier | Prix | Limites |
|---|---|---|
| **Self-host Starter** | **299€** one-time | 1 instance · Pro features · 6 mois updates · forum support |
| **Self-host Pro** ⭐ | **899€** one-time | 5 instances · all features · 12 mois updates · email support |
| **Self-host Enterprise** | **2999€** one-time | ∞ instances · code source partiel · 24 mois updates · 4h dev custom · email priority |

### Bundles Forge Suite (cross-sell)
- **Forge Suite Cloud** (les 6 produits) : **349€/mo** au lieu de 6×129 = 774€ → **-55% bundle discount**
- **Forge Suite Self-host** : **3499€** one-time

### Logique pricing
- 39€ = au-dessus du seuil "indie/hobby" (qui finit à 20€) → ne paraît PAS cheap
- 129€ = "sérieux SMB", classique pour outils tech professionnels
- 349€ = mid-market clair, pas un jouet
- 999€ = enterprise sérieux mais accessible
- Tous 40-65% sous concurrence directe → casse le marché sans dévalorisation

---

## 2. MARCHÉ DAY-1

- **Cloud EU** sur VPS OVH (Frankfurt/Paris)
- **Self-hosted** : worldwide (US, APAC, Brazil, partout) — résout data residency sans cloud multi-région
- **Cloud US/APAC** : ajouté QUAND premier client payant le demande, financé par son MRR

---

## 3. COMPLIANCE — 12 juridictions

### 5 prioritaires (presets complets)
- 🇪🇺 RGPD (existe déjà)
- 🇪🇺 EU AI Act (NEW)
- 🇺🇸 HIPAA (existe déjà)
- 🇺🇸 CCPA / CPRA (NEW)
- 🇧🇷 LGPD (NEW)

### 7 stubs (preset chargé, description traduite, mappé sur RGPD baseline)
- 🇨🇦 PIPEDA
- 🇯🇵 APPI
- 🇸🇬 PDPA Singapore
- 🇿🇦 POPIA
- 🇮🇳 DPDP Act
- 🇨🇳 PIPL
- 🇦🇺 Privacy Act 1988

### Doc à produire
- Page `/compliance` dashboard avec matrice "supporté" par juridiction
- Section README compliance
- Descriptions traduites en 15 langues

---

## 4. PLAN EXÉCUTION — 4 phases

### PHASE A — Bloquants production (~6h)
- **A1** Vault DB persistence (fix bug critique tokenmaps perdues au restart)
- **A2** README + Getting Started complet
- **A3** LICENSE proprietary
- **A4** OpenAPI docs enrichies (examples, descriptions)
- **A5** 12 compliance presets (5 complets + 7 stubs)
- **A6** Page `/compliance` dashboard avec matrice juridictions
- **A7** Documents légaux drafts (DPA, Security Whitepaper, Sub-processors, Privacy Policy, ToS)

### PHASE B — Différenciateurs (~8h)
- **B1** SDK Python drop-in (`from guardforge import OpenAI`)
- **B2** PDF export compliance reports
- **B3** Custom entities CRUD (page `/entities` + endpoints)
- **B4** Webhooks high-risk alerts
- **B5** Polish UX dashboard (loading states, toasts, error boundaries)

### PHASE C — Qualité (~6h)
- **C1** Tests E2E Playwright sur 5 flows critiques
- **C2** Benchmarks performance (p50/p95 sur 1000 req)
- **C3** Validation precision/recall datasets PII publics multi-langue
- **C4** Documenter limitations connues
- **C5** Coverage backend ≥80%
- **C6** Hardening sécurité (rate limit Redis, CORS strict, security headers)

### PHASE D — Lancement (~5h, dont actions user)
- **D1** Site marketing 1-page (Vercel free)
- **D2** Page comparaison vs Presidio/Nightfall
- **D3** GitHub repo OSS limité (acquisition funnel)
- **D4** Compte LemonSqueezy + variants pricing (**user only**)
- **D5** Démo vidéo 2-3 min Loom (**script par moi, enregistrement par user**)
- **D6** Drafts annonces HN/Reddit/Twitter (**post par user**)

---

## 5. ENGAGEMENTS D'EXÉCUTION

1. Aucune feature ne passe en "fait" sans test live (curl + browser)
2. Pytest full après chaque change backend
3. Build dashboard après chaque change frontend
4. Si bug trouvé en cours, fix avant de continuer
5. Git commit checkpoint entre chaque phase
6. Routage modèles strict : Haiku audits/grep, Sonnet implémentation, Opus orchestration/vérif
7. Jamais 2 features en parallèle sans tester celle d'avant

---

## 6. ÉTAT D'AVANCEMENT

| Phase | Statut |
|---|---|
| A | 🟡 EN COURS — démarrage A1 |
| B | ⚪ pending |
| C | ⚪ pending |
| D | ⚪ pending |

**Dernière action** : 13 avril 2026 — plan validé, démarrage Phase A.1 vault persistence
