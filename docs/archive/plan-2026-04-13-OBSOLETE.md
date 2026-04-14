> # ⚠️ DOCUMENT OBSOLÈTE — NE PLUS SUIVRE
>
> **Archivé le 14 avril 2026.** Ce plan OracleForge "from-scratch" est remplacé par `../plan-maxia-oracle-2026-04-14.md` qui acte le pivot vers **MAXIA Oracle** (extraction des modules oracle de MAXIA V12 au lieu d'une construction from-scratch). Raisons du pivot détaillées §1 du nouveau plan.
>
> Conservé ici uniquement pour traçabilité historique. Aucune session Claude ne doit exécuter ce document.
>
> Code from-scratch correspondant : archivé sous le tag git `oracleforge-v0-archive` + tarball `C:/Users/Mini pc/Desktop/maxia-lab-backups/oracleforge-v0-2026-04-14.tar.gz`.

---

# OracleForge — Plan de mise en production (OBSOLÈTE)

**Date** : 13 avril 2026
**Auteur** : Session Claude post-pivot (suite à la mise hors ligne de GuardForge)
**Statut** : ~~EN ATTENTE DE VALIDATION ALEXIS~~ **OBSOLÈTE — remplacé par plan-maxia-oracle-2026-04-14.md**

> ~~Ce document est la source de vérité pour la prochaine session sur OracleForge.~~ **Obsolète**, voir bandeau en haut.

---

## 1. Contexte du pivot

GuardForge a été déployé le 13 avril 2026 puis mis hors ligne le même jour, après audit honnête révélant :
- Détection PII regex-only (concurrents = ML/NLP — Presidio gratuit, Nightfall, Skyflow)
- Bug regex phone tronquant les numéros, vault tournant en in-memory en prod, SECRET_KEY exposé au client
- Marketing claims faux (AES-256 alors que Fernet/AES-128, "GDPR/HIPAA compliant" sans certification)
- Pas vendable en l'état sans 6-8 semaines de refonte (Presidio integration, auth user, billing wire, monitoring, backups)

Décision stratégique : **pause GuardForge**, **pivot OracleForge** parce que :
- API pure (pas de UI complexe à polir)
- Distribution via RapidAPI (gère billing, auth, analytics)
- Niche claire (devs crypto/DeFi/trading bots)
- Erreur produit = "prix légèrement off" et non "fuite de données client"
- Aucune claim compliance risquée
- Code existant déjà fonctionnel (audit ci-dessous)

GuardForge est en mode 503 (page maintenance) sur https://guardforge.maxiaworld.app — code, DB, cert, DNS conservés pour réactivation future éventuelle.

---

## 2. Audit réel d'OracleForge (vérifié 2026-04-13)

### Ce qui existe et fonctionne

| Composant | État vérifié |
|---|---|
| **Backend FastAPI** | `oracleforge/backend/main.py` propre, lifespan async, security middleware (X-API-Key) |
| **5 source integrations** | CoinGecko, Pyth Hermes, Chainlink (Base RPC), Yahoo Finance, Finnhub |
| **Tests** | **22 tests pytest passent** (mais tous mockés, aucun test live en CI) |
| **Sources testées en réel** | 4/5 fonctionnent : BTC ~$72340 sur CoinGecko/Pyth/Yahoo/Chainlink, écart $10, latence 30-170ms (Finnhub désactivé par défaut, nécessite API key gratuite) |
| **Confidence scoring** | Algorithme basé sur déviation max vs moyenne. <1% écart → 0.95+, >5% écart → <0.60 (anomalie) |
| **Circuit breaker per-source** | États CLOSED → OPEN → HALF_OPEN, threshold 3 failures, TTL 60s |
| **TTL cache** | 30s par défaut |
| **Endpoints** | `GET /api/price/{symbol}`, `POST /api/prices/batch` (≤50 symbols), `GET /api/sources`, `GET /api/cache/stats`, `GET /health` |
| **Dashboard Next.js** | 4 routes (`/`, `/prices`, `/sources`, `/cache`), 15 langues i18n |
| **Dockerfile + docker-compose** | Présents (pas testés) |
| **README** | 44 lignes, basique mais clair |

### Ce qui manque ou est faible

| Item | Sévérité |
|---|---|
| **Couverture symboles faible** : CoinGecko 21 cryptos, Pyth 8, Chainlink 2 (BTC/ETH only), Yahoo 10 cryptos + 6 stocks. Total unique ≈ 25 cryptos. Stocks support quasi-nul. | **HIGH** |
| **Tests purement mockés** — comme le bug GuardForge phone regex, des bugs réels resteront cachés jusqu'aux tests live | HIGH |
| **Sécurité dashboard** : probable même pattern `NEXT_PUBLIC_API_KEY` qu'on a fixé sur GuardForge (à vérifier) | HIGH |
| **Aucun déploiement** | — |
| **Aucune doc API publique** (Swagger/OpenAPI clean, exemples, integration guides) | MEDIUM |
| **Aucun marketing material** | MEDIUM |
| **Aucun monitoring/backup** | MEDIUM |
| **Pas de stress test** — comportement à 100/1000/10000 RPS inconnu | MEDIUM |
| **Rate limit côté providers** : CoinGecko free = 10-30 calls/min, Yahoo informel. Si trafic monte, blocages possibles. | MEDIUM |
| **Stocks mal couverts** : seulement Yahoo (non-officiel, peut casser) + Finnhub (60 calls/min payé). Pour vendre "stocks + crypto unifié", il faut probablement ajouter Alpha Vantage ou Twelve Data. | MEDIUM |
| **Pas de Docker test, pas de CI** | LOW |

### Comparaison concurrence (à valider, à NE PAS prendre comme vérité absolue sans recherche supplémentaire)

| Concurrent | Modèle | Pricing | Différence vs OracleForge |
|---|---|---|---|
| CoinGecko Pro | Single source | $129/mo (500/min) | Plus complet, mais 1 source = pas de cross-verification |
| CoinMarketCap Pro | Single source | $79-799/mo | Idem |
| CryptoCompare | Single source | $80-2400/mo | Idem |
| Polygon.io | Single source (stocks focus) | $29-200/mo | Idem |
| Alpha Vantage | Single source (stocks) | $50-250/mo | Idem |
| Pyth Network | On-chain oracle | Gratuit | Pas d'API REST consumer-friendly |
| Chainlink Data Feeds | On-chain oracle | Gratuit (gas only) | Idem, lecture on-chain uniquement |

**Positionnement défendable d'OracleForge** : "Multi-source price API with cross-verification confidence — never trust a single feed." Différentiateur réel = le confidence score basé sur l'agreement de plusieurs sources.

**Risque positionnement** : "cross-verification" est nice-to-have, pas must-have. Beaucoup de devs préfèrent payer 1 source fiable plutôt qu'un agrégateur. À tester en Phase 4.

---

## 3. Plan d'exécution — 4 phases, 4 checkpoints

**Principe directeur** : aucune promesse au-delà du checkpoint courant. À chaque fin de phase, Alexis valide explicitement "go" ou "stop" avant de continuer. Pas de momentum forcé.

---

### Phase 1 — Audit complet et durcissement (5-7 jours, exécution Claude)

**Objectif** : passer de "ça marche en démo" à "ça tient sous trafic réel".

| Jour | Action | Livrable |
|---|---|---|
| 1 | Audit live des 5 sources sur ≥50 symboles (cryptos majeurs + stocks majeurs). Mesurer disponibilité, latence p50/p95, taux d'erreur sur fenêtre 1h | `oracleforge/docs/source_audit.md` avec données réelles |
| 2 | Élargir mapping symboles : CoinGecko 21→100+, Pyth 8→50+, Chainlink → vérifier feeds Base/Ethereum mainnet, Yahoo crypto+stocks majeurs | `services/sources.py` mis à jour, tests de sources |
| 2 | Évaluation ajout Alpha Vantage ou Twelve Data pour vrais stocks (free tier 5 calls/min). Décision documentée. | Décision + intégration si retenue |
| 3 | Tests d'intégration LIVE (`tests/test_live_sources.py`) — vrais appels HTTP, exécutés manuellement (pas en CI pour ne pas spam les providers) | Test suite + rapport coverage |
| 3 | Audit regex/parsing à la manière du fix phone GuardForge — vérifier que chaque source parse correctement les edge cases | Bugs corrigés + tests de régression |
| 4 | Refactor sécurité dashboard : pattern server-side proxy `app/api/[...path]/route.ts` (même fix qu'aujourd'hui sur GuardForge), `GUARDFORGE_API_KEY` → `ORACLEFORGE_API_KEY` server-only | Dashboard sécurisé, grep .next/static = 0 leaks |
| 4 | Rate limiting + métriques `requests/source/min` exposées sur `/api/sources` | Métriques visibles dans le dashboard |
| 5 | Stress test : 100 → 1000 req/min sur backend local. Mesurer où ça casse (mémoire, threads, providers rate-limit) | `oracleforge/docs/load_test.md` |
| 5 | Documentation API : OpenAPI complet, description claire de chaque endpoint, 5 exemples curl/Python/JS, guide d'intégration | `oracleforge/docs/API.md` |
| 6-7 | Buffer pour bugs trouvés en cours de phase | — |

**🛑 Checkpoint 1 — fin Phase 1**

Questions à se poser honnêtement :
- ❓ Les 5 sources tiennent-elles 1000 req/min sans tomber ?
- ❓ Couverture symboles à ≥100 cryptos et ≥30 stocks ?
- ❓ Confidence score fiable sur cas réels (anomalie détectée si 1 source décale de 5%) ?
- ❓ Combien de bugs trouvés ? Si >5, on creuse encore (signe que le code n'a pas été testé sérieusement).
- ❓ Le pattern `NEXT_PUBLIC_API_KEY` a-t-il bien été fixé en server-side ?

**Si OUI à toutes** → Phase 2. **Si NON sur ≥1** → Phase 1 continuée, **pas** de move forward.

---

### Phase 2 — Deploy production VPS (3 jours, exécution Claude + 1 action Alexis)

| Jour | Action | Qui |
|---|---|---|
| 8 | Adaptation des fichiers deploy GuardForge à OracleForge : systemd backend (port 8003), systemd dashboard (port 3004 pour ne pas conflit avec 3003 réservé GuardForge), nginx vhost, deploy.sh idempotent | Claude |
| 8 | Préparation `oracleforge/deploy/` avec systemd units + scripts | Claude |
| **8** | **Ajouter record DNS chez OVH : `oracle.maxiaworld.app` (ou autre nom validé) → `146.59.237.43`** | **Alexis (5 min)** |
| 9 | Cert Let's Encrypt via webroot (même méthode no-downtime que GuardForge) | Claude |
| 9 | Déploiement systemd + démarrage services. Vérification que les 5 sources fonctionnent depuis le VPS (différent du local, IPs différentes) | Claude |
| 10 | Setup monitoring : UptimeRobot externe (gratuit) + Sentry pour erreurs (gratuit jusqu'à 5k events/mois) | Claude |
| 10 | Backup automatique SQLite quotidien dans `/opt/backups/oracleforge/` | Claude |
| 10 | Smoke tests E2E pendant 24h pour valider la stabilité | Claude (passif, monitoring) |

**🛑 Checkpoint 2 — fin Phase 2**

- ❓ Service stable 24h sans crash ?
- ❓ Les 5 sources sont-elles toutes UP depuis le VPS (les IPs de production ne sont pas rate-limit) ?
- ❓ Le monitoring détecte-t-il les erreurs simulées correctement ?
- ❓ Backup auto fonctionne ?

**Si OUI** → Phase 3. **Si NON** → debug avant de continuer.

---

### Phase 3 — RapidAPI listing et pricing (5-10 jours, mix Claude + Alexis)

| Action | Qui | Estimation |
|---|---|---|
| Créer compte RapidAPI Provider | Alexis | 15 min |
| Fournir URL API publique stable (`https://oracle.maxiaworld.app`) | Claude (déjà fait Phase 2) | — |
| Rédiger description API + endpoints + paramètres + responses + 5 exemples (curl, Python, JS, Go, PHP) | Claude | 4-6h |
| Définir pricing tiers (proposition à valider Alexis) | Alexis décide / Claude exécute | 1h discussion |
| Soumettre listing pour review | Alexis | 30 min |
| Attente review RapidAPI | RapidAPI | **2-7 jours (bloquant)** |
| Itérer si feedback RapidAPI (auth, format, doc) | Claude | variable |
| Listing live | — | — |

**Proposition pricing initiale** (à valider Alexis Checkpoint 3) :
- **Free** : 100 requêtes/jour, 5 symboles cryptos majeurs, sources_used max 2, pas de batch
- **Basic $9.99/mo** : 10 000 requêtes/mois, 50 symboles, batch jusqu'à 10
- **Pro $29/mo** : 100 000 requêtes/mois, tous symboles, batch jusqu'à 50, support email
- **Ultra $99/mo** : 1M requêtes/mois, priorité support, latence <100ms garantie

Logique : Free pour attirer l'essai, Basic accessible pour devs solo, Pro = sweet spot pour bots, Ultra = enterprise.

**🛑 Checkpoint 3 — listing approuvé**

- ❓ Listing visible et discoverable sur RapidAPI ?
- ❓ Free tier assez attirant pour générer des essais ?
- ❓ Pricing cohérent vs concurrence (CoinMarketCap Pro $79+, Polygon $29+) ?
- ❓ La doc OpenAPI est-elle générée correctement par RapidAPI à partir de notre OpenAPI ?

---

### Phase 4 — Soft launch et observation (2-3 semaines, mix)

| Semaine | Focus |
|---|---|
| Semaine 1 post-listing | Observer trafic naturel RapidAPI sans marketing actif. Mesurer : combien de free subs, combien de paid conversions, quels endpoints utilisés, taux d'erreur. |
| Semaine 2 | Si signal positif (>10 free subs sans marketing) : lancer marketing soft — Show HN, post r/cryptocurrency, post r/algotrading, threads Twitter dev. Si signal négatif : itérer le positionnement et la doc avant marketing. |
| Semaine 3 | Décision rationnelle : continuer à pousser OracleForge, OU pivoter sur un autre Forge, OU consolider GuardForge avec les leçons apprises. |

**🛑 Checkpoint 4 — 3 semaines post-listing**

Critères de décision honnête :
- ❓ Combien de revenus mensuels récurrents (MRR) ?
- ❓ Coût de support par client (heures/semaine) ?
- ❓ Demande organique (les gens trouvent le produit seuls) ou seulement trafic forcé par marketing ?
- ❓ Feedback qualitatif des premiers users (s'il y en a) ?

**Critère de coupure** : si **<5 paying customers après 3 semaines**, le produit ne décolle pas naturellement. Deux options :
- **Option A** : refonte marketing/positionnement, retry 3 semaines
- **Option B** : reconnaître que le marché est trop petit ou saturé, pivot

**Pas de marathon perdu**. Cinq euros de revenus n'est pas un signe à ignorer.

---

## 4. Estimations totales — réalistes

| Scénario | Délai jusqu'au premier $ entrant |
|---|---|
| **Optimiste** (zéro bug majeur, RapidAPI rapide, demande spontanée) | 3-4 semaines |
| **Réaliste** (1-2 bugs trouvés en Phase 1, RapidAPI 5 jours, ajustements doc) | **5-6 semaines** ← référence |
| **Pessimiste** (rebuild stocks support, RapidAPI rejette, refonte marketing) | 8-10 semaines |

**Compte sur 6 semaines, pas 3.**

---

## 5. Risques qui peuvent tuer ce plan (à connaître à l'avance)

1. **Rate-limit hostile des providers** (CoinGecko/Yahoo bloquent l'IP VPS quand trafic monte). Mitigation : proxies, ou payer CoinGecko Pro $129/mo.

2. **Pas de demande réelle** — "cross-verified prices" est un nice-to-have, pas un must-have. Si les devs préfèrent 1 source fiable, le produit ne décolle pas. **C'est le risque le plus important.** À tester froidement en Phase 4.

3. **RapidAPI rejette le listing** ou demande des changements majeurs (auth, pricing, doc). Pas dramatique, mais décale.

4. **Lassitude** — Phase 1-2 est invisible (pas de feedback externe). Risque que tu te lasses avant Phase 4. Mitigation : checkpoints partagés à voix haute.

5. **Bugs production majeurs** comme le vault GuardForge. Phase 2 inclut 24h de stabilité justement pour les attraper.

6. **Concurrence cachée** — il existe peut-être un OracleForge-like déjà sur RapidAPI qu'on n'a pas vu. Phase 3 inclut un check de listings existants avant submit.

---

## 6. Ce que Claude peut faire seul vs ce qu'Alexis doit faire

**Claude (autonome, sans Alexis)** :
- Phase 1 entière (audit, durcissement, sécurité, tests, doc API)
- Phase 2 deploy (sauf le record DNS qui demande l'accès panel OVH)
- Phase 3 partie technique (description API, examples code, intégration RapidAPI)
- Phase 4 monitoring + analyse des chiffres

**Alexis (~3h actives sur 6 semaines)** :
- Ajouter record DNS `oracle.maxiaworld.app` chez OVH (5 min)
- Créer compte RapidAPI Provider (15 min)
- Décider pricing avec Claude (1h)
- Soumettre listing pour review (30 min)
- Décider à chaque checkpoint (4× 15 min)
- Si décision marketing en Phase 4 : poster sur HN/Reddit (~1h par post)

---

## 7. Validation Alexis — 5 points à confirmer avant de démarrer

> **Tant qu'Alexis n'a pas validé ces 5 points, Claude ne touche à rien sur OracleForge.**

1. **Acceptation des checkpoints** — on s'arrête à chaque fin de phase et tu peux dire "non, on arrête". Pas de momentum forcé.
2. **Acceptation de l'estimation 6 semaines** comme baseline réaliste, pas comme promesse.
3. **Acceptation du critère de coupure Phase 4** — si <5 paying customers après 3 semaines, on regarde froidement et on pivot ou on arrête.
4. **Confirmation du nom de domaine** — `oracle.maxiaworld.app` ? `prices.maxiaworld.app` ? autre ?
5. **GuardForge reste en pause** pendant ces 6 semaines (pas de tentative parallèle de le ressusciter).

---

## 8. Notes pour la prochaine session Claude

- **Lire ce document AVANT de toucher quoi que ce soit** dans `oracleforge/`
- **Le checkpoint courant est `0` (validation Alexis)**. Aucun travail Phase 1 ne doit commencer tant qu'Alexis n'a pas confirmé les 5 points
- **GuardForge est OFFLINE** : `https://guardforge.maxiaworld.app` renvoie 503. Code, DB, secrets, cert et DNS conservés sur le VPS. Backup du vhost live à `/opt/guardforge/deploy/nginx-subdomain.conf.live`. Pour réactiver : restaurer ce fichier, reload nginx, restart les 2 systemd services
- **Mémoire MAXIA Lab** : la règle `feedback_never_lie.md` (mémoire critique) doit être respectée. Auditer avant d'affirmer. Dire "je ne sais pas" si on ne sait pas
- **VPS** : `ubuntu@maxiaworld.app` (146.59.237.43, OVH). Port 8003 réservé à OracleForge backend, port 3004 pour dashboard. MAXIA tourne sur 8000, GuardForge tournerait sur 8004/3003 si réactivé
