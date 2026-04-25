# Plan de correction — Audit 2026-04-25

**Source** : `audit-qa-senior-2026-04-25.md`
**Périmètre** : 60 findings (22 critiques, 26 hauts, 12 moyens)
**Objectif** : produit vendable et défendable techniquement avant ouverture early adopters payants.

## Stratégie globale

7 blocs séquentiels. Chaque bloc se termine par tests verts + déploiement + smoke test live. Pas de bloc B avant que A soit en prod. **Ne pas mélanger sécurité et features**.

```
B1 → B2 → B3 → B4 → B5 → B6 → B7
sec.    sec.    archi.  perf.   UX     test    doc
prod    pay     budget  scale   front  cov     ship
```

Estimation : **4 à 6 jours pleins** si tout va bien. **Réaliste : 8 à 10 jours** avec retours.

---

## BLOC 1 — Stop-the-bleeding sécurité (1 jour)

**But** : refermer les portes ouvertes critiques. Aucune nouvelle feature.

### B1.1 — Rate limiting cassé (C01)

**Fichier** : `backend/routes/proxy.py`

Inverser l'ordre des décorateurs sur 9 endpoints :

```
AVANT (cassé) :
@limiter.limit("30/minute;1000/hour")
@router.post("/proxy/anthropic/v1/messages")
async def proxy_anthropic(...)

APRÈS (correct) :
@router.post("/proxy/anthropic/v1/messages")
@limiter.limit("30/minute;1000/hour")
async def proxy_anthropic(...)
```

Vérifier : anthropic, google, deepseek, mistral, openrouter, ollama×2, together, azure-openai, aws-bedrock.

**Test** : test live `for i in 1..50; curl proxy/anthropic` → vérifier 429 après 30.

### B1.2 — Dashboard auth (C11, C12, C13)

**Fichier** : `dashboard/proxy.ts`

- Supprimer le fallback `?? "default-secret"` → raise si `NODE_ENV==='production' && !SESSION_SECRET`.
- Remplacer le HMAC fixe par un cookie signé (jwt-like) contenant `iat` + `exp`. Au minimum : générer un cookie aléatoire à chaque login et le stocker côté serveur (table session ou Redis).
- Ajouter `/clients` et toute route du sidebar à `PROTECTED_PATHS`. Mieux : passer en liste noire (tout protégé sauf `/`, `/login`, `/portal`, `/api/auth`).

### B1.3 — Dev mode et export full DB (C17, C22)

**Fichiers** : `backend/routes/export.py`, `backend/core/auth.py`, `backend/main.py`

- Dans `lifespan` (main.py), raise au démarrage si `app_env=='production' && !admin_api_key` (déjà partiel, vérifier).
- `routes/export.py:44-52` : `is_global_admin = x_admin_key == settings.admin_api_key` (retirer le fallback dev). Si pas de admin_key configuré ET pas en dev → 503.
- `routes/auth.py:require_admin` : conserver dev mode mais ajouter env var `BUDGETFORGE_ALLOW_DEV_MODE_BYPASS=1` requise pour ouvrir.

### B1.4 — CORS prod (H13)

**Fichier** : `backend/main.py:118-133`

Conditionner `allow_origins` :

```
if settings.app_env == "production":
    allow_origins = ["https://llmbudget.maxiaworld.app"]
else:
    allow_origins = ["http://localhost:3000", "http://localhost:3001", ...]
```

### B1.5 — request.client.host derrière proxy (H08)

**Fichier** : `backend/main.py`

Ajouter en tête :
```
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
```

Et configurer uvicorn avec `--proxy-headers --forwarded-allow-ips="*"` (ou IP nginx précise) côté systemd.

### B1.6 — Turnstile cohérence (H09)

Choix : **fail-closed**. Plus défensif.

**Fichier** : `backend/routes/signup.py:95-119`

```
if not secret:
    if settings.app_env == "production":
        raise HTTPException(status_code=503, detail="Anti-bot misconfigured")
    return True  # dev only
```

Synchroniser le commentaire main.py:71-75.

