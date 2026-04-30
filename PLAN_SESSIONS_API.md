# PLAN SESSIONS — Pivot APIs MAXIA Lab

**Démarrage : 2026-04-28**
**Objectif : 5 APIs sur RapidAPI + vente BudgetForge en 10 semaines**

---

## CONSIGNES POUR CLAUDE (à lire à chaque session)

1. **Lire ce fichier en premier**
2. **Vérifier la date** → identifier le jour J en cours
3. **Trouver l'action du jour** dans le calendrier ci-dessous
4. **Marquer ✅ à côté de l'action quand faite**
5. **Si tu vois ⏸️** = action bloquée, demander pourquoi
6. **Si tu vois ⚠️** = action critique, double-check avant
7. **Updater le HANDOFF.md** en fin de session

## RÈGLES DURES (à respecter à chaque session)

- ❌ **PAS de Twitter** (Alexis banni)
- ❌ **PAS d'appel téléphonique / visio** (zéro contact humain)
- ❌ **PAS de "ça existe déjà" sans vérification live** (mea culpas répétés)
- ❌ **PAS de code avant validation publique** (erreur BudgetForge)
- ✅ **Reddit + HackerNews + GitHub + IndieHackers** = canaux principaux
- ✅ **WebSearch obligatoire avant toute affirmation marché**

---

## PHASE 0 — Vente BudgetForge (Jours 1-3 = 28-30 avril)

### J1 — 28 avril 2026 ⬅️ AUJOURD'HUI
- [ ] **Action 1.1** (30 min) : préparer texte de listing BudgetForge (description, stack, métriques code, asking price $5-15k)
- [ ] **Action 1.2** (45 min) : lister sur **Acquire.com** (Alexis crée compte si pas fait)
- [ ] **Action 1.3** (15 min) : screenshot de l'admin/dashboard pour preuve

### ⚡ AJUSTEMENT 28 avril — Parallélisation code + validation

Décision : commencer le code de l'API #1 Token Counter **dès maintenant** en parallèle de la validation Reddit. Justification : effort faible (3-5j), code déjà existant à 80%, risque limité, avoir 1 API live améliore validation des suivantes.

**APIs avec code immédiat (low risk) :**
- ✅ #1 Token Counter — démarre J1
- ✅ #2 Cost Estimator — démarre après #1 si #1 ship sans douleur
- ⏸️ #9 Pyth REST — attendre validation Reddit
- ⏸️ #4 Semantic Cache — attendre validation
- ⏸️ #13 Oracle Anomaly — **exiger validation forte avant de coder** (effort 2 sem)

### Sprint code anticipé — API #1 Token Counter (J1-J5 = 28 avril - 2 mai)

- [x] **C1.1** (J1, 1h) : Setup repo `maxia-apis`, structure shared/, gitignore, README
- [x] **C1.2** (J1, 30 min) : Setup compte Railway ou Fly.io (Alexis)
- [x] **C1.3** (J2, 3h) : Extraction `token_estimator.py` → service standalone, tests TDD — 23 tests verts
- [x] **C1.4** (J3, 3h) : Endpoint FastAPI `/count-tokens`, OpenAPI doc, support multi-provider (OpenAI/Anthropic/Google/Cohere) — 36 tests verts
- [x] **C1.5** (J4, 2h) : Deploy Railway — https://maxia-apis-production.up.railway.app
- [x] **C1.6** (J5, 2h) : Listing RapidAPI — BASIC $0/500req · PRO $9/50k · ULTRA $29/500k
- [x] **C1.7** (J1, 1h) : Show HN posté → https://news.ycombinator.com/item?id=47931942

### J2 — 29 avril
- [ ] **Action 2.1** : lister sur **MicroAcquire** (clone du listing Acquire)
- [ ] **Action 2.2** : lister sur **Flippa** (catégorie SaaS code)
- [ ] **Action 2.3** : préparer FAQ acheteurs type (10 Q/R en texte)

### J3 — 30 avril
- [ ] **Action 3.1** : Post r/SaaS "Selling my LLM cost monitor backend, $X" (lien listings)
- [ ] **Action 3.2** : Post r/IndieHackers similaire
- [ ] **Action 3.3** : Si zéro contact en 60j → archiver code, briques réutilisables identifiées

**Phase 0 = max 2-3h total. Après, oublier BudgetForge.**

---

## PHASE 1 — Karma Reddit INCUBATION (Jours 1-21 en parallèle)

### ⚠️ État de départ réel (28 avril) :
- **Handle** : `Correct_Suspect_4513`
- **Karma** : 1 (compte quasi neuf)
- **Contributions** : 0
- **Conséquence** : shadow-ban quasi garanti si post dans subs sérieux avant J21

### Phase d'incubation OBLIGATOIRE — pas de post avant J21

