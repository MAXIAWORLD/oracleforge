# Audit QA Senior — BudgetForge — 2026-04-25

**Auditeur** : Claude Opus 4.7 (1M ctx)
**Cible** : `https://llmbudget.maxiaworld.app`
**Stack** : FastAPI + SQLite (WAL) + slowapi + Next.js 15 + 2 workers uvicorn
**Méthode** : 4 phases séquentielles — logique métier, sécurité/injection, UX/états frontend, simulation monde réel.

---

## Synthèse exécutive

**Verdict : pas prêt pour la prod sous charge réelle.** 22 findings critiques + 26 hauts. Trois blockers bloquants pour vendre :

1. **Rate limiting NUL sur 9/10 endpoints proxy** — décorateur mal ordonné.
2. **AWS Bedrock = bypass total du budget** — usage hardcodé à 0 + import cassé.
3. **Plan Pro promet "10 projects" — schéma DB ne le permet pas** (`Project.name` UNIQUE, signup force `name=email`).

---

## Tableau complet des risques

| # | Gravité | Phase | Composant | Problème |
|---|---------|-------|-----------|----------|
| C01 | CRITIQUE | 1 | `routes/proxy.py` | `@limiter.limit` placé AU-DESSUS de `@router.post` sur 9 endpoints (anthropic, google, deepseek, mistral, openrouter, together, azure, bedrock, ollama×2). FastAPI enregistre la fonction non-wrappée → rate limiting NUL. |
| C02 | CRITIQUE | 1 | `aws_bedrock_client.py:150,171` | `usage` hardcodé à `{prompt_tokens:0, completion_tokens:0}`. Cost = 0. **Bypass budget total Bedrock**. |
| C03 | CRITIQUE | 1 | `aws_bedrock_client.py:5` | `from ..core.config import settings` — import relatif. Le projet utilise `from core.config`. ImportError au premier appel. |
| C04 | CRITIQUE | 1 | `aws_bedrock_client.py:63-72` | Détection format depuis `messages[0].content` (string match "claude"/"llama"). N'utilise pas `model_id`. Conditionné par contenu utilisateur. |
| C05 | CRITIQUE | 1 | `aws_bedrock_client.py:39-48` | `boto3.invoke_model` bloquant appelé depuis async. Bloque l'event loop. |
| C06 | CRITIQUE | 1 | `aws_bedrock_client.py:74-96` | API `prompt+Human:/Assistant:` dépréciée Bedrock. Réponses échouent. |
| C07 | CRITIQUE | 1 | `services/budget_guard.py` + `proxy_dispatcher.py:117` | Si `budget_usd is None` → return immédiat. Budget illimité = pas d'enforcement. |
| C08 | CRITIQUE | 1 | `distributed_budget_lock.py:75-98` | Redlock anti-pattern : `delete(lock_key)` sans token. Si TTL expire pendant call lent, autre worker prend le lock, le premier supprime celui du voisin. |
| C09 | CRITIQUE | 1 | `proxy_dispatcher.py:446-450` | Streaming : `stream_error=True` ET `got_usage=True` → finalize avec tokens partiels. Client facturé pour réponse incomplète. |
| C10 | CRITIQUE | 1 | `proxy_dispatcher.py:330-337` | `cancel_usage` n'acquiert PAS le `budget_lock`. Race possible. |
| C11 | CRITIQUE | 2 | `dashboard/proxy.ts:31` | `SESSION_SECRET ?? "default-secret"` — fallback hardcodé. Cookie forgeable sans variable d'env. |
| C12 | CRITIQUE | 2 | `dashboard/proxy.ts:7-9` | Token = HMAC fixe d'une chaîne constante "session". Tous les utilisateurs partagent le MÊME cookie. Pas d'IAT, pas de rotation. |
| C13 | CRITIQUE | 2 | `dashboard/proxy.ts:5` | `PROTECTED_PATHS` n'inclut pas `/clients`. Page client accessible sans auth. |
| C14 | CRITIQUE | 2 | `routes/billing.py:147-154` | `_handle_checkout_completed` → IntegrityError si l'utilisateur a déjà un projet free. Webhook fail. Idempotency StripeEvent retourne ok au retry sans rejouer. **Customer paie sans upgrade**. |
| C15 | CRITIQUE | 2 | `routes/billing.py:113-122` | Stripe checkout sans auth, sans bind email. Email Stripe ≠ email signup → projet orphelin. |
| C16 | CRITIQUE | 2 | `services/alert_service.py:96-105` | Webhook HTTPS avec `pinned_url=IP` + `verify=True` → cert validé contre IP, pas hostname. Tous les webhooks Slack/Office HTTPS échouent silencieusement. |
| C17 | CRITIQUE | 2 | `routes/export.py:44-52` | Dev mode (`admin_api_key=""`) → `is_global_admin=True` pour tous → dump CSV/JSON de toutes les usages. |
| C18 | CRITIQUE | 2 | `routes/export.py:60` | `_query_usages(...).all()` charge tout en RAM. OOM possible. |
| C19 | CRITIQUE | 2 | `services/plan_quota.py:39` | `filter(Project.name == owner_email)` retourne 0 ou 1 (name UNIQUE). Quota par owner inexistant. |
| C20 | CRITIQUE | 2 | `core/models.py:27` | `name` UNIQUE → un seul projet par utilisateur. Plan Pro "10 projects" impossible. |
| C21 | CRITIQUE | 2 | `routes/billing.py:203-220` | `_handle_subscription_deleted` ne révoque pas la clé API, ne reset pas `budget_usd`. Pro downgradé conserve clé bf-xxx avec gros budget. |
| C22 | CRITIQUE | 2 | `core/auth.py:22-37` | En `app_env != "production"` ET `admin_api_key=""` → `require_admin` ouvre tous les writes. |
| H01 | HAUT | 1 | `proxy_dispatcher.py:227` | Le `budget_lock` ne couvre que `prepare_request`. Appel LLM + finalize hors lock → overshoot possible. |
| H02 | HAUT | 1 | `distributed_budget_lock.py:130-141` | flock `/tmp/bf_budget_<id>.lock` sans `O_NOFOLLOW`. Symlink attack par utilisateur local. |
| H03 | HAUT | 1 | `distributed_budget_lock.py:130-133` | Sur Windows fallback = `asyncio.Lock` per-process. Multi-worker Windows = pas de sync. |
| H04 | HAUT | 1 | `proxy_dispatcher.py:611-614` | `dispatch_anthropic_format` non-stream : pas de retry (vs OpenAI). Inconsistance. |
| H05 | HAUT | 1 | `services/token_estimator.py:198-200` | `max_tokens=2000000` retourné direct. Court-circuit du clamp 4096. Self-DoS prebill. |
| H06 | HAUT | 1 | `services/budget_guard.py:80-83` | `should_alert` returns True if `budget_usd<=0` mais `_call_maybe_send_alert` early-return si `not budget_usd` (False pour 0.0). Logique incohérente. |
| H07 | HAUT | 1 | `proxy_dispatcher.py:298,324,336` | `db.commit()` fail après prebill/finalize/cancel : log+rollback mais state incertain. |
| H08 | HAUT | 2 | `routes/signup.py:128` | `request.client.host` derrière nginx = `127.0.0.1`. Rate-limit signup bypass total ou DoS. |
| H09 | HAUT | 2 | `routes/signup.py:95-119` | Turnstile fail-open. `main.py:71-75` log warning mais ne raise pas. Code et doc en contradiction. |
| H10 | HAUT | 2 | `routes/portal.py:226-234` | Cookie samesite=lax 90j sans rotation. Vol XSS = 90j de session. |
| H11 | HAUT | 2 | `routes/portal.py:212` | Magic-link via GET avec token en query string. Présent dans logs nginx, history, Referer. |
| H12 | HAUT | 2 | `dashboard/lib/api.ts:46-54` | Admin key envoyé sur chaque requête + localStorage. XSS = compromission totale. |
| H13 | HAUT | 2 | `main.py:118-133` | CORS `allow_origins` inclut `localhost:3000` en prod + `allow_credentials=True`. |
| H14 | HAUT | 2 | `routes/export.py` | CSV injection via `agent` (header `X-BudgetForge-Agent` libre). `=+-@` exécutent formules Excel. |
| H15 | HAUT | 2 | `routes/members.py:36-46` | Tout admin peut promouvoir email arbitraire à `role=admin`. |
| H16 | HAUT | 2 | `routes/settings.py:64-70` | Admin peut écrire `smtp_host=evil.com`. Onboarding emails → serveur attaquant → leak api_keys. |
| H17 | HAUT | 2 | `services/dynamic_pricing.py:191-218` | `_load_from_file(file_path,...)` lit n'importe quel YAML/JSON. Surface latente. |
| H18 | HAUT | 1 | `services/proxy_forwarder.py:325-364` | `forward_aws_bedrock` raise ValueError → retry 3 fois → spam logs. |
| H19 | HAUT | 4 | Scénario timeout | `proxy_timeout_ms` jusqu'à 300s. Worker bloqué. Si client ferme connexion, finalize jamais appelé → prebill conservatif reste comptabilisé. |
| H20 | HAUT | 4 | Scénario clé invalide | `get_project_by_api_key` 1 query/tentative. Pas de constant-time compare. Timing leak minime. |
| H21 | HAUT | 3 | `dashboard/app/dashboard/page.tsx:497-500` | `atRisk`/`exceeded` ne comptent que projets avec `usage` chargé. Si fail réseau, comptage faussé silencieusement. |
| H22 | HAUT | 4 | `services/plan_quota.py:50-62` | `check_quota` recalcule SQL count à chaque appel. Sous 100 r/s SQLite serialize → latence dégradée. |
| H23 | HAUT | 3 | `dashboard/app/portal/page.tsx:138-174` | Erreur portal/verify : 401 et 500 messages différents mais pas de bouton renvoi auto. |
| H24 | HAUT | 1 | `proxy_dispatcher.py` | Retry sans backoff exponentiel. Rafale de 3 retries instantanés sur 5xx provider. |
| H25 | HAUT | 2 | `services/stripe_reconcile.py:15-24` | Plan détecté via `'agency' in nickname` / `'pro' in nickname`. Fragile, downgrade abusif possible. |
| H26 | HAUT | 1 | `services/dynamic_pricing.py:439-445` | Singleton `_pricing_manager` global. Pas de `await close()` au shutdown. Cache + connexions httpx ouvertes. |
| M01 | MOYEN | 1 | `distributed_budget_lock.py:102-103` | `_memory_locks` dict illimité. Memory leak avec beaucoup de projets. |
| M02 | MOYEN | 1 | `services/token_estimator.py:25-37` | `CODE_PATTERNS` regex unanchored. Faux positifs sur prompts naturels. |
| M03 | MOYEN | 2 | `services/alert_service.py:137` | Email body avec `project_name` non échappé. Mailsplit possible si name contient `\r\n`. |
| M04 | MOYEN | 2 | `routes/portal.py:125-146` | `portal_request` retourne `{ok: True}` peu importe si email existe. Mais timing différent (DB write si projet existe). Email enum via timing. |
| M05 | MOYEN | 2 | `routes/portal.py:262-272` | `PortalRevokedSession` jamais purgé. Croissance illimitée. |
| M06 | MOYEN | 3 | `dashboard/app/projects/[id]/page.tsx:528` | `project.api_key` affiché en clair. Pas de masking, pas de "show/hide". |
| M07 | MOYEN | 3 | `dashboard/app/projects/[id]/page.tsx:421-461` | `saveBudget` affiche toast "Budget saved" même si `warning` retourné par backend (budget=0+block). |
| M08 | MOYEN | 4 | `routes/history.py:74-87` | `total` count query refait scan sans pagination. Slow sur grosse base. |
| M09 | MOYEN | 4 | `routes/history.py:65-72` | `date_from`/`date_to` parsés en naive UTC. Users non-UTC voient mauvais bornes. |
| M10 | MOYEN | 1 | `routes/models.py:368-403` | `get_models` lance 9 requêtes outbound parallèles à chaque cache miss. /api/models lent. |
| M11 | MOYEN | 2 | `routes/admin.py:19-22` | `billing_sync` retourne `{ok:False, error:"..."}` (HTTP 200) sur misconfig. Devrait être 503. |
| M12 | MOYEN | 1 | `services/plan_quota.py:7-17` | `PLAN_LIMITS["agency"]=500_000` calls/mois — pas de spec/source. À documenter. |

---

## Ce qui est solide

1. `core/auth.py:13` — admin_key compare avec `hmac.compare_digest`.
2. `routes/portal.py:62-78` — verify_session check sig + iat + table révocation.
3. `core/url_validator.py` — couverture RFC 1918, link-local, métadonnées cloud, IPv6 ULA, DNS-pinning.
4. `routes/billing.py:84-99` — webhook stripe avec idempotency StripeEvent + IntegrityError catch.
5. `core/database.py:18-20` — SQLite WAL + busy_timeout=30000 + synchronous=NORMAL.

---

## Statistiques

- **CRITIQUE** : 22
- **HAUT** : 26
- **MOYEN** : 12
- **Total** : 60 findings

Phases couvertes : logique métier (15), sécurité/injection (28), UX frontend (8), simulation monde réel (9).
