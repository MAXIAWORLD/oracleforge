# HANDOFF — Session 30 avril 2026 — GuardForge OSS + landing + audit-ia

## Ce qui a été fait

- **GuardForge OSS** : Apache 2.0 + docker-compose (backend + dashboard) + 5 fixes critiques (CORS, Swagger prod, vault key, webhook timeout, streaming NotImplementedError) + README local-first. Pusché sur `github.com/MAXIAWORLD/guardforge`
- **Fix CORS** : `localhost:3003` ajouté dans les defaults `config.py` + `.env.example`
- **Dashboard local** : testé et fonctionnel sur `localhost:3003` (backend `localhost:8004`)
- **maxiaworld.app/guardforge** : landing complète créée et déployée (stats, quick start, features, limitations)
- **maxiaworld.app/** : card GuardForge ajoutée (4ème card), lede mis à jour
- **maxiaworld.app/audit/** : section GuardForge ajoutée (explication RGPD client, 3 étapes, cards techniques, bandeau inclus dans rapport) + ligne dans tarifs Pro/Complet
- **Mémoires** : GuardForge ajouté dans `mon-setup` et `automatisation-locale`
- **Reddit J3** : 5 commentaires préparés (3 generiques + 2 sur threads trouvés)
- **Cold emails** : 5 cibles Apollo identifiées (Kintsugy, ALCOM, COGIGROUP, IA Drones, Made In Tracker) — emails rédigés, manque crédits pour 2 derniers

## ⚠️ Actions Alexis restantes

- Poster les commentaires Reddit préparés aujourd'hui
- Poster les 2 posts LinkedIn BudgetForge + Audit IA (en retard depuis J2)
- Récupérer emails Apollo + envoyer les cold emails (5 cibles prêtes)
- Lister BudgetForge sur MicroAcquire + Flippa (en retard depuis J2)
- Recharger crédits Apollo si besoin pour IA Drones + Made In Tracker

## Prochaine session J4 (1er mai)

1. Reddit J4 : 3 nouveaux commentaires
2. Surveiller réponses cold emails (10 envoyés depuis J1)
3. Surveiller thread HN Token Counter
4. FAQ acheteurs BudgetForge (10 Q/R) — en retard depuis J2
5. MicroAcquire + Flippa si pas fait

---

# HANDOFF — Session 29 avril 2026 — Stripe + cold emails + Reddit J2

## Ce qui a été fait

- **5 cold emails rédigés** (Richard Dorard/BEWAI, Teo Hivart/Altexence, Joel Baude/INQU-AI, Fabrice Foiry/WAIABE, Erwan Desvergnes/digiCONTACTS) — à envoyer dès que les emails Apollo sont récupérés
- **Signature email fixée** : "Cordialement, Majorel Alexis / Expert IA & Systèmes LLM / maxiaworld.app/audit"
- **Stripe configuré** : 3 Payment Links créés (Essentiel €299 / Pro €499 / Complet €749) — sauvegardés en mémoire
- **Template réponse "comment facturer"** rédigé avec les 3 liens
- **audit-ia.html** : boutons Commander → Stripe, renommage Simple→Essentiel/Complet→Pro/Urgent→Complet, fix footer Forge Suite → maxiaworld.app
- **Déployé sur VPS** + commit `2e06b94`
- **Reddit J2** : 3 commentaires prêts à poster (AskReddit, learnpython, NoStupidQuestions)

## ⚠️ Actions Alexis non faites (restent pour J3)

- Poster les 2 posts LinkedIn (BudgetForge + Audit IA)
- Récupérer les 5 emails Apollo → envoyer les cold emails
- Lister BudgetForge sur MicroAcquire + Flippa (prévu J2, pas fait)
- Poster les 3 commentaires Reddit ci-dessus

## Prochaine session J3 (30 avril)

1. Reddit J3 : 3 nouveaux commentaires (je cherche les threads au début de session)
2. Surveiller réponses cold emails
3. Surveiller thread HN Token Counter → répondre
4. MicroAcquire + Flippa listings BudgetForge
5. FAQ acheteurs BudgetForge (10 Q/R) — prévu J2, pas fait

---

# HANDOFF — Session 28 avril 2026 (soir) — Audit IA + cold emails + LinkedIn

## Ce qui a été fait (session soir)

- **Nouvelle offre : Audit IA Express** — conseil IA async, rapport PDF 48-72h, €299/€499/€749
- **Site live** : `maxiaworld.app/audit` (design AM Tech, 4 étapes, 3 cas clients, pricing -30%)
- **Apollo.io configuré** : 193 prospects FR (founder/president, 11-50 emp, LLM/AI keywords)
- **5 cold emails envoyés** : Kheops.ai, Custom IA, SPOT'IA, A.I.Mergence, Heysmart
- **BudgetForge dashboard réparé** : nginx `/api/auth` rerouté vers Next.js (3011), clé admin = `dev-admin-key` dans localStorage
- **2 posts LinkedIn rédigés** : BudgetForge + Audit IA (à poster demain matin)

## Prochaine session J2 (29 avril matin)

1. Poster les 2 posts LinkedIn (BudgetForge + Audit IA)
2. 5 nouveaux cold emails Apollo (70 crédits restants)
3. Surveiller réponses aux 5 premiers emails
4. Reddit karma J2 : 3 commentaires (routine incubation)
5. Surveiller thread HN Token Counter

---

# HANDOFF — Session 28 avril 2026 (API #1 Token Counter LIVE + Track A préparé)

## Ce qui a été fait aujourd'hui

- **C1.1→C1.7 DONE** : Token Counter API complète en une session
  - Repo `maxia-apis` créé + pushé sur `MAXIAWORLD/maxia-apis`
  - Service tiktoken multi-provider : exact (OpenAI/Mistral) + estimated (Anthropic/Google/Cohere)
  - 36 tests TDD verts
  - Deploy Railway : `https://maxia-apis-production.up.railway.app`
  - Listing RapidAPI live : BASIC $0 / PRO $9 / ULTRA $29
  - Show HN posté : https://news.ycombinator.com/item?id=47931942
- **Phase 1 Reddit J1** : 3 commentaires postés (r/learnpython, r/AskReddit, r/NoStupidQuestions)
- **BudgetForge** : skip listing Acquire (0 MRR = invendable sérieusement). Archive dans 60j.

## Track A — Cold email freelance (préparé fin J1, AWAITING ALEXIS VALIDATION)

Décidé dans `PLAN_SESSIONS_API.md` (Decisions #6, #9, #10) mais jamais opérationnalisé. Préparé en fin de session J1 :

- **Profil cible** validé : mix AI/LLM US + DeFi + agences FR, EN+FR, TJM €550 / $700/jour, async-only
- **Source leads** recommandée : YC Directory (gratuit) + Apollo free (50/mois) + Hunter free (25 vérifs/mois) + Free-Work + DefiLlama + TechBehemoths FR
- **3 templates rédigés** : A (AI/LLM US, EN), B (DeFi, EN), C (Agence FR, FR)
- **5 prospects identifiés** pour J2 : RamAIn (YC W26), E2B, PeakLab (Paris), LightOn (Paris), RedStone
- **5 emails personnalisés draftés** — variables `[email]` à remplir via Apollo demain matin

**⚠️ Action Alexis avant J2 matin** : valider les 5 emails (corrections OK) ET dire si Track A est ajouté à `PLAN_SESSIONS_API.md` (je ne l'ai pas édité — pas de "go" reçu).

Contenu détaillé (templates + prospects + emails) dans le transcript de session J1 (chercher "Track A — livrables pour J2").

## Prochaine session J2 (29 avril)

1. **Track A** : Alexis valide les 5 emails → Apollo pour récup emails → envoi 5/jour 9-11h
2. Surveiller thread HN → répondre aux commentaires
3. Reddit J2 : 3 nouveaux commentaires (donner threads au début de session)
4. Évaluer signal HN avant de démarrer C2 (API #2 Cost Estimator)

---

# HANDOFF — Session 28 avril 2026 (PIVOT vers APIs RapidAPI)

## ⚠️ DERNIER PIVOT — 28 avril 2026

**BudgetForge et stratégie team/entreprise = abandonnés.**

Nouveau plan : **5 APIs sur RapidAPI** extraites du code existant (BudgetForge + OracleForge + LLMForge + AuthForge).

➡️ **Première action chaque session : lire `PLAN_SESSIONS_API.md` à la racine.** Tout y est planifié par jour.

### Pourquoi ce pivot
- BudgetForge = marché LLM cost saturé (LiteLLM, Portkey, Helicone, etc.) — vendable à tort confirmé
- Team/entreprise demande vente humaine — Alexis refuse contact direct
- API marketplace = 0 vente directe, paiement automatique, distribution organique
- Code déjà à 80% écrit dans les forges existantes

### Règles dures décidées 28 avril
1. ❌ Twitter banni (Alexis banned)
2. ❌ 0 call / 0 visio / 0 démo live
3. ✅ Reddit + HN + GitHub + IndieHackers + Hashnode = canaux principaux
4. ✅ Validation publique AVANT code (vs erreur BudgetForge)
5. ✅ WebSearch obligatoire avant toute affirmation marché
6. **BudgetForge mis en vente sur Acquire/MicroAcquire/Flippa** — période 60j puis archive

### Top 5 APIs à valider/build (ordre)
1. Token Counter Multi-Model (depuis `budgetforge/services/token_estimator.py`)
2. LLM Cost Estimator Multi-Provider (depuis `cost_calculator.py` + `dynamic_pricing.py`)
3. Pyth Network REST (depuis `oracleforge/services/oracle/pyth_solana_oracle.py`)
4. Semantic LLM Cache (depuis `llmforge/services/cache.py`)
5. Oracle Anomaly Detection (depuis `oracleforge/services/oracle/intelligence.py`)

---

# (ANCIEN) HANDOFF — Session 27 avril 2026 (Phase 0 distribution + V12 kill)

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

## ⚠️ PIVOT STRATÉGIE — fin de session 27 avril

Phase 0 a été exécutée par erreur en **mode indie** (BETA50 lifetime, pricing $29-79, AppSumo planifié, signup form perso). Le vrai ICP décidé dès le 12 avril est **équipes dev 3-20 personnes avec budget IT** = team/entreprise.

**Plan d'adaptation à exécuter en priorité prochaine session :** voir mémoire `project_strategy_pivot_team_enterprise.md`.

Résumé : refonte pricing ($199 Team / $599 Business / Custom Enterprise), refonte hero copy ("Cap your team's LLM spend before the CFO sees the bill"), drop BETA50 → Design Partner Program, Loom walkthrough à enregistrer, distrib refondue (LinkedIn outbound + cold email senior + cabinets conseil — kill AppSumo/Smithery), OracleForge repositionné asset marketing OSS sans revenue attendu.

Question à reposer à Alexis dès le début : "tu acceptes ou pas 1 call B2B / sem max ? Si non, on double le besoin social proof."

## Première action prochaine session

1. Lire ce fichier en premier
2. Lire `feedback_icp_team_enterprise.md` (règle dure ICP)
3. Lire `project_strategy_pivot_team_enterprise.md` (plan d'exécution)
4. Reposer la question "1 call/sem max" à Alexis
5. Démarrer refonte pricing + landing copy team/entreprise
6. **NE PAS** enchaîner sur "Phase 1 étape A directories agents IA" — c'était la stratégie indie obsolète