**Tests bloc 1** : `pytest backend/tests/test_admin_auth.py test_signup_*.py test_export.py test_proxy_rate_limit.py`

**Déploiement** : git commit, push, deploy.sh, smoke test live :
- `/api/proxy/anthropic` saturé à 30/min
- Cookie dashboard refusé sans SESSION_SECRET
- `/api/usage/export` 401 sans clé admin en prod

---

## BLOC 2 — Stripe + paiement (1 jour)

**But** : aucun client ne paie sans recevoir l'upgrade.

### B2.1 — Upgrade flow lié au projet existant (C14, C15)

**Fichier** : `backend/routes/billing.py`

Refactor `create_checkout_session` :
- Ajouter param `email` requis (depuis portal session ou body). Sans email connu → erreur.
- Passer `customer_email` à Stripe.
- Stocker en metadata : `{"plan": plan, "linked_email": email}`.

Refactor `_handle_checkout_completed` :
```
email = session["customer_details"]["email"]
existing = db.query(Project).filter(Project.name == email).first()
if existing:
    existing.plan = plan
    existing.stripe_customer_id = customer_id
    existing.stripe_subscription_id = subscription_id
    db.commit()
    # email = "votre plan a été upgradé"
else:
    # créer nouveau projet (cas où l'utilisateur n'avait pas signé en free)
    ...
```

### B2.2 — Subscription deleted = downgrade complet (C21)

**Fichier** : `backend/routes/billing.py:203-220`

Ajouter :
```
project.budget_usd = None  # reset budget config
# optionnel : rotate api_key pour révoquer accès si attaquant connaît la clé
project.previous_api_key = project.api_key
project.api_key = f"bf-{secrets.token_urlsafe(32)}"
project.key_rotated_at = now()
```

Envoyer email avec nouvelle clé (déjà fait via `send_downgrade_email`, ajouter la clé au template).

### B2.3 — Webhook HTTPS Slack/Office cassé (C16)

**Fichier** : `backend/services/alert_service.py:96-105`

Approche pragmatique : retirer le pinning IP et accepter le DNS rebinding TOCTOU côté webhook (impact faible : le webhook n'envoie qu'une payload de notification, pas de credentials sensibles). Garder la validation hostname via `is_safe_webhook_url` au moment de la config (déjà fait).

```
async with httpx.AsyncClient(
    timeout=5.0,
    follow_redirects=False,
    verify=(scheme == "https"),
) as client:
    await client.post(url, json=payload)
return True
```

Ou alternative : transport custom httpx qui vérifie cert contre `host_header`. Plus complexe, garder pour V2.

### B2.4 — Reconcile fragile (H25)

**Fichier** : `backend/services/stripe_reconcile.py`

Mapper price_id → plan via `core/config.py` (env vars existent déjà : `STRIPE_PRO_PRICE_ID`, `STRIPE_AGENCY_PRICE_ID`).

```
def _plan_from_price_id(price_id: str) -> str:
    if price_id == settings.stripe_agency_price_id: return "agency"
    if price_id == settings.stripe_pro_price_id: return "pro"
    return "free"
```

**Tests bloc 2** : `pytest backend/tests/test_billing.py test_stripe_*`

**Déploiement** : test live `/api/checkout/pro` → payer en mode test Stripe → vérifier project upgrade. Cancel subscription dans dashboard Stripe → vérifier downgrade + nouvelle clé email.

---

## BLOC 3 — Schéma DB + multi-projet (2 jours)

**But** : tenir la promesse "Pro = 10 projets, Agency = illimité".

### B3.1 — Ajouter `owner_email` (C19, C20)

**Migration Alembic** : `add_owner_email_to_projects.py`

```sql
ALTER TABLE projects ADD COLUMN owner_email VARCHAR;
CREATE INDEX ix_projects_owner_email ON projects(owner_email);
-- backfill : owner_email = name pour tous les projets existants
UPDATE projects SET owner_email = name;
-- garder name UNIQUE pour l'instant (slug du projet, à humaniser plus tard)
```

### B3.2 — Découpler `name` de `owner_email`

**Fichier** : `backend/core/models.py`, `backend/routes/signup.py`, `backend/routes/portal.py`, `backend/routes/billing.py`, `backend/services/plan_quota.py`