| Période | Action | Subs cibles |
|---|---|---|
| **J1-J2** | Customiser profile (avatar + bio neutre courte) | — |
| **J1-J7** | **Commentaires uniquement** 3-5/jour, courts (50-200 chars) | r/AskReddit, r/NoStupidQuestions, r/explainlikeimfive, r/learnpython, r/CasualConversation, r/AskProgramming |
| **J7-J14** | Commentaires plus longs (200-500 chars) | r/Python, r/programming, r/webdev, r/learnpython |
| **J14-J21** | Premiers commentaires dans subs cibles | r/LLMDevs, r/LangChain, r/SaaS, r/IndieHackers |
| **J21+** | 1er vrai post validation API (si karma > 100) | r/LLMDevs en priorité |

### Règles karma (NON négociables)
- 0 lien dans les 14 premiers jours
- 0 mention de futurs produits
- Ratio 90/10 (90% utile, 10% promotion)
- Bio Reddit propre, **PAS** "founder of X"
- Pas plus de 5 commentaires/jour (suspect pour nouveau compte)

### Compteur karma (à updater)
- J1 départ : 1 karma
- Objectif J7 : 20-50 karma
- Objectif J14 : 100+ karma
- Objectif J21 : 200+ karma (seuil acceptable pour subs stricts)

### Routine quotidienne (15-20 min/jour, J1 → J21)
Chaque session, je prépare **3 commentaires prêts à copier** sur des threads actuels (je check les "Hot" du jour) :
- 1 dans un sub "easy karma" (AskReddit, ELI5, etc.)
- 1 dans un sub tech permissif (r/learnpython, r/AskProgramming)
- 1 dans un sub thématique selon phase

---

## PHASE 2 — Validation publique APIs (Jours 14-28)

**Objectif : valider 5 idées d'APIs SANS coder.**

### Top 5 APIs à valider (par ordre)

| # | API | Source code | Concurrent direct | Différenciateur testé |
|---|---|---|---|---|
| 1 | Token Counter Multi-Model | `budgetforge/services/token_estimator.py` | tiktoken (OpenAI only) | Multi-provider unifié REST |
| 2 | LLM Cost Estimator | `budgetforge/services/cost_calculator.py` + `dynamic_pricing.py` | LiteLLM (lib self-host) | API hostée + free tier |
| 9 | Pyth REST | `oracleforge/services/oracle/pyth_solana_oracle.py` | Pyth WebSocket only | REST + cache 1s |
| 4 | Semantic LLM Cache | `llmforge/services/cache.py` | GPTCache (lib) | API zero-setup |
| 13 | Oracle Anomaly Detection | `oracleforge/services/oracle/intelligence.py` | Chaos Labs ($$$$) | $99/mois vs $5k+ enterprise |

### Calendrier validation (1 API par 2 jours)

#### J14 (11 mai) — API #1 Token Counter
- [ ] **A14.1** : Landing page minimale Vercel "tokencounter.dev — coming soon, join waitlist"
- [ ] **A14.2** : Post r/LLMDevs : "Working on a unified token counter API (GPT/Claude/Gemini). Would you pay $9/mo for this? What features matter?"
- [ ] **A14.3** : Issue GitHub repo public "API Wishlist" pour Token Counter

**Signal min pour passer en code** : 10+ upvotes Reddit, 3+ comments engaged, 20+ emails waitlist

#### J16 (13 mai) — API #2 Cost Estimator
Idem méthode pour Cost Estimator (poster dans r/LLMDevs + r/LocalLLaMA)

#### J18 (15 mai) — API #9 Pyth REST
Post r/solana + r/ethdev "Why isn't there a simple REST for Pyth?"

#### J20 (17 mai) — API #4 Semantic Cache
Post r/LangChain + r/LLMDevs "Hosted semantic cache for LLM calls — viable?"

#### J22 (19 mai) — API #13 Oracle Anomaly
Post r/defi + r/ethdev "Affordable oracle anomaly detection for small protocols"

### J24-28 (21-25 mai) — Mesurer signal & décider

| API | Signal Reddit | Signal HN | Waitlist | Décision |
|---|---|---|---|---|
| #1 | __ | __ | __ | __ |
| #2 | __ | __ | __ | __ |
| #9 | __ | __ | __ | __ |
| #4 | __ | __ | __ | __ |
| #13 | __ | __ | __ | __ |

**Règle dure : tuer toute API avec <10 signals positifs cumulés.**

---

## PHASE 3 — Code APIs validées (Semaines 5-8 = 26 mai - 22 juin)

### Stack technique partagé (à coder S5 J1)

```
maxia-apis/
├── shared/
│   ├── auth.py          # API key validation (depuis authforge)
│   ├── rate_limit.py    # depuis budgetforge
│   ├── monitoring.py    # uptime + alerts
│   └── usage_tracker.py # log usage RapidAPI
├── apis/
│   ├── token_counter/    # extraction de budgetforge
│   ├── cost_estimator/   # extraction de budgetforge
│   ├── pyth_rest/        # extraction de oracleforge
│   ├── oracle_anomaly/   # extraction de oracleforge
│   └── semantic_cache/   # extraction de llmforge
└── deploy/
    ├── Dockerfile
    └── railway.toml      # OU fly.toml selon choix
```

