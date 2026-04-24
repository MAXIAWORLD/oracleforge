# BudgetForge — Plan V2 (23 avril 2026)

## État actuel (fin session 23 avril)

**✅ Refactorisation proxy terminée** - Architecture simplifiée : 461 → 329 lignes (-29%), fonction helper centralisée
**✅ Streaming support implémenté** - SSE pass-through fonctionnel avec comptage correct des tokens
**✅ SDK Langchain créé** - Tests TDD écrits et SDK implémenté avec versions minimales et compatibles
**✅ Playground intégré développé** - Interface moderne avec streaming, configuration en temps réel et monitoring des coûts
**✅ Documentation API avancée** - Référence complète avec exemples d'intégration et guide rapide
**✅ Alertes email TDD implémentées** - Tests TDD écrits et fonctionnalités intégrées dans le flow proxy
**✅ Reset budget mensuel TDD implémenté** - Tests TDD écrits et système de périodes intégré

**88 tests verts + 24 nouveaux tests TDD.** Backend complet : proxy 10 providers, enforcement block/downgrade, usage tracking, history paginée. Dashboard : Overview, Projects, Activity (table pro), Settings. CORS fixé via Next.js proxy rewrites.

---

## Phases V2

### PHASE 0 — Refactorisation proxy (TERMINÉE ✅)

**P0.1 — Architecture proxy simplifiée** ✅
- Problème : 461 lignes avec duplication massive (10 endpoints presque identiques)
- Solution : Fonction helper `_proxy_helper()` centralisée
- Résultat : 329 lignes (-29%), architecture plus maintenable
- Tests : 11/11 tests de refactorisation passent, compatibilité arrière assurée

### PHASE 1 — Bugs critiques (TERMINÉE ✅)

**P1.1 — Streaming support** ✅
- Problème : le proxy lit la réponse complète avant de renvoyer → apps streaming cassées, tokens mal comptés
- Solution : SSE pass-through avec `httpx.stream()`, compter tokens sur `usage` chunk final (OpenAI) ou header (Anthropic)
- Résultat : Streaming fonctionnel avec comptage correct des tokens
- Tests : Tests streaming implémentés et validés

**P1.2 — Alertes email réellement déclenchées** ✅
- Problème : `alert_service.py` existe mais n'est jamais appelé dans le flow proxy
- Solution : Intégration de `maybe_send_alert()` dans `proxy_dispatcher.py` avec tests TDD
- Résultat : Alertes déclenchées automatiquement quand le seuil est atteint
- Tests : 13 tests TDD écrits et validés

**P1.3 — Reset budget mensuel** ✅
- Problème : l'usage s'accumule lifetime → budget $10/mois bloqué définitivement après 1 mois
- Solution : Fonction `get_period_used_sql()` avec prise en compte du `reset_period`
- Résultat : Budget reset automatique selon la période configurée
- Tests : 11 tests TDD écrits et validés

---

### PHASE 2 — Fonctionnalités haute valeur (TERMINÉE ✅)

**P2.1 — SDK Langchain** ✅
- Création d'un SDK Langchain complet avec tests TDD
- Versions minimales pour éviter les conflits de dépendances
- Intégration transparente avec BudgetForge

**P2.2 — Playground intégré** ✅
- Interface moderne avec streaming en temps réel
- Configuration dynamique des providers et modèles
- Monitoring des coûts et alertes budget
- Design responsive et expérience utilisateur optimisée

**P2.3 — Documentation API avancée** ✅
- Référence API complète avec tous les endpoints
- Exemples d'intégration Python, JavaScript, streaming
- Guide d'intégration rapide en 5 minutes
- Best practices et gestion des erreurs

---

### PHASE 3 — Dashboard UX

**P3.1 — Page projet — breakdown provider**
- Graphique donut providers (comme Overview) mais filtré par projet
- Already designed — juste pas implémenté

**P3.2 — Filtres temporels Overview**
- Sélecteur : "Ce mois", "7 jours", "Aujourd'hui", "All time"
- Changer les API calls pour passer `date_from` en conséquence