- `Project.name` reste unique (slug technique). Pour signup free : `name = f"{email}-{secrets.token_hex(4)}"` ou `name = email` initial.
- `Project.owner_email` indexé (pas unique).
- `signup_free` : crée `Project(name=email, owner_email=email)`.
- `_handle_checkout_completed` : trouve via `owner_email`, pas `name`.
- `portal_request`/`portal_verify` : query par `owner_email`.
- `plan_quota.check_project_quota` : `count(filter(owner_email==email))`.

### B3.3 — Endpoint POST /api/projects multi-tenant

**Fichier** : `backend/routes/projects.py`

Pour Pro/Agency : permettre de créer un nouveau projet à partir du portal (login email) :
- `POST /api/portal/projects` (auth = portal session, pas admin) : crée un projet avec `owner_email = session.email`. Vérifie quota plan.
- Le dashboard admin reste pour staff (création de N'IMPORTE quel projet).

### B3.4 — Frontend portal "Add project"

**Fichier** : `dashboard/app/portal/page.tsx`

Ajouter bouton "Create new project" si `plan != "free"` ou si `len(projects) < limit_for_plan`. Form simple : `name` (slug). Validation côté serveur.

### B3.5 — Mise à jour pricing page

**Fichier** : `dashboard/components/pricing-section.tsx`

Si après B3.1-3.4 le multi-projet ne marche toujours pas → retirer "10 projects" du texte Pro et passer à "1 projet" ou repousser cette fonctionnalité. **Ne pas vendre ce qui n'existe pas.**

**Tests bloc 3** : test_signup_quota.py (créer 2 projets free → 429), test_portal_create_project.py.

**Déploiement** : migration alembic en prod (backup DB AVANT — règle Alexis), déploiement, smoke test.

---

## BLOC 4 — Logique budget + race conditions (1.5 jour)

**But** : enforcement réel du budget, même sous charge.

### B4.1 — `budget_usd is None` = pas illimité par défaut (C07)

**Décision produit** : un projet `budget_usd = None` doit-il bloquer ou autoriser ?

Recommandation : **fail-closed**. Si pas de budget, le projet refuse les calls (HTTP 402 "Budget not set"). Forcer le user à setup.

**Fichier** : `backend/services/proxy_dispatcher.py:117-118`

```
if project.budget_usd is None:
    raise HTTPException(status_code=402, detail="Budget not configured. Set a budget in the dashboard.")
```

Pour les agency clients qui veulent vraiment "illimité" : ajouter `budget_usd = -1` comme sentinelle "illimité explicite" + warning dans le portal.

### B4.2 — Redlock token-based (C08)

**Fichier** : `backend/services/distributed_budget_lock.py:50-98`

```
import secrets
@asynccontextmanager
async def distributed_budget_lock(project_id, timeout=30.0):
    redis_client = await get_redis_client()
    if redis_client is None:
        raise ConnectionError("Redis not available")
    lock_key = f"budget_lock:{project_id}"
    token = secrets.token_urlsafe(16).encode()
    lock_ttl = 60
    acquired = await redis_client.set(lock_key, token, nx=True, ex=lock_ttl)
    if not acquired:
        # busy-wait avec polling
        ...
    try:
        yield
    finally:
        # Lua script pour delete-if-token-matches
        lua = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        await redis_client.eval(lua, 1, lock_key, token)
```

### B4.3 — flock O_NOFOLLOW + path safe (H02)

**Fichier** : `backend/services/distributed_budget_lock.py:114-117`

```
import os
def _acquire_file_lock(path: str):
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    fh = os.fdopen(fd, "w")
    _fcntl.flock(fh, _fcntl.LOCK_EX)
    return fh
```

Et déplacer les locks de `/tmp/` vers `/var/run/budgetforge/` ou `/run/user/<uid>/budgetforge/` (mkdir 0700 owned par l'utilisateur du service).

### B4.4 — Lock englobe finalize_usage (C10, H01)

**Fichier** : `backend/services/proxy_dispatcher.py`

Repenser : prebill et finalize devraient être atomiques par rapport aux check budgets concurrents. Solution simple : faire les comparaisons SUM(cost_usd) + check directement en SQL avec FOR UPDATE (pas SQLite-friendly), OU :

Refactor : tout le block `prepare_request` → `dispatch_*` → `finalize_usage` doit être idempotent par usage_id, et un `verifier` background fix les overshoots détectés.

Plus pragmatique : élargir le lock au moins jusqu'à `prebill_usage` + `finalize_usage` (pas l'appel LLM lui-même). Le lock est uniquement bloquant pour la phase comptable, pas pour la latence réseau LLM.

À discuter : pour l'instant **garder lock partiel + accepter overshoot ≤ estimate_error** (déjà couvert par cap_per_call). Documenter dans `audit-qa-senior` que c'est un compromis volontaire.

### B4.5 — Streaming finalize partiel (C09)

**Fichier** : `backend/services/proxy_dispatcher.py:446-450`

```
finally:
    if stream_error:
        if got_usage and tokens_out > 0:
            # On a au moins reçu de la sortie, finalize avec ce qu'on a
            await finalize_usage(db, usage_id, tokens_in, tokens_out, final_model)
        else:
            cancel_usage(db, usage_id)
        logger.warning("Stream error mid-flight for usage_id=%s: ...", usage_id)
    elif got_usage:
        await finalize_usage(db, usage_id, tokens_in, tokens_out, final_model)
    else:
        cancel_usage(db, usage_id)
    await _call_maybe_send_alert(project, db)
```

### B4.6 — should_alert vs _call_maybe_send_alert cohérence (H06)

**Fichier** : `backend/services/budget_guard.py:80-83` et `proxy_dispatcher.py:386-406`

Aligner : si `budget_usd <= 0` (= 0 ou None), pas d'alerte (pas de budget à atteindre). Modifier `should_alert` pour retourner `False` si `budget_usd <= 0`.

### B4.7 — Token estimator clamp (H05)

**Fichier** : `backend/services/token_estimator.py:198-200`

```
if max_tokens is not None:
    return min(max_tokens, MODEL_MAX_OUTPUT_TOKENS.get(model, 8192))
```

Ajouter `MODEL_MAX_OUTPUT_TOKENS` dict avec les vrais maxima (gpt-4o=16384, claude-opus=8192, etc.).

**Tests bloc 4** : test_budget_lock_redlock.py, test_streaming_partial_failure.py, test_budget_none_blocks.py.

**Déploiement** : tests de charge avec ab/wrk sur `/proxy/openai` à 100 RPS. Vérifier no overshoot, no race.

---

## BLOC 5 — AWS Bedrock (1 jour)

**Décision** : retirer ou réparer ?

Si Bedrock n'est pas vendu activement → **retirer** la route + supprimer du sidebar de modèles. Sinon réparation complète :

### B5.1 — Import correct (C03)

**Fichier** : `backend/services/aws_bedrock_client.py:5`

```
from core.config import settings
```

### B5.2 — Async via to_thread (C05)

**Fichier** : `backend/services/proxy_forwarder.py:325-354`

```
async def forward_aws_bedrock(request_body, api_key="", timeout_s=60.0):
    return await asyncio.to_thread(
        _forward_aws_bedrock_sync, request_body
    )

def _forward_aws_bedrock_sync(request_body):
    # logique boto3 synchrone
    ...
```

### B5.3 — API moderne `converse` (C06)

**Fichier** : `backend/services/aws_bedrock_client.py`

Remplacer `invoke_model` par `bedrock-runtime.converse()` (API unifiée Anthropic/Llama/etc., pas de format prompt à gérer).

```
response = client.converse(
    modelId=model_id,
    messages=messages_in_converse_format,
    inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
)
# response['usage'] contient inputTokens, outputTokens
# response['output']['message']['content'][0]['text'] contient la réponse
```

### B5.4 — Usage réel (C02)

Extraire `response.usage.inputTokens` et `outputTokens` dans le converti OpenAI :

```
return {
    "id": ...,
    "choices": [...],
    "usage": {
        "prompt_tokens": response['usage']['inputTokens'],
        "completion_tokens": response['usage']['outputTokens'],
        "total_tokens": response['usage']['totalTokens'],
    },
}
```

### B5.5 — Détection model par model_id (C04)

`convert_to_bedrock_format` : utiliser `model_id` (déjà passé en argument), pas `messages[0].content`. En converse API, plus besoin de format custom.

### B5.6 — Sentinelle "non configuré" propre (H18)

`aws_bedrock_client.is_configured()` → check `True/False`. Si False, `forward_aws_bedrock` retourne `HTTPException(503, "Bedrock not configured")` au lieu de `ValueError`.

**Tests bloc 5** : test_aws_bedrock_real_api.py (mock boto3 client) + test live avec vraie clé AWS staging.

**Déploiement** : si pas de clé AWS active → laisser route mais retourner 503. Communiquer clairement aux clients.

---

## BLOC 6 — Frontend + UX (1 jour)

### B6.1 — localStorage admin key (H12)

**Fichier** : `dashboard/lib/api.ts`, `dashboard/app/login/page.tsx`

Migration vers cookie HttpOnly :
- Login form POST `/api/auth` (next.js route) → set-cookie `bf_admin=<token>` HttpOnly samesite=strict.
- Backend FastAPI lit le cookie OR `X-Admin-Key` (compat).
- `lib/api.ts` ne lit plus localStorage. Cookie auto-envoyé via `credentials: 'include'`.

Si trop long : ajouter au minimum `expires` et invalidation forcée si `last_active > 24h`.

### B6.2 — Magic link en POST (H11)

**Fichiers** : `backend/routes/portal.py:212-236`, `dashboard/app/portal/page.tsx:147-165`

- Verify devient POST avec token en JSON body.
- Frontend : si query string `?token=...` détecté, faire fetch POST avec ce token, puis `replaceState` pour vider l'URL.

### B6.3 — Cookie portal samesite=strict + rotation 14j (H10)

**Fichier** : `backend/routes/portal.py:226-234`

```
_SESSION_MAX_AGE = 14 * 24 * 3600  # 14 jours
response.set_cookie(..., samesite="strict")  # si pas de cross-site magic-link nécessaire
```

À chaque endpoint qui valide la session, refresh le cookie (sliding window).

### B6.4 — Dashboard error state propre (H21, H23)

**Fichiers** : `dashboard/app/dashboard/page.tsx`, `dashboard/app/portal/page.tsx`

- Si `usage` fetch fail → afficher état "données indisponibles" sur la card concernée, ne pas compter dans atRisk/exceeded.
- Portal verify error → bouton "Renvoyer un lien" qui pré-remplit l'email.

### B6.5 — API key masking dashboard (M06)

**Fichier** : `dashboard/app/projects/[id]/page.tsx:526-545`

```
{showKey ? project.api_key : `${project.api_key.slice(0, 8)}...${project.api_key.slice(-4)}`}
<button onClick={() => setShowKey(v => !v)}>{showKey ? "Hide" : "Show"}</button>
```

### B6.6 — saveBudget warning display (M07)

**Fichier** : `dashboard/app/projects/[id]/page.tsx:445-462`

```
const result = await api.projects.setBudget(...);
if (result.warning) showToast(`⚠ ${result.warning}`);
else showToast("Budget saved");
```

**Tests bloc 6** : `npm test` dashboard, e2e Playwright sur les flows critiques.

**Déploiement** : test manuel — login dashboard, magic link portal, set budget, voir warning.

---

## BLOC 7 — Hardening admin + tests (1 jour)

### B7.1 — Members admin escalation (H15)

**Fichier** : `backend/routes/members.py:36-46`

Ajouter check : seul un caller authentifié via `settings.admin_api_key` (clé globale) peut créer un member admin. Member admin compromis ne peut créer que des viewers.

```
def create_member(payload, x_admin_key, db):
    is_global_admin = hmac.compare_digest(x_admin_key, settings.admin_api_key)
    if payload.role == "admin" and not is_global_admin:
        raise HTTPException(403, "Only the global admin can create admin members")
    ...
```

### B7.2 — Settings smtp restrictions (H16)

**Fichier** : `backend/routes/settings.py`

Ajouter validation hostname : domaine non-IP, pas dans `_BLOCKED_HOSTNAMES`. Idéalement : whitelist via env (`ALLOWED_SMTP_HOSTS=smtp.sendgrid.net,smtp.gmail.com,...`).

### B7.3 — CSV injection (H14)

**Fichier** : `backend/routes/export.py:90-108`

```
def _safe_csv_cell(val):
    s = str(val) if val is not None else ""
    if s and s[0] in "=+-@\t\r":
        s = "'" + s
    return s

writer.writerow({k: _safe_csv_cell(v) for k, v in row.items()})
```

### B7.4 — Export streaming (C18)

**Fichier** : `backend/routes/export.py`

Remplacer `.all()` par `.yield_per(1000)` :

```
def generate_csv():
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    yield output.getvalue()
    output.seek(0); output.truncate()
    
    for u in q.yield_per(1000):
        writer.writerow(...)
        if output.tell() > 4096:
            yield output.getvalue()
            output.seek(0); output.truncate()
    if output.tell() > 0:
        yield output.getvalue()
```

### B7.5 — Retry backoff (H24)

**Fichier** : `backend/services/proxy_dispatcher.py:489-512`

```
import asyncio
for attempt in range(max_retries + 1):
    try:
        ...
    except Exception as e:
        last_exc = e
        if attempt < max_retries:
            await asyncio.sleep(min(2 ** attempt, 10))  # exponential backoff cap 10s
```

### B7.6 — PortalRevokedSession purge (M05)

Ajouter cron systemd ou cleanup au démarrage :

```
def cleanup_old_revoked_sessions(db):
    cutoff = datetime.now() - timedelta(days=90)
    db.query(PortalRevokedSession).filter(
        PortalRevokedSession.revoked_at < cutoff
    ).delete()
    db.commit()
```

### B7.7 — Plan limits documentés (M12)

**Fichier** : `backend/services/plan_quota.py:7-17`

Ajouter docstring source : "Limits set 2026-04-22, validation client interview pending. Sources: ..."

### B7.8 — Tests live obligatoires

Suite de tests live à ajouter dans `tests/test_live_*.py` (skip si pas de clés) :
- `test_live_openai_real_call` : fais un vrai call OpenAI 3 tokens, vérifie cost ~ $0.0001
- `test_live_anthropic_streaming_finalize` : streaming complet, vérifie usage updaté
- `test_live_stripe_webhook_full_flow` : reproduit signup-free → checkout pro → webhook → upgrade
- `test_live_portal_magic_link` : signup → request → verify → access projects

**Déploiement** : final smoke test, puis go-live.

---

## Suivi

À chaque fin de bloc :
1. Tests verts (`pytest -v`)
2. Commit avec message `fix(audit): bloc N — <résumé>`
3. Push
4. `bash deploy.sh` (avec backup auto comme corrigé après incident 22 avril)
5. Smoke test manuel sur prod
6. Update `audit-qa-senior-2026-04-25.md` : marquer findings résolus avec ✅ + date
7. Update `HANDOFF.md` avec état actuel

## Critères de "vendable"

Bloc obligatoire avant ouverture early adopters :
- ✅ B1 (sécurité critique)
- ✅ B2 (paiement fiable)
- ✅ B4 (budget enforcement réel)
- ✅ B5 ou retirer Bedrock
- ✅ B6.4-6.6 (UX errors, masking)
- ✅ B7.3-7.4 (CSV injection, OOM export)

Bloc recommandé mais reportable :
- B3 (multi-projet) — ou retirer la promesse "10 projets" du pricing
- B6.1-6.3 (localStorage migration) — XSS catastrophique mais aujourd'hui dépend d'une autre faille pour exploiter
- B7.1, B7.2 (members + smtp) — admin compromise déjà = game over

## Ce qui ne peut PAS attendre

Si le temps manque, **B1 + B2 + B4.1 + B4.5 + B5 (retrait au minimum)** sont les blockers absolus. Tout le reste est nuance.
