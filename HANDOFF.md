# HANDOFF — Session 27 avril 2026 (Phase 0 distribution + V12 kill)

## État global

- **Forge Suite** : 2 forges en prod, hub statique à `maxiaworld.app`
- **BudgetForge** : code freeze (verdict ship), 0 paying user
- **OracleForge** : v0.1.9 prod, 0 paying user
- **MAXIA V12** : killé sur prod (régulé), archive conservée

---

## Ce qui a été fait dans cette session

### Phase 0 distribution (DONE)

| Item | Détail |
|---|---|
| **Umami self-hosted analytics** | `https://analytics.maxiaworld.app` (login admin / mot de passe défini par Alexis le 27/04). 3 sites trackés : BudgetForge, OracleForge, Hub. SSL Let's Encrypt jusqu'au 2026-07-26. |
| **Audit copy Lot 1** | Hero des 2 landings refait : "Stop unexpected LLM API bills" + "Stop your AI agent from trading on a wrong price". Pricing visible dans hero. |
| **Beta badge** | Kicker "Beta · 50% lifetime for first 50 users" sur les 2 landings. |
| **Coupon Stripe** | `BETA50` créé : 50% off, permanent (Forever), 50 max redemptions. Promotion code activé. |
| **Loops audience sync** | Compte créé, sending domain `mail.maxiaworld.app` validé (DKIM/SPF/DMARC). API key en env var prod (jamais commitée). 2 audiences : `BudgetForge Beta` (sync via signup) + `OracleForge Beta` (sync via waitlist endpoint). |
| **OracleForge waitlist** | Nouvel endpoint `POST /api/waitlist` (8 tests TDD verts). Form sur landing. |
| **BudgetForge Loops integration** | `services/loops_sync.py` (4 tests TDD verts). Push Loops asynchrone après signup. |
| **V12 marketplace killed** | `maxia.service` stoppé+disabled. `/opt/maxia/frontend` archivé. nginx config simplifié (static + monitor). |
| **Forge Suite hub** | `maxiaworld.app` sert un hub minimal : 2 cards BudgetForge + OracleForge, footer support@. Umami tracker actif. |
| **Email convention** | `ceo@maxiaworld.app` → `support@maxiaworld.app` partout (8 fichiers, 3 sites). |
| **Code freeze BudgetForge** | Verdict formalisé : plus d'audit jusqu'à 50 paying users ou bug bloquant. Mémoire `project_budgetforge_ship_verdict.md`. |

### Tests verts ajoutés

- BudgetForge `tests/test_loops_sync.py` : 4/4
- OracleForge `tests/test_waitlist.py` : 8/8

### Backups VPS

- `/opt/budgetforge/backend/.env.bak-*`
- `/etc/maxia-oracle/env.bak-*`
- `/opt/budgetforge/dashboard/app/page.tsx.bak-loops-*`
- `/opt/budgetforge/backend/routes/signup.py.bak-loops-*`
- `/opt/budgetforge/backend/core/config.py.bak-loops-*`
- `/opt/maxia-oracle/oracleforge/backend/main.py.bak-loops-*`
- `/var/www/oracle/index.html.bak-loops-*`
- `/etc/nginx/sites-available/maxia.bak-pre-killV12-*`
- `/opt/maxia/frontend.archive-v12-2026-04-27/` (68 HTML originaux V12)

---

## ⚠️ Action Alexis avant prochaine session

1. **Vérifier l'alias `support@maxiaworld.app` dans OVH Email Pro Zimbra.** Si pas créé, le créer comme alias de ton inbox principale. Sinon les emails reçus bouncent.
2. **Supprimer le contact test `smoketest@maxialab.example` dans Loops** (Audience → search → delete).

---

## Tâches pending pour prochaine session

### #8 Phase 1 Distribution multi-canal (4 sem) — PRIORITÉ MAX

Ordre recommandé :

| Étape | Effort | Impact | Action |
|---|---|---|---|
| **A. Directories agents IA** | 1-2h | trafic gratuit récurrent | Submit BudgetForge + OracleForge sur Smithery, mcp.so, AI Tools List, Glama, AI Agents Directory, etc. (10 directories). Je rédige les fiches, Alexis copy-paste. |
| **B. SEO content** | 3-4h | long terme | 3 articles ciblés mots-clés "openai cost limit", "claude api budget", "stop runaway llm bills". Hébergement : `/blog` sur llmbudget. |
| **C. AppSumo Marketplace** | 2h + délai 2-4 sem | trafic massif si accepté | Submit BudgetForge en lifetime deal $59-79. |
| **D. Cold email FR agences IA** | 2h setup + ongoing | meilleur ROI court terme | 50 emails/jour via Lemlist, scrape Welcome to the Jungle. |

### #9 Phase 2 Optimisation conversion

Après Phase 1 : Lot 2 + Lot 3 audit copy (B3 storytelling, B4 pricing visible, B5/B6/B7, O5/O6/O7).

---

## Décisions structurelles à mémoriser

- **Code freeze BudgetForge** jusqu'à 50 paying users ou bug bloquant rapporté par paying user
- **Pas de Calendly** (Alexis ne veut pas de calls) → support par email uniquement
- **maxiaworld.app** = hub Forge Suite statique, pas un produit
- **Loops.so** = stack email officielle (pas de SMTP custom au-delà des emails transactionnels existants)
- **Umami self-hosted** = stack analytics officielle (jamais de Google Analytics, RGPD)

---

## Commits / files à committer côté Alexis

Modifs locales non committées :
- `budgetforge/dashboard/app/page.tsx`, `dashboard/app/docs/page.tsx`
- `budgetforge/backend/services/loops_sync.py` (nouveau)
- `budgetforge/backend/tests/test_loops_sync.py` (nouveau)
- `budgetforge/backend/core/config.py`
- `budgetforge/backend/routes/signup.py`
- `oracleforge/backend/services/email/__init__.py` + `loops_sync.py` (nouveaux)
- `oracleforge/backend/api/routes_waitlist.py` (nouveau)
- `oracleforge/backend/tests/test_waitlist.py` (nouveau)
- `oracleforge/backend/main.py`
- `oracleforge/landing/index.html`, `landing/docs/index.html`, `llms.txt`, `placeholder.html`, `openapi.json`, `docs/openapi.json`
- `maxia-hub/index.html` (nouveau dossier)

Suggestion commit messages :
- `feat(loops): sync signup emails to Loops.so audiences (TDD)`
- `feat(oracleforge): waitlist endpoint + landing form`
- `chore: ceo@ → support@ email throughout`
- `feat(maxia-hub): static Forge Suite hub replaces V12 marketplace`
- `chore(landings): hero copy lot 1 — beta badge + clearer value prop`

---

## Première action prochaine session

Lire ce fichier en premier. Puis enchaîner sur **Phase 1 étape A — directories agents IA**.