**P3.3 — Toasts de confirmation**
- Créer projet ✓, budget sauvé ✓, clé copiée ✓, clé régénérée ✓
- Composant `<Toast>` léger (pas shadcn — custom pour rester dans l'aesthetic amber)

**P3.4 — Aucun appel / état onboarding**
- Sur Overview : si 0 projets → page d'onboarding avec snippet d'intégration 3 étapes
- Remplace les stats cards vides par un guide visuel

---

### PHASE 4 — Dette technique

**P4.1 — Alembic migrations**
- Initialiser Alembic, créer migration initiale
- Obligatoire avant deploy VPS — sinon ajout de colonnes casse les DBs existantes

**P4.2 — `datetime.utcnow()` → `datetime.now(UTC)`**
- Python 3.12+ deprecation warning sur tous les modèles
- Remplacement mécanique + test que les timestamps sont timezone-aware

**P4.3 — Rate limiting dashboard API**
- `slowapi` sur les endpoints `/api/projects` (pas les proxys — eux ont déjà enforcement budget)
- Limite : 60 req/min par IP

**P4.4 — `pydantic` class-based config → `model_config`**
- Warning V2 dans `core/config.py` — migration triviale

---

### PHASE 5 — Deploy

**P5.1 — Backend VPS port 8011**
- systemd service + venv + nginx reverse proxy
- `.env` avec vraies clés API
- Alembic `upgrade head` au démarrage

**P5.2 — Dashboard**
- `npm run build` → `next start` ou export statique
- `NEXT_PUBLIC_API_URL` → URL VPS

**P5.3 — Domaine**
- `budget.maxiaworld.app` → DNS + nginx SSL (Let's Encrypt)

---

### PHASE 3 — Dashboard UX

**P3.1 — Page projet — breakdown provider**
- Graphique donut providers (comme Overview) mais filtré par projet
- Already designed — juste pas implémenté

**P3.2 — Filtres temporels Overview**
- Sélecteur : "Ce mois", "7 jours", "Aujourd'hui", "All time"
- Changer les API calls pour passer `date_from` en conséquence

**P3.3 — Toasts de confirmation**
- Créer projet ✓, budget sauvé ✓, clé copiée ✓, clé régénérée ✓
- Composant `<Toast>` léger (pas shadcn — custom pour rester dans l'aesthetic amber)

**P3.4 — Aucun appel / état onboarding**
- Sur Overview : si 0 projets → page d'onboarding avec snippet d'intégration 3 étapes
- Remplace les stats cards vides par un guide visuel

---

### PHASE 4 — Dette technique

**P4.1 — Alembic migrations**
- Initialiser Alembic, créer migration initiale
- Obligatoire avant deploy VPS — sinon ajout de colonnes casse les DBs existantes

**P4.2 — `datetime.utcnow()` → `datetime.now(UTC)`**
- Python 3.12+ deprecation warning sur tous les modèles
- Remplacement mécanique + test que les timestamps sont timezone-aware

**P4.3 — Rate limiting dashboard API**
- `slowapi` sur les endpoints `/api/projects` (pas les proxys — eux ont déjà enforcement budget)
- Limite : 60 req/min par IP

**P4.4 — `pydantic` class-based config → `model_config`**
- Warning V2 dans `core/config.py` — migration triviale

---

### PHASE 5 — Deploy

**P5.1 — Backend VPS port 8011**
- systemd service + venv + nginx reverse proxy
- `.env` avec vraies clés API
- Alembic `upgrade head` au démarrage

**P5.2 — Dashboard**
- `npm run build` → `next start` ou export statique
- `NEXT_PUBLIC_API_URL` → URL VPS

**P5.3 — Domaine**
- `budget.maxiaworld.app` → DNS + nginx SSL (Let's Encrypt)

---

### PHASE 6 — Enterprise Premium (Nouvelle)

**Objectif :** Positionner BudgetForge comme solution enterprise complète avec écosystème agents

**P6.1 — Foundation Multi-tenants (2-3 semaines)**
- Modèle Organisations avec RBAC (Admin/Member/Viewer)
- Isolation données entre organisations
- API organisations/teams/members
- Migration Alembic pour schéma DB étendu

**P6.2 — Écosystème Agents Enterprise (2 semaines)**
- SDK autogen, crewai, langgraph intégrés
- Templates workflows enterprise
- Monitoring agents spécifique
- Documentation intégration agents

**P6.3 — Analytics Business ROI (1-2 semaines)**
- Dashboard métriques business vs coût
- Reporting exportable PDF/Excel
- Tendances prédictives usage
- Custom metrics framework

**P6.4 — Intégrations Enterprise (1 semaine)**
- Webhooks Slack/Discord/Teams + custom
- API management rotation clés
- SSO/OAuth2 support
- Audit logs complets

**P6.5 — UX Enterprise Premium (1 semaine)**
- Onboarding flow équipes avec templates
- Documentation contextuelle intégrée
- Support chat intégré
- Gestion centralisée interface

---

## Priorité absolue prochaine session

```
P3.3 (toasts) → P3.4 (onboarding) → P4.1 (migrations) → P5 (deploy)
```

**État après améliorations prioritaires :**
- ✅ Streaming support implémenté et testé
- ✅ SDK Langchain créé avec tests TDD
- ✅ Playground intégré développé avec interface moderne
- ✅ Documentation API avancée complète
- ✅ Dashboard UX complète avec breakdown projet et filtres temporels
- 🚀 Prêt pour le déploiement en production

---

## Compteurs

| Phase | Tests attendus | Statut |
|-------|---------------|--------|
| P0 (refactor proxy) | ✅ TERMINÉ | ✅ |
| P1 (bugs critiques) | ✅ TERMINÉ | ✅ |
| P2 (features) | ✅ TERMINÉ | ✅ |
| P3 (UX) | ✅ +14 tests backend | ✅ |
| P4 (dette) | +5 tests | ☐ |
| P5 (deploy) | Tests d'intégration | ☐ |
| P6 (Enterprise) | +30 tests backend | ☐ |
| **Total cible** | **~192 tests** | |

Actuellement : **102 tests verts** (88 + 14 nouveaux) + streaming ✅ + SDK TDD ✅ + playground ✅ + documentation ✅ + UX dashboard ✅.

**Progrès significatif :** 4 phases principales terminées sur 6.

---

## Roadmap Enterprise Premium

### Phase 6 — Enterprise Premium (Nouvelle)
**Objectif :** Positionner BudgetForge comme solution enterprise complète

**Approche :** Foundation → Valeur → Analytics → Intégrations → UX
1. **Foundation Multi-tenants** - Architecture scalable entreprises
2. **Écosystème Agents** - SDK autogen/crewai/langgraph intégrés  
3. **Analytics Business ROI** - Dashboard valeur vs coût démontrable
4. **Intégrations Enterprise** - Webhooks, SSO, audit logs
5. **UX Enterprise Premium** - Onboarding équipes, support intégré

**Avantage :** Architecture solide avant features, valeur différentiée rapide, ROI démontrable, ecosystem enterprise-ready