### Semaine 5 (26 mai - 1 juin) — Sprint Quick Win

- [ ] **S5J1-J2** : Setup repo `maxia-apis`, structure shared/, deploy minimal
- [ ] **S5J3-J5** : API #1 Token Counter — extraction + endpoint + tests + OpenAPI
- [ ] **S5J6-J7** : Listing RapidAPI Token Counter + post Reddit launch

### Semaine 6 (2-8 juin) — API #2

- [ ] **S6J1-J5** : API #2 Cost Estimator — extraction + endpoint + tests
- [ ] **S6J6-J7** : Listing RapidAPI + cross-sell page avec #1

### Semaine 7 (9-15 juin) — API #9 + #4

- [ ] **S7J1-J3** : API #9 Pyth REST
- [ ] **S7J4-J7** : API #4 Semantic Cache

### Semaine 8 (16-22 juin) — API #13 (le gros)

- [ ] **S8J1-J7** : API #13 Oracle Anomaly Detection (le ticket premium)

### Tests obligatoires (TDD règle Alexis)
- 80%+ coverage par API
- Tests live (pas mocks pour les oracles)

---

## PHASE 4 — Launch coordonné (Semaines 9-10 = 23 juin - 6 juillet)

### Semaine 9 — Marketing intensif

- [ ] **S9J1** : Article technique Hashnode "How I built 5 APIs from one stack"
- [ ] **S9J2** : Article par API (5 articles techniques sur 5 jours)
- [ ] **S9J5** : ProductHunt launch groupé "5 APIs for AI/Web3 devs"
- [ ] **S9J6** : Show HN technique pour chaque API
- [ ] **S9J7** : Posts Reddit dans subs où signal positif Phase 1 — DM aux waitlist

### Semaine 10 — Iteration

- [ ] **S10** : Réponses au feedback launch, ajustements pricing/doc/features
- [ ] **S10J5** : Listing AlternativeTo + GitHub public-apis PR
- [ ] **S10J7** : Bilan métriques (revenu, clients, traction par API)

---

## PHASE 5 — Maintenance + audience (continu après J70)

### Routine hebdo (3-5h/sem)
- 30 min : update prix modèles LLM (mensuel mais check hebdo)
- 30 min : support tickets RapidAPI
- 30 min : monitoring uptime
- 1-2h : 1 article technique Hashnode/Dev.to
- 30 min : 5-10 réponses Reddit pour maintenir karma

### Métrique de succès (à updater)

| Mois | APIs live | MRR cible bas | MRR cible haut | MRR réel |
|---|---|---|---|---|
| Mois 1 (mai) | 0 (validation) | $0 | $0 | __ |
| Mois 2 (juin) | 4-5 | $50 | $500 | __ |
| Mois 3 (juillet) | 5 | $200 | $2 000 | __ |
| Mois 6 (octobre) | 5 + traction | $2 000 | $15 000 | __ |
| Mois 12 (avril 2027) | 5-7 + maturité | $5 000 | $30 000 | __ |

---

## DÉCISIONS CLÉS (à respecter sans relitige)

1. **BudgetForge en vente $5-15k**. Période 60j. Si invendu → archive.
2. **Twitter banni → Reddit principal** (en incubation 21j).
3. **0 call / 0 démo / 0 visio. Email OK** (correction 28 avril).
4. **Validation AVANT code** pour les grosses APIs. Code immédiat OK pour API #1 (low risk).
5. **Différenciateur explicite par API.** Doit être validable en 1 phrase.
6. **TJM freelance Track A : €550** (starter), monte à €700+ après reviews.
7. **3 domaines forts à mettre en avant** :
   - LLM cost optimization & multi-provider routing
   - AI agent infrastructure & RAG
   - Web3/DeFi oracles & price feeds
8. **Boîte mail outbound** : `support@maxiaworld.app` (vérifier alias OVH actif)
9. **Cold email outil** : Gmail manuel + Mailtrack free (5 emails/jour max au début)
10. **Plan hybride 4 tracks** : Freelance (A) + APIs (B) + Cold email (C) + BudgetForge vente (D).

---

## FICHIERS À METTRE À JOUR EN FIN DE CHAQUE SESSION

1. **Ce fichier** : cocher ✅ les actions faites
2. **HANDOFF.md** : résumé de la session (1 paragraphe)
3. **Memory `project_apis_pivot.md`** (à créer) : décisions importantes, métriques

---

## SI BLOQUÉ / CHANGEMENT MAJEUR

Modifier ce fichier, marquer la décision en haut "DÉCISION DU JJ-MM" avec rationale.

**Ne jamais abandonner silencieusement une étape sans noter pourquoi ici.**
