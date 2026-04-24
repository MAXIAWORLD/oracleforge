# BudgetForge — Plan de correction complet (audit 24/04/2026)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger les 21 findings identifiés lors de l'audit QA du 24 avril 2026 (Opus 4.7), rendre BudgetForge prod-ready sans risque de sécurité majeur.

**Architecture:** Corrections ciblées sur backend (services, routes, core) et dashboard. Aucune refactorisation architecturale. Chaque tâche correspond à un finding précis.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, SQLite WAL, slowapi, Stripe SDK, httpx, pytest, Next.js 14.

---

## Tableau récapitulatif

| ID | Gravité | Finding | Fichier(s) |
|---|---|---|---|
| A1 | CRITIQUE | Race condition inter-workers (asyncio.Lock cross-process) | `distributed_budget_lock.py`, `database.py`, `proxy_dispatcher.py` |
| A2 | CRITIQUE | Modèle inconnu → `cost=0` silencieux (spam $0) | `proxy_dispatcher.py`, `cost_calculator.py` |
| A3 | CRITIQUE | `except (ValueError, Exception)` trop large dans cost_calculator | `cost_calculator.py`, `dynamic_pricing.py` |
| A4 | CRITIQUE | `check_provider` + `downgrade_chain` fail-open sur JSON corrompu | `proxy_dispatcher.py` |
| A5 | CRITIQUE | `STRIPE_WEBHOOK_SECRET` absent du lifespan guard prod | `main.py` |
| B1 | HAUT | Rate limiting absent sur 9 proxys (Anthropic, Google…) | `routes/proxy.py` |
| B2 | HAUT | Cookie portal sans `iat` — non révocable (volé = 90j d'accès) | `routes/portal.py` |
| B3 | HAUT | Stripe webhook replay (pas de `event_id` dedup) | `routes/billing.py`, `core/models.py` |
| B4 | HAUT | Stripe webhook perdu → client payé, pas de projet créé | `routes/billing.py`, page `/success` |
| B5 | HAUT | Budget overshoot illimité si `max_cost_per_call_usd` non configuré | `routes/projects.py`, `proxy_dispatcher.py` |
| B6 | HAUT | Signup anti-abuse : 334 IPs = 1000 comptes free/jour | `routes/signup.py` |
| C1 | MOYEN→HAUT | SSRF DNS rebinding : `send_webhook` ne re-valide pas l'URL | `services/alert_service.py` |
| C2 | MOYEN | SQLite `database is locked` → 500 brut (doit retourner 503) | `main.py`, `database.py` |
| C3 | MOYEN | `finalize_usage` non-transactionnel — row bloqué à l'estimation si crash | `proxy_dispatcher.py` |
| C4 | MOYEN | Dashboard backend down → UI muette, aucune bannière d'erreur | `dashboard/app/page.tsx` |
| C5 | MOYEN | SMTP sans vérification TLS — magic links exfiltrables (MITM) | `services/onboarding_email.py` |
| C6 | MOYEN | `plan_quota` : `name == email` assumé — admin peut polluer la limite free | `services/plan_quota.py` |
| C7 | MOYEN | Stream Anthropic : `tokens_out=0` si provider omet `message_delta.usage` | `proxy_dispatcher.py` |
| C8 | MOYEN | XSS latent : `Project.name` libre côté admin, rendu non échappé à risque | `dashboard` |
| D1 | BAS | Timing attack sur lookup API key (2 SELECT observables) | `proxy_dispatcher.py` |
| D2 | BAS | Fichiers artefacts `=1.13` dans le repo | racine repo |

---

## Ce qui est solide (ne pas toucher)

1. **SSRF proxy** : URLs providers hardcodées dans `proxy_forwarder.py`. `X-Provider-Key` jamais interprétée comme URL.
2. **Signature Stripe webhook** : `stripe.Webhook.construct_event` utilisé correctement, 400 sur mismatch.
3. **SQL injection** : 100% ORM SQLAlchemy, aucune raw query.
4. **Isolation client** : une `bf-xxx` ne peut pas lire les projets d'un autre client.
5. **Portal magic link** : token 256 bits, TTL 1h, usage unique (delete on verify), HTTPOnly+SameSite=lax.

---

## Bloc A — CRITIQUE (ship-blockers, ordre obligatoire)

### A1 — Race condition inter-workers

**Problème :** `asyncio.Lock()` est par process. Avec 2 workers uvicorn, Worker A et Worker B lisent `used=$0.80` simultanément (budget=$1.00), tous deux décident `allowed=True`, tous deux prebill $0.30 → total $1.10 en DB.

**Solution :**
- `database.py` : ajouter `PRAGMA busy_timeout=30000` dans `_sqlite_pragma_on_connect`
- `proxy_dispatcher.py` / `prepare_request` : dans `async with budget_lock(project.id)`, ajouter `db.execute(text("BEGIN IMMEDIATE"))` avant `check_budget_model`

**Fichiers :** `core/database.py`, `services/proxy_dispatcher.py`, `services/distributed_budget_lock.py`

**Test :**
```python
@pytest.mark.asyncio
async def test_budget_not_exceeded_under_concurrent_load(client):
    proj = (await client.post("/api/projects", json={"name": "race-tight"})).json()
    await client.put(f"/api/projects/{proj['id']}/budget",
        json={"budget_usd": 0.00001, "alert_threshold_pct": 80, "action": "block"})
    FAKE = {"id": "x", "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    async def forward(*a, **kw):
        await asyncio.sleep(0.05)
        return FAKE
    with patch("services.proxy_forwarder.ProxyForwarder.forward_openai", new=forward):
        r1, r2 = await asyncio.gather(
            client.post("/proxy/openai/v1/chat/completions",
                json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
                headers={"Authorization": f"Bearer {proj['api_key']}"}),
            client.post("/proxy/openai/v1/chat/completions",
                json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
                headers={"Authorization": f"Bearer {proj['api_key']}"}),
        )
    statuses = sorted([r1.status_code, r2.status_code])
    assert 429 in statuses
```

**Commit :** `fix(budget): SQLite busy_timeout + BEGIN IMMEDIATE pour sérialiser check+prebill entre workers`

---

### A2 — Modèle inconnu → HTTP 400

**Problème :** `UnknownModelError` attrapée dans `prebill_usage` → `cost=0.0`. Un attaquant envoie un modèle inconnu → budget jamais atteint → spam gratuit.

**Solution :**
```python
# proxy_dispatcher.py / prebill_usage
# AVANT
except UnknownModelError:
    cost = 0.0

# APRÈS
except UnknownModelError:
    raise HTTPException(status_code=400,
        detail=f"Unknown model '{model}'. Configure pricing or use a supported model.")
```

**Fichiers :** `services/proxy_dispatcher.py`

**Test :**
```python
async def test_unknown_model_returns_400(client):
    proj = (await client.post("/api/projects", json={"name": "unknown-model"})).json()
    await client.put(f"/api/projects/{proj['id']}/budget",
        json={"budget_usd": 100.0, "alert_threshold_pct": 80, "action": "block"})
    resp = await client.post("/proxy/openai/v1/chat/completions",
        json={"model": "fake-model-xyz-99999", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": f"Bearer {proj['api_key']}"})
    assert resp.status_code == 400
    assert "unknown model" in resp.json()["detail"].lower()
```

**Commit :** `fix(proxy): modele inconnu → HTTP 400 au lieu de cost=0 silencieux`

---

### A3 — except trop large dans cost_calculator

**Problème :** `except (ValueError, Exception)` dans `cost_calculator.py:76` et `dynamic_pricing.py:155` avale toutes les pannes (timeout réseau, KeyError) → pricing cassé = `cost=0` invisible.

**Solution :**
- Remplacer `except (ValueError, Exception)` par `except UnknownModelError`
- Laisser remonter `httpx.TimeoutException`, `httpx.NetworkError`, `KeyError`
- Ajouter `except Exception as e: logger.error(...); raise` en dernier recours

**Fichiers :** `services/cost_calculator.py`, `services/dynamic_pricing.py` (si existe)

**Test :**
```python
async def test_pricing_network_error_raises_not_swallowed():
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("timeout")):
        with pytest.raises(Exception):
            await CostCalculator.compute_cost("gpt-4o", 100, 100)
```

**Commit :** `fix(cost): except trop large → laisser remonter les vraies pannes pricing`

---

### A4 — check_provider + downgrade_chain fail-closed

**Problème :** JSON invalide dans `allowed_providers` → `except json.JSONDecodeError: return` = fail-open (tous les providers autorisés silencieusement). Idem `downgrade_chain`.

**Solution :**
```python
# AVANT
except json.JSONDecodeError:
    return

# APRÈS
except json.JSONDecodeError:
    raise HTTPException(status_code=500,
        detail="Project config corrupted: allowed_providers contains invalid JSON")
```

```python
# AVANT (downgrade_chain)
except (json.JSONDecodeError, TypeError):
    pass

# APRÈS
except (json.JSONDecodeError, TypeError):
    raise HTTPException(status_code=500,
        detail="Project config corrupted: downgrade_chain contains invalid JSON")
```

**Fichiers :** `services/proxy_dispatcher.py`

**Test :**
```python
async def test_corrupted_allowed_providers_returns_500(client, db):
    from core.models import Project
    proj = (await client.post("/api/projects", json={"name": "corrupt"})).json()
    db.query(Project).filter(Project.id == proj["id"]).update({"allowed_providers": "not-json"})
    db.commit()
    resp = await client.post("/proxy/openai/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": f"Bearer {proj['api_key']}"})
    assert resp.status_code == 500
    assert "corrupted" in resp.json()["detail"].lower()
```

**Commit :** `fix(proxy): check_provider + downgrade_chain fail-closed sur JSON corrompu`

---

### A5 — Lifespan guard : STRIPE_WEBHOOK_SECRET

**Problème :** `main.py` vérifie `ADMIN_API_KEY` et `PORTAL_SECRET` en prod, mais pas `STRIPE_WEBHOOK_SECRET`. Si absent → faux événements `payment_succeeded` acceptés.

**Solution :**
```python
# main.py / lifespan
missing = [
    name for name, val in [
        ("ADMIN_API_KEY", settings.admin_api_key),
        ("PORTAL_SECRET", settings.portal_secret),
        ("STRIPE_WEBHOOK_SECRET", settings.stripe_webhook_secret),
    ] if not val
]
if missing:
    raise RuntimeError(f"Variables obligatoires manquantes en production: {', '.join(missing)}")
```

**Fichiers :** `backend/main.py`

**Commit :** `fix(startup): ajouter STRIPE_WEBHOOK_SECRET au guard production lifespan`

---

## Bloc B — HAUT (parallélisables)

### B1 — Rate limiting symétrique

**Problème :** Seul `/proxy/openai` a `@limiter.limit`. 9 autres endpoints sans limite.

**Solution :** Ajouter `@limiter.limit("30/minute;1000/hour")` + `request: Request` sur tous les endpoints proxy. Ollama : `"60/minute;2000/hour"` (local = gratuit).

**Bonus :** `key_func` combinant IP + Authorization header pour contrer la rotation IP.

**Fichiers :** `routes/proxy.py`

**Commit :** `fix(proxy): rate limiting symétrique sur tous les endpoints proxy`

---

### B2 — Cookie portal révocable

**Problème :** HMAC signé sur `email` seul, sans timestamp. Cookie volé = 90j d'accès garantis, aucune révocation.

**Solution :**
```python
# portal.py
import time

def _sign_session(email: str) -> str:
    iat = str(int(time.time()))
    payload = f"{email}|{iat}"
    sig = hmac.new(_portal_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"

def _verify_session(cookie: str) -> str | None:
    try:
        parts = cookie.rsplit("|", 1)
        if len(parts) != 2:
            return None
        payload, sig = parts
        expected = hmac.new(_portal_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        email, iat_str = payload.split("|", 1)
        int(iat_str)  # valider que c'est un entier
        return email
    except Exception:
        return None
```

**Fichiers :** `routes/portal.py`

**Commit :** `fix(portal): cookie session avec iat pour permettre invalidation temporelle`

---

### B3 — Stripe webhook idempotence

**Problème :** Même event rejoué → recrée un projet. Pas de table `stripe_events`.

**Solution :**
```python
# core/models.py
class StripeEvent(Base):
    __tablename__ = "stripe_events"
    event_id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
```

```python
# billing.py / stripe_webhook — au début, après signature OK :
existing = db.query(StripeEvent).filter(StripeEvent.event_id == event_id).first()
if existing:
    return {"ok": True}
db.add(StripeEvent(event_id=event_id, event_type=event_type))
db.commit()
```

**Fichiers :** `core/models.py`, `routes/billing.py`, `migrations/add_stripe_events.sql`

**Commit :** `fix(billing): idempotence Stripe via event_id dedup`

---

### B4 — Stripe webhook perdu : réconciliation /success

**Problème :** Webhook perdu → client payé, aucun projet créé. Page `/success` ne vérifie rien.

**Solution :**
```python
# billing.py — nouvel endpoint
@router.get("/api/billing/reconcile/{session_id}")
async def reconcile_checkout(session_id: str, db: Session = Depends(get_db)):
    session = stripe.checkout.Session.retrieve(session_id)
    if session.get("payment_status") not in ("paid", "no_payment_required"):
        raise HTTPException(status_code=402, detail="Payment not confirmed")
    await _handle_checkout_completed(dict(session), db)  # idempotent grâce à B3
    return {"ok": True}
```

Dashboard : page `/success?session_id=X` appelle `GET /api/billing/reconcile/{session_id}` à l'arrivée.

**Fichiers :** `routes/billing.py`, `dashboard/app/success/page.tsx`

**Commit :** `fix(billing): endpoint reconcile pour webhook Stripe perdu`

---

### B5 — Warning overshoot budget

**Problème :** `max_cost_per_call_usd` optionnel → 1 call peut coûter $500 sur un budget de $10.

**Solution :**
```python
# routes/projects.py / set_budget
warning = None
if project.max_cost_per_call_usd is None and project.budget_usd and project.budget_usd > 0:
    warning = ("Sans max_cost_per_call_usd, un seul appel coûteux peut dépasser votre budget. "
               "Recommandé : définir max_cost_per_call_usd ≤ budget_usd / 10.")
return BudgetResponse(..., warning=warning)
```

**Fichiers :** `routes/projects.py`, `dashboard/app/projects/[id]/page.tsx`

**Commit :** `fix(budget): warning si max_cost_per_call absent lors du set_budget`

---

### B6 — Signup rate limit par domaine email

**Problème :** 3 signups/jour/IP = 1000 comptes free/jour avec 334 IPs.

**Solution :**
- `core/models.py` / `SignupAttempt` : ajouter colonne `email_domain`
- `routes/signup.py` : `_check_domain_rate_limit(domain, db, max=10/jour)`

```python
def _check_domain_rate_limit(domain: str, db: Session, max_per_day: int = 10) -> bool:
    if not domain:
        return True
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    count = db.query(SignupAttempt).filter(
        SignupAttempt.email_domain == domain, SignupAttempt.created_at > cutoff
    ).count()
    return count < max_per_day
```

**Fichiers :** `routes/signup.py`, `core/models.py`

**Commit :** `fix(signup): rate limit par domaine email pour contrer rotation IP`

---

## Bloc C — MOYEN (robustesse)

### C1 — SSRF re-validation à l'envoi

**Problème :** `is_safe_webhook_url` appelé seulement à la création. DNS rebinding possible ensuite.

**Solution :**
```python
# services/alert_service.py / send_webhook — en premier
if not is_safe_webhook_url(url):
    logger.warning("Webhook URL blocked at send time (SSRF): %s", url)
    return False
```

**Fichiers :** `services/alert_service.py`

**Commit :** `fix(alert): re-valider URL webhook au moment de l'envoi (anti-DNS-rebinding)`

---

### C2 — SQLite busy → 503 propre

**Solution :**
```python
# main.py
class SQLiteBusyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except SAOperationalError as e:
            if "database is locked" in str(e):
                await asyncio.sleep(0.1)
                try:
                    return await call_next(request)
                except SAOperationalError:
                    return JSONResponse(status_code=503,
                        content={"detail": "Service temporarily busy, retry in 1s"},
                        headers={"Retry-After": "1"})
            raise
```

**Fichiers :** `backend/main.py`

**Commit :** `fix(db): middleware SQLite busy → 503 avec Retry-After`

---

### C3 — finalize_usage transactionnel + flag finalized

**Problème :** Crash entre prebill et finalize → row à l'estimation indéfiniment, aucun audit possible.

**Solution :**
- Ajouter colonne `finalized BOOLEAN DEFAULT 0` à `Usage`
- `finalize_usage` : SET `finalized=1` dans le même UPDATE
- Endpoint admin `GET /api/admin/unfinalized` : rows `finalized=0` depuis > 5min

**Fichiers :** `proxy_dispatcher.py`, `core/models.py`, `routes/admin.py`

**Commit :** `fix(usage): flag finalized + endpoint audit pour prebills orphelins`

---

### C4 — Dashboard : bannière backend down

**Problème :** `catch { /* ignore */ }` → dashboard muet si backend down.

**Solution :** Remplacer par `catch (e) { setBannerError("Service temporarily unavailable") }` + composant `<ErrorBanner>` visible.

**Fichiers :** `dashboard/app/page.tsx` (et toute page avec fetch silencieux)

**Commit :** `fix(dashboard): bannière erreur si backend indisponible`

---

### C5 — SMTP TLS strict

**Problème :** `SMTP` + `starttls()` sans contexte SSL → MITM possible, magic links exfiltrables.

**Solution :**
```python
import ssl
ctx = ssl.create_default_context()
# Si port 465 :
with smtplib.SMTP_SSL(host, port, context=ctx) as smtp:
    smtp.login(user, password)
    smtp.sendmail(...)
# Si port 587 :
with smtplib.SMTP(host, port) as smtp:
    smtp.starttls(context=ctx)
    smtp.login(user, password)
    smtp.sendmail(...)
```

**Fichiers :** `services/onboarding_email.py`

**Commit :** `fix(email): TLS strict avec vérification certificat SMTP`

---

### C6 — plan_quota : ne pas comparer name == email

**Problème :** `Project.name == email` assume name = email. Un admin peut nommer un projet `victim@x.com` et polluer la limite free d'un autre user.

**Solution :** Utiliser un champ `owner_email` dédié dans `Project`. Si absent → ajouter la colonne + migration. Filtrer sur `owner_email` dans `plan_quota.py`.

**Fichiers :** `services/plan_quota.py`, `core/models.py`

**Commit :** `fix(quota): filtrer par owner_email au lieu de name`

---

### C7 — Anthropic stream tokens_out undercount

**Problème :** Si `message_delta` absent mais `message_start` reçu → `tokens_out=0`, coût sous-estimé.

**Solution :** Fallback sur `estimate_output_tokens(payload)` si `tokens_out == 0` après le stream.

**Fichiers :** `services/proxy_dispatcher.py` / `_anthropic_stream_gen`

**Commit :** `fix(anthropic): fallback estimation tokens_out si message_delta absent`

---

### C8 — XSS latent

**Problème :** `Project.name` est un champ libre (côté admin). Tout rendu `dangerouslySetInnerHTML` ou attribut URL construit à partir de `name` serait XSS.

**Solution :** Auditer le dashboard — interdire `dangerouslySetInnerHTML` sur `project.name`. Valider que tous les usages passent par React (échappe par défaut). Ajouter ESLint rule `no-danger`.

**Fichiers :** `dashboard` (audit complet)

**Commit :** `chore(dashboard): audit XSS latent sur Project.name`

---

## Bloc D — BAS

**D1 — Timing attack API key** : non actionnable sans refonte (256 bits d'entropie, risque nul en pratique). Documenter uniquement dans `docs/security-notes.md`.

**D2 — Artefacts `=1.13`** :
```bash
git rm "budgetforge/backend/=1.13" "missionforge/backend/=1.13"
git commit -m "chore: supprimer artefacts pip mal interprétés"
```

---

## Ordre d'exécution recommandé

```
A1 → A2 → A3 → A4 → A5        (séquentiel, critiques — order matters)
B1   B2   B3   B4   B5   B6   (parallélisables)
C1   C2   C3   C4   C5   C6   C7   C8   (parallélisables, faible risque)
D1   D2                        (cosmétique, en dernier)
```

**Ship-blockers absolus : A1, A2, A3, A4, A5.**
Sans ces 5 corrections, BudgetForge n'est pas prod-ready.

---

## Résumé des fichiers modifiés

| Fichier | Tâche(s) |
|---|---|
| `core/database.py` | A1, C2 |
| `services/distributed_budget_lock.py` | A1 |
| `services/proxy_dispatcher.py` | A1, A2, A3, A4, C3, C7 |
| `services/cost_calculator.py` | A3 |
| `services/dynamic_pricing.py` | A3 |
| `services/alert_service.py` | C1 |
| `services/onboarding_email.py` | C5 |
| `services/plan_quota.py` | C6 |
| `core/models.py` | B3, B6, C3, C6 |
| `routes/billing.py` | A5→B3, B4 |
| `routes/portal.py` | B2 |
| `routes/proxy.py` | B1 |
| `routes/signup.py` | B6 |
| `routes/projects.py` | B5 |
| `routes/admin.py` | C3 |
| `main.py` | A5, C2 |
| `migrations/add_stripe_events.sql` | B3 |
| `dashboard/app/page.tsx` | C4 |
| `dashboard/app/success/page.tsx` | B4 |
| `dashboard/app/projects/[id]/page.tsx` | B5 |
| `dashboard` (audit) | C8 |
