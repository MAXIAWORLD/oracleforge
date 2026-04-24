# Plan Argent — Forge Suite
> Dernière mise à jour : 2026-04-21
> Source : analyse marché + données concurrents vérifiées (Helicone, Portkey, Langfuse, CoinGecko, Clerk, AppSumo)

---

## Priorité 1 — BudgetForge (segment vide sur AppSumo)

### À qui vendre
| Persona | Douleur | Willingness to pay |
|---|---|---|
| Solo dev / indie hacker avec feature AI | Dépense $200-2K/mois en LLM, veut alertes + hard block | $29/mois |
| Agency gérant LLM pour clients | Multi-projets, visibilité, facturation client | $79/mois |
| CTO startup early-stage | 37% des boîtes dépensent >$250K/an en LLM, zéro visibilité | $79-99/mois |

### Pricing à activer
| Tier | Prix | Limite | Action |
|---|---|---|---|
| Free | $0 | 5K calls/mois, 1 projet | Déjà live — lead gen |
| **Pro** | **$29/mois** | 100K calls, alertes, projets illimités | **À activer maintenant** |
| **Agency** | **$79/mois** | 500K calls, multi-team, webhooks | **À activer maintenant** |
| AppSumo LTD | $69 tier 1 | ~2 ans de Pro lifetime | Canal lancement |

### Canaux par ordre de priorité
1. **Stripe / Lemon Squeezy direct** — marge 95%, à activer en premier
2. **AppSumo LTD** — acquisition client initiale, segment vide (aucun concurrent LLM budget actuellement sur AppSumo), marge ~30% pour nouveaux vendeurs
3. Product Hunt — awareness, audience dev, gratuit
4. HackerNews Show HN — après karma suffisant

### Revenue estimé
| Scénario | Clients | Gross | Net (direct 95%) |
|---|---|---|---|
| Direct conservateur | 50 clients Pro $29/mois | $1 450/mois | **$17K/an** |
| Direct moyen | 150 clients | $4 350/mois | **$52K/an** |
| AppSumo launch | 400 LTD × $69 | $27 600 gross | **~$8K net** (30%) |

### Benchmarks concurrents (prix vérifiés)
- Helicone : $79/mois (surtout observability, pas hard block)
- Portkey : $49/mois (idem)
- Langfuse : $29/mois (open-source, pas d'UI budget)
- LiteLLM : open-source, pas d'UI

**Différentiateur BudgetForge** : seul avec hard block + UI + hosted + multi-provider (OpenAI + Anthropic + Google + DeepSeek).

---

## Priorité 2 — OracleForge (x402 sous-monétisé)

### Problème actuel
x402 à $0.001/call = 3.8x plus cher que CoinGecko Analyst pour volumes normaux. Aucun abonnement = 0 client récurrent possible.

### À qui vendre
| Persona | Usage | Canal |
|---|---|---|
| Dev DeFi / dApp builder | Besoin multi-source redundancy | Discord DeFi communities |
| AI agent developer | Paiement autonome crypto → x402 parfait | Developer forums |
| Crypto startup | Data provider fiable et agrégé | Product Hunt |

### Pricing à ajouter (en complément du x402)
| Tier | Prix | Calls/mois | Notes |
|---|---|---|---|
| Free | $0 | 1K calls | Test/intégration |
| **Dev** | **$29/mois** | 100K calls | À créer |
| **Pro** | **$99/mois** | 500K calls | Benchmarké sur CoinGecko Analyst $129/mois |
| x402 | $0.001/call | Pay-per-call | Garder pour AI agents autonomes uniquement |

### Benchmarks concurrents (prix vérifiés)
- CoinGecko Basic : $35/mois / 100K calls
- CoinGecko Analyst : $129/mois / 500K calls ← benchmark direct
- CoinMarketCap Standard : $199/mois
- Pyth / Chainlink : pas d'API SaaS commerciale, on-chain seulement

**Différentiateur OracleForge** : seul agrégateur 6 sources (Pyth + Chainlink + Uniswap v3 + RedStone + CoinPaprika + Pyth Solana). Redondance maximale.

### Canaux
1. Direct (Stripe) — marge 95%
2. DeFi communities (The Defiant, Bankless, Discord Uniswap/Chainlink)
3. Product Hunt
4. **Pas AppSumo** — audience trop crypto-spécialisée, pas le bon marché

---

## Priorité 3 — AuthForge (niche étroite, déployer d'abord)

### Réalité du marché (sans langue de bois)
- Clerk : gratuit jusqu'à 50K MAU → barre quasi impossible à battre sur le grand marché
- Stytch : gratuit jusqu'à 10K MAU
- Auth0 : cher + décrié → opportunité sur le repricing mais marché enterprise

**USP réelle** : Clerk et Stytch sont JavaScript-first. AuthForge = Python / FastAPI natif. Seul sur ce segment.

### À qui vendre
Uniquement : développeurs Python buildant des APIs ou des microservices. Pas les app builders grand public.

### Pricing max viable
| Tier | Prix | Justification |
|---|---|---|
| Free | $0 | Obligatoire — Clerk l'impose |
| Pro | $9-15/mois | Rester compétitif sans se faire écraser |

### Canaux
1. Product Hunt (audience dev)
2. PyCoder's Weekly, Python Weekly (newsletters)
3. Reddit r/Python, r/FastAPI
4. **Pas AppSumo** — trop technique pour leur audience SMB

### Condition de go/no-go
Déployer sur VPS (port 8005), Product Hunt launch, 60 jours. Si <20 users payants → ne pas investir davantage.

---

## Priorité 4 — MissionForge (ne pas vendre avant P9/P10 fini)

### Marché AppSumo AI orchestration (données réelles)
| Produit | Prix tier 1 | Reviews | Rating | Note |
|---|---|---|---|---|
| AgenticFlow | $69 | 61 | 3.7/5 | Déçu l'audience |
| Diaflow | $89 | 48 | 3.83/5 | Moyen |
| Dart (AI project mgmt) | $59 | 56 | **4.62/5** | Seul bon score |
| t0ggles | $19 | 25 | 4.56/5 | Budget |

Dart est le benchmark : project management + AI bien intégré = seul bon rating. MissionForge doit atteindre ce niveau de polish.

### Condition de lancement
- [ ] Dashboard P9 complet (pas juste backend)
- [ ] QA complète (flows utilisateur réels, pas juste tests unitaires)
- [ ] Zéro bug critique

### Canaux quand prêt
1. Product Hunt
2. Show HN (karma 5+ requis)
3. AppSumo si positioning product management > orchestration technique

---

## Règles de go-to-market (valables pour tous les produits)

1. **Marge directe d'abord** : Stripe ou Lemon Squeezy (95% de marge) avant toute marketplace
2. **AppSumo = acquisition, pas revenus** : lance un LTD pour les utilisateurs, construis ton ARR en direct
3. **Free tier obligatoire** : sans free tier, le marché dev rejette le produit
4. **Un produit à la fois** : lancer BudgetForge payant → stabiliser → puis OracleForge → puis suite
5. **Segment vide > marché concurrentiel** : BudgetForge sur AppSumo est un segment vide, c'est la priorité

---

## Prochaines actions concrètes

| # | Action | Produit | Délai cible |
|---|---|---|---|
| 1 | Intégrer Stripe (Pro $29/mois + Agency $79/mois) | BudgetForge | Session suivante |
| 2 | Ajouter tiers abonnement ($29/$99/mois) | OracleForge | +1 semaine |
| 3 | Déployer VPS port 8005 | AuthForge | +1 semaine |
| 4 | Préparer dossier AppSumo (screenshots, démo vidéo) | BudgetForge | +2 semaines |
| 5 | Finir dashboard MissionForge P9/P10 | MissionForge | Après AuthForge |
| 6 | Product Hunt launch BudgetForge | BudgetForge | Après Stripe live |
