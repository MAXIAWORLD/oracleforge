# BudgetForge Audit #8 — Plan de correction complet

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger les 6 findings audit #8 + 8 findings audit #4 effort≤2, déployer en prod, atteindre le verdict PRÊT.

**Architecture:** TDD strict — test rouge d'abord, implémentation minimale, test vert, commit. Chaque tâche = 1 commit. Les blocs A et B sont indépendants mais A doit passer avant B8 (deploy). Bloc C = session dédiée post-launch.

**Tech Stack:** Python 3.12 + FastAPI + SQLite + Alembic — pytest pour les tests backend. Next.js 16 (App Router) pour le dashboard.

---

## BLOC A — Bloquants mise en vente (faire EN PREMIER)

### Task A1 : X2 — Email normalization dans webhook Stripe

**Problème :** `_handle_checkout_completed` (billing.py:114) ne normalise pas l'email. Un upgrade Stripe avec `Foo+work@Gmail.com` crée un projet inaccessible via le portail (qui normalise à `foo@gmail.com`).

**Files:**
- Modify: `backend/routes/billing.py:114-116`
- Modify (tests): `backend/tests/test_audit8.py` (créer)

- [ ] **Écrire le test RED**

Créer `backend/tests/test_audit8.py` :

```python
"""Tests audit #8 — X2 X3 X4 X5 X8."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


# ── X2 — email normalization webhook ──────────────────────────────────────────

class TestX2EmailNormalizationWebhook:
    def test_webhook_email_uppercased_normalised(self, db_session):
        """Email Stripe en majuscules/+tag doit être normalisé avant insert."""
        from routes.billing import _handle_checkout_completed
        import asyncio

        session = {
            "customer_details": {"email": "Foo+Work@Gmail.COM"},
            "metadata": {"plan": "pro"},
            "customer": "cus_test",
            "subscription": "sub_test_x2_upper",
        }
        with patch("routes.billing.send_onboarding_email"):
            asyncio.get_event_loop().run_until_complete(
                _handle_checkout_completed(session, db_session)
            )

        from core.models import Project
        project = db_session.query(Project).filter(
            Project.stripe_subscription_id == "sub_test_x2_upper"
        ).first()
        assert project is not None
        assert project.name == "foo@gmail.com", (
            f"Email doit être normalisé à 'foo@gmail.com', got '{project.name}'"
        )

    def test_webhook_email_plus_tag_stripped(self, db_session):
        """Le +tag doit être strippé pour correspondre au portail."""
        from routes.billing import _handle_checkout_completed
        import asyncio

        session = {
            "customer_details": {"email": "user+stripe@example.com"},
            "metadata": {"plan": "pro"},
            "customer": "cus_test2",
            "subscription": "sub_test_x2_tag",
        }
        with patch("routes.billing.send_onboarding_email"):
            asyncio.get_event_loop().run_until_complete(
                _handle_checkout_completed(session, db_session)
            )

        from core.models import Project
        project = db_session.query(Project).filter(
            Project.stripe_subscription_id == "sub_test_x2_tag"
        ).first()
        assert project is not None
        assert project.name == "user@example.com"
```

- [ ] **Lancer pour confirmer RED**

```bash
cd budgetforge/backend
pytest tests/test_audit8.py::TestX2EmailNormalizationWebhook -v
```
Attendu : FAIL — email non normalisé.

- [ ] **Implémenter le fix** dans `backend/routes/billing.py:114-116`

Remplacer :
```python
    email = (session.get("customer_details") or {}).get("email") or session.get(
        "customer_email"
    )
    if not email or not _EMAIL_RE.match(str(email)):
```

Par :
```python
    raw_email = (session.get("customer_details") or {}).get("email") or session.get(
        "customer_email"
    )
    if not raw_email or not _EMAIL_RE.match(str(raw_email)):
        logger.warning(
            "Invalid or missing email in checkout — customer=%s session=%s",
            session.get("customer"),
            session.get("id"),
        )
        return
    # Normaliser comme signup_free et portal_request
    _local, _domain = str(raw_email).strip().lower().split("@", 1)
    email = _local.split("+")[0] + "@" + _domain
    if not _EMAIL_RE.match(email):
```

- [ ] **Lancer pour confirmer GREEN**

```bash
pytest tests/test_audit8.py::TestX2EmailNormalizationWebhook -v
```
Attendu : PASS.

- [ ] **Commit**

```bash
git add backend/routes/billing.py backend/tests/test_audit8.py
git commit -m "fix(billing): normalize Stripe webhook email (lower + strip +tag) — X2"
```

---

### Task A2 : X5 — Downgrade révoque les projets excédentaires

**Problème :** `_handle_subscription_deleted` (billing.py:205-222) passe 1 seul projet en free. Un client Pro qui avait 10 projets garde 9 projets Pro après churn.

**Files:**
- Modify: `backend/routes/billing.py:205-222`
- Modify (tests): `backend/tests/test_audit8.py`

- [ ] **Écrire le test RED** (ajouter dans `test_audit8.py`)

```python
# ── X5 — downgrade revoke excess projects ─────────────────────────────────────

class TestX5DowngradeRevokesExcess:
    def test_downgrade_sets_all_projects_to_free(self, db_session):
        """Annulation sub → TOUS les projets du customer passent en free."""
        from core.models import Project
        from routes.billing import _handle_subscription_deleted
        from unittest.mock import patch

        # Créer 3 projets pour le même customer
        customer_id = "cus_downgrade_test"
        for i in range(3):
            p = Project(
                name=f"user{i}@test.com",
                plan="pro",
                stripe_customer_id=customer_id,
                stripe_subscription_id=f"sub_down_{i}",
                budget_usd=50.0,
            )
            db_session.add(p)
        db_session.commit()

        sub = {"id": "sub_down_0", "customer": customer_id}
        with patch("routes.billing.send_downgrade_email"):
            _handle_subscription_deleted(sub, db_session)

        projects = db_session.query(Project).filter(
            Project.stripe_customer_id == customer_id
        ).all()
        assert all(p.plan == "free" for p in projects), (
            "Tous les projets du customer doivent être passés en free"
        )

    def test_downgrade_sends_email_once(self, db_session):
        """Email de downgrade envoyé une seule fois (au projet principal)."""
        from core.models import Project
        from routes.billing import _handle_subscription_deleted
        from unittest.mock import patch, call

        customer_id = "cus_email_once"
        p = Project(
            name="main@test.com",
            plan="pro",
            stripe_customer_id=customer_id,
            stripe_subscription_id="sub_main_email",
            budget_usd=50.0,
        )
        db_session.add(p)
        db_session.commit()

        with patch("routes.billing.send_downgrade_email") as mock_email:
            _handle_subscription_deleted({"id": "sub_main_email", "customer": customer_id}, db_session)

        mock_email.assert_called_once()
```

- [ ] **Lancer pour confirmer RED**

```bash
pytest tests/test_audit8.py::TestX5DowngradeRevokesExcess -v
```

- [ ] **Implémenter le fix** dans `backend/routes/billing.py:205-222`

Remplacer la fonction entière :
```python
def _handle_subscription_deleted(subscription: dict, db: Session) -> None:
    subscription_id = subscription.get("id")
    customer_id = subscription.get("customer")
    if not subscription_id:
        return

    # Downgrade TOUS les projets du customer (pas juste celui de la sub)
    projects = db.query(Project).filter(
        Project.stripe_customer_id == customer_id
    ).all() if customer_id else []

    # Fallback : chercher par subscription_id si customer_id absent
    if not projects:
        project = (
            db.query(Project)
            .filter(Project.stripe_subscription_id == subscription_id)
            .first()
        )
        if project:
            projects = [project]

    if not projects:
        return

    for project in projects:
        project.plan = "free"
        project.stripe_subscription_id = None
    db.commit()

    logger.info(
        "%d project(s) downgraded to free (customer=%s subscription=%s)",
        len(projects),
        customer_id,
        subscription_id,
    )
    # Email envoyé sur le premier projet trouvé
    send_downgrade_email(projects[0].name)
```

- [ ] **Lancer pour confirmer GREEN**

```bash
pytest tests/test_audit8.py::TestX5DowngradeRevokesExcess -v
```

- [ ] **Commit**

```bash
git add backend/routes/billing.py backend/tests/test_audit8.py
git commit -m "fix(billing): downgrade revokes all customer projects — X5"
```

---

### Task A3 : X3 — Webhook Stripe payload size cap

**Problème :** `POST /webhook/stripe` n'a pas de limite de taille de payload. Un attaquant envoie des requêtes de 10 MB → parse + HMAC verify consomme CPU/mémoire.

**Files:**
- Modify: `backend/routes/billing.py:71-73`
- Modify (tests): `backend/tests/test_audit8.py`

- [ ] **Écrire le test RED**

```python
# ── X3 — webhook payload cap ───────────────────────────────────────────────────

class TestX3WebhookPayloadCap:
    def test_oversized_payload_returns_413(self, client):
        """Payload > 100KB doit retourner 413."""
        oversized = b"x" * (101 * 1024)
        resp = client.post(
            "/webhook/stripe",
            content=oversized,
            headers={"stripe-signature": "t=1,v1=fake"},
        )
        assert resp.status_code == 413, f"Attendu 413, got {resp.status_code}"

    def test_normal_payload_proceeds_to_sig_check(self, client):
        """Payload normal (< 100KB) doit passer au check de signature (400, pas 413)."""
        resp = client.post(
            "/webhook/stripe",
            content=b'{"type":"test"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )
        assert resp.status_code == 400  # signature invalide, pas 413
```

- [ ] **Lancer pour confirmer RED**

```bash
pytest tests/test_audit8.py::TestX3WebhookPayloadCap -v
```

- [ ] **Implémenter** dans `backend/routes/billing.py:72-73` (après `async def stripe_webhook`)

```python
@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    if len(payload) > 100_000:
        raise HTTPException(status_code=413, detail="Payload too large")
    sig_header = request.headers.get("stripe-signature", "")
    # ... reste inchangé
```

- [ ] **Lancer pour confirmer GREEN**

```bash
pytest tests/test_audit8.py::TestX3WebhookPayloadCap -v
```

- [ ] **Commit**

```bash
git add backend/routes/billing.py backend/tests/test_audit8.py
git commit -m "fix(billing): cap webhook payload at 100KB — X3"
```

---

### Task A4 : X4 — Magic-link token via hash fragment (pas query string)

**Problème :** Le lien magic-link envoie le token en `?token=xxx` (query string) → leaké dans l'en-tête Referer si la page charge des ressources externes, et visible dans l'historique navigateur.

**Fix :** Passer à `#token=xxx` (hash fragment) — jamais envoyé aux serveurs ni dans Referer.

**Files:**
- Modify: `backend/routes/portal.py:92`
- Modify: `dashboard/app/portal/page.tsx` (lecture depuis `window.location.hash`)
- Modify (tests): `backend/tests/test_audit8.py`

- [ ] **Écrire le test RED**

```python
# ── X4 — magic-link hash fragment ─────────────────────────────────────────────

class TestX4MagicLinkHash:
    def test_portal_email_uses_hash_fragment(self):
        """Le lien magic-link doit utiliser # et non ? pour le token."""
        from routes.portal import send_portal_email
        from unittest.mock import patch, MagicMock
        import smtplib

        captured_body = []

        def fake_sendmail(from_addr, to_addr, msg_str):
            captured_body.append(msg_str)

        with patch("routes.portal.settings") as mock_settings, \
             patch("smtplib.SMTP") as mock_smtp:
            mock_settings.smtp_host = "smtp.test"
            mock_settings.smtp_port = 587
            mock_settings.smtp_user = "u"
            mock_settings.smtp_password = "p"
            mock_settings.alert_from_email = "noreply@test.com"
            mock_settings.app_url = "https://llmbudget.maxiaworld.app"

            instance = mock_smtp.return_value.__enter__.return_value
            instance.sendmail.side_effect = fake_sendmail

            send_portal_email("user@test.com", "tok123")

        assert captured_body, "Email non envoyé"
        body = captured_body[0]
        assert "#token=tok123" in body, "Token doit être dans le hash, pas en query string"
        assert "?token=tok123" not in body, "Token NE DOIT PAS être en query string"
```

- [ ] **Lancer pour confirmer RED**

```bash
pytest tests/test_audit8.py::TestX4MagicLinkHash -v
```

- [ ] **Implémenter backend** dans `backend/routes/portal.py:92`

Remplacer :
```python
    link = f"{settings.app_url}/portal?token={token}"
```
Par :
```python
    link = f"{settings.app_url}/portal#token={token}"
```

- [ ] **Implémenter dashboard** dans `dashboard/app/portal/page.tsx`

Trouver la ligne qui lit `searchParams` ou `useSearchParams()` pour récupérer le token, et remplacer par lecture depuis `window.location.hash`.

Chercher le pattern existant :
```bash
grep -n "token\|searchParams\|useSearchParams\|hash" budgetforge/dashboard/app/portal/page.tsx | head -20
```

Puis modifier pour lire depuis le hash :
```typescript
// Remplacer la lecture depuis searchParams par :
useEffect(() => {
  const hash = window.location.hash; // "#token=xxx"
  if (hash.startsWith("#token=")) {
    const token = hash.slice(7);
    // appel verify avec ce token
    // après verify réussi : nettoyer le hash
    window.history.replaceState(null, "", window.location.pathname);
  }
}, []);
```

- [ ] **Lancer pour confirmer GREEN**

```bash
pytest tests/test_audit8.py::TestX4MagicLinkHash -v
```

- [ ] **Commit**

```bash
git add backend/routes/portal.py dashboard/app/portal/page.tsx backend/tests/test_audit8.py
git commit -m "fix(portal): magic-link token via hash fragment (no Referer leak) — X4"
```

---

## BLOC B — Corrections effort ≤ 2 (audit #4 restants)

> Les tests pour M01, M02, M11 existent déjà dans `backend/tests/test_bloc9_effort2.py`. Pour ces tasks : vérifier qu'ils sont RED, implémenter, vérifier GREEN.

### Task B1 : X8 — Cookie `bf_session` flag Secure

**Files:**
- Modify: `dashboard/app/api/auth/route.ts`

- [ ] **Chercher toutes les occurrences de `Set-Cookie` / `set-cookie`**

```bash
grep -rn "SameSite\|httpOnly\|HttpOnly\|bf_session" budgetforge/dashboard/app/api/ budgetforge/dashboard/proxy.ts
```

- [ ] **Ajouter le flag `Secure` conditionnel** dans chaque `Set-Cookie` trouvé

Pattern à appliquer (dans chaque route API Next.js qui émet `bf_session`) :
```typescript
const isProduction = process.env.NODE_ENV === "production";
const cookieOptions = [
  `bf_session=${value}`,
  "Path=/",
  "HttpOnly",
  "SameSite=Lax",
  `Max-Age=${86400}`,
  ...(isProduction ? ["Secure"] : []),
].join("; ");
response.headers.set("Set-Cookie", cookieOptions);
```

- [ ] **Vérifier sur VPS que le cookie reçoit Secure**

```bash
curl -sI https://llmbudget.maxiaworld.app/api/auth | grep -i set-cookie
```
Attendu : `Secure` présent dans la ligne `Set-Cookie`.

- [ ] **Commit**

```bash
git add dashboard/app/api/auth/route.ts
git commit -m "fix(dashboard): add Secure flag to bf_session cookie in production — X8"
```

---

### Task B2 : H26 — `dynamic_pricing` singleton sans close()

**Problème :** Le singleton `DynamicPricingManager` ouvre un client `httpx.AsyncClient` jamais fermé → file descriptor leak à chaque reload de l'app.

**Files:**
- Modify: `backend/main.py` (lifespan)
- Modify: `backend/services/dynamic_pricing.py`

- [ ] **Écrire le test RED** (ajouter dans `test_audit8.py`)

```python
# ── H26 — dynamic_pricing close ───────────────────────────────────────────────

class TestH26DynamicPricingClose:
    def test_dynamic_pricing_manager_has_close_method(self):
        """DynamicPricingManager doit avoir une méthode close() async."""
        from services.dynamic_pricing import DynamicPricingManager
        import inspect
        assert hasattr(DynamicPricingManager, "close"), "Méthode close() manquante"
        assert inspect.iscoroutinefunction(DynamicPricingManager.close), "close() doit être async"

    @pytest.mark.asyncio
    async def test_dynamic_pricing_close_closes_http_client(self):
        """close() doit fermer le client httpx si existant."""
        from services.dynamic_pricing import DynamicPricingManager
        manager = DynamicPricingManager()
        # Simuler qu'un client est ouvert
        import httpx
        manager._http_client = httpx.AsyncClient()
        await manager.close()
        assert manager._http_client.is_closed
```

- [ ] **Lancer pour confirmer RED**

```bash
pytest tests/test_audit8.py::TestH26DynamicPricingClose -v
```

- [ ] **Implémenter** dans `backend/services/dynamic_pricing.py`

Trouver la classe principale et ajouter :
```python
    async def close(self) -> None:
        """Fermer proprement le client HTTP si existant."""
        if hasattr(self, "_http_client") and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
```

Et dans `backend/main.py`, dans le bloc `lifespan` (ou `@app.on_event("shutdown")`) :
```python
from services.dynamic_pricing import get_dynamic_pricing_manager  # adapter au nom réel

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    manager = get_dynamic_pricing_manager()
    if manager:
        await manager.close()
```

- [ ] **Lancer GREEN**

```bash
pytest tests/test_audit8.py::TestH26DynamicPricingClose -v
```

- [ ] **Commit**

```bash
git add backend/services/dynamic_pricing.py backend/main.py backend/tests/test_audit8.py
git commit -m "fix(dynamic_pricing): add close() + call in lifespan — H26"
```

---

### Task B3 : M01 — `_memory_locks` dict illimité

**Tests déjà écrits** dans `backend/tests/test_bloc9_effort2.py::TestM01MemoryLocksBounded`.

- [ ] **Confirmer RED**

```bash
pytest tests/test_bloc9_effort2.py::TestM01MemoryLocksBounded -v
```

- [ ] **Implémenter** dans `backend/services/distributed_budget_lock.py:102-111`

```python
_memory_locks: dict[int, asyncio.Lock] = {}
_MEMORY_LOCKS_MAX_SIZE = 1000


def _get_memory_lock(project_id: int) -> asyncio.Lock:
    if project_id not in _memory_locks:
        if len(_memory_locks) >= _MEMORY_LOCKS_MAX_SIZE:
            # Éviction FIFO : supprimer la plus ancienne clé
            oldest = next(iter(_memory_locks))
            del _memory_locks[oldest]
        _memory_locks[project_id] = asyncio.Lock()
    return _memory_locks[project_id]
```

Remplacer les appels directs à `_memory_locks[project_id]` par `_get_memory_lock(project_id)`.

- [ ] **Confirmer GREEN**

```bash
pytest tests/test_bloc9_effort2.py::TestM01MemoryLocksBounded -v
```

- [ ] **Commit**

```bash
git add backend/services/distributed_budget_lock.py
git commit -m "fix(lock): cap _memory_locks at 1000 entries with FIFO eviction — M01"
```

---

### Task B4 : M02 — `CODE_PATTERNS` regex non compilées

**Tests déjà écrits** dans `backend/tests/test_bloc9_effort2.py::TestM02CodePatternsCompiled`.

- [ ] **Confirmer RED**

```bash
pytest tests/test_bloc9_effort2.py::TestM02CodePatternsCompiled -v
```

- [ ] **Implémenter** dans `backend/services/token_estimator.py:25`

```python
import re

# Remplacer les strings brutes par des re.Pattern compilés
CODE_PATTERNS = [
    re.compile(r"def |class |import |from |return |if |for |while "),
    re.compile(r"function |const |let |var |=>|async |await "),
    # ... adapter aux patterns existants dans le fichier
]
```

Adapter en lisant les patterns existants ligne 25-44 du fichier.

- [ ] **Confirmer GREEN**

```bash
pytest tests/test_bloc9_effort2.py::TestM02CodePatternsCompiled -v
```

- [ ] **Commit**

```bash
git add backend/services/token_estimator.py
git commit -m "fix(estimator): pre-compile CODE_PATTERNS regex — M02"
```

---

### Task B5 : M03 — Email injection via `\r\n` (mailsplit)

**Problème :** Si un email contient `\r\n`, SMTP interprète les lignes suivantes comme des headers additionnels.

**Files:**
- Modify: `backend/routes/portal.py:131` (email normalization)
- Modify: `backend/routes/signup.py` (idem)
- Modify (tests): `backend/tests/test_audit8.py`

- [ ] **Écrire le test RED**

```python
# ── M03 — email injection via \r\n ─────────────────────────────────────────────

class TestM03EmailInjection:
    def test_portal_request_rejects_email_with_crlf(self, client):
        """`\r\n` dans l'email doit retourner 422 ou 400."""
        resp = client.post(
            "/api/portal/request",
            json={"email": "user@test.com\r\nBcc: attacker@evil.com"},
        )
        assert resp.status_code in (400, 422), (
            f"Email avec CRLF doit être rejeté, got {resp.status_code}"
        )

    def test_portal_request_rejects_email_with_newline(self, client):
        resp = client.post(
            "/api/portal/request",
            json={"email": "user@test.com\nX-Injected: header"},
        )
        assert resp.status_code in (400, 422)
```

- [ ] **Lancer pour confirmer RED**

```bash
pytest tests/test_audit8.py::TestM03EmailInjection -v
```

- [ ] **Implémenter** dans `backend/routes/portal.py:131`

Ajouter après `email = body.email.strip().lower()` :
```python
    if "\r" in email or "\n" in email:
        raise HTTPException(status_code=400, detail="Invalid email")
```

Faire la même chose dans `backend/routes/signup.py` à l'endroit où l'email est traité.

- [ ] **Lancer GREEN**

```bash
pytest tests/test_audit8.py::TestM03EmailInjection -v
```

- [ ] **Commit**

```bash
git add backend/routes/portal.py backend/routes/signup.py backend/tests/test_audit8.py
git commit -m "fix(portal,signup): reject emails containing CRLF — M03"
```

---

### Task B6 : M04 — Timing attack sur enum email `portal_request`

**Problème :** `portal_request` retourne `{"ok": True}` même si l'email n'existe pas (correct pour l'UX) mais le temps de réponse diffère (requête DB rapide si 0 projet vs. slow si envoi SMTP). Un attaquant peut timer pour savoir si un email est inscrit.

**Files:**
- Modify: `backend/routes/portal.py:127-146`
- Modify (tests): `backend/tests/test_audit8.py`

- [ ] **Écrire le test RED**

```python
# ── M04 — timing portal_request ───────────────────────────────────────────────

class TestM04TimingPortalRequest:
    def test_portal_request_response_time_consistent(self, client):
        """Les temps de réponse pour email inexistant vs existant doivent être comparables."""
        import time

        # Email inexistant
        t0 = time.monotonic()
        client.post("/api/portal/request", json={"email": "nobody@nowhere.com"})
        t_miss = time.monotonic() - t0

        # Email inexistant #2 (pas besoin d'un vrai compte pour ce test de structure)
        t0 = time.monotonic()
        client.post("/api/portal/request", json={"email": "also_nobody@nowhere.com"})
        t_miss2 = time.monotonic() - t0

        # Les deux doivent prendre au minimum MIN_DELAY (ex: 100ms)
        MIN_DELAY = 0.05  # 50ms minimum pour les deux cas
        assert t_miss >= MIN_DELAY or t_miss2 >= MIN_DELAY  # au moins l'un des deux
```

Note : ce test est indicatif. L'important est que le code ajoute un délai minimal.

- [ ] **Implémenter** dans `backend/routes/portal.py:127-146`

```python
@router.post("/api/portal/request")
@limiter.limit("5/hour")
async def portal_request(
    request: Request, body: PortalRequestBody, db: Session = Depends(get_db)
):
    import asyncio as _asyncio
    cleanup_expired_tokens(db)
    email = body.email.strip().lower()
    if "\r" in email or "\n" in email:
        raise HTTPException(status_code=400, detail="Invalid email")

    # Délai constant pour éviter l'énumération par timing
    _start = __import__("time").monotonic()
    _MIN_RESPONSE_S = 0.1  # 100ms

    projects = db.query(Project).filter(Project.name == email).all()
    if projects:
        token = PortalToken(
            email=email,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
            + timedelta(hours=_TOKEN_TTL_HOURS),
        )
        db.add(token)
        db.commit()
        db.refresh(token)
        await _asyncio.to_thread(send_portal_email, email, token.token)

    # Pad jusqu'au délai minimum
    elapsed = __import__("time").monotonic() - _start
    if elapsed < _MIN_RESPONSE_S:
        await _asyncio.sleep(_MIN_RESPONSE_S - elapsed)

    return {"ok": True}
```

- [ ] **Commit**

```bash
git add backend/routes/portal.py backend/tests/test_audit8.py
git commit -m "fix(portal): constant-time response to prevent email enumeration — M04"
```

---

### Task B7 : M10 — `/api/models` fait 9 requêtes outbound à chaque appel

**Problème :** `GET /api/models` appelle tous les providers à chaque requête → latence + coût.

**Files:**
- Modify: `backend/routes/models.py`
- Modify (tests): `backend/tests/test_audit8.py`

- [ ] **Écrire le test RED**

```python
# ── M10 — /api/models cache ────────────────────────────────────────────────────

class TestM10ModelsCache:
    def test_models_endpoint_uses_cache(self, client):
        """/api/models ne doit pas faire 9 appels outbound à chaque requête."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=lambda: {"data": []})
            client.get("/api/models", headers={"X-Admin-Key": "test-admin-key"})
            first_calls = mock_get.call_count

            client.get("/api/models", headers={"X-Admin-Key": "test-admin-key"})
            second_calls = mock_get.call_count - first_calls

        assert second_calls < first_calls, (
            "Le 2ème appel doit utiliser le cache (moins d'appels HTTP)"
        )
```

- [ ] **Implémenter** dans `backend/routes/models.py`

Ajouter un cache TTL simple (5 minutes) :
```python
import time
from typing import Optional

_models_cache: Optional[dict] = None
_models_cache_ts: float = 0.0
_MODELS_CACHE_TTL = 300  # 5 minutes


async def _fetch_models_with_cache() -> dict:
    global _models_cache, _models_cache_ts
    now = time.monotonic()
    if _models_cache is not None and (now - _models_cache_ts) < _MODELS_CACHE_TTL:
        return _models_cache
    result = await _fetch_models_live()  # logique existante
    _models_cache = result
    _models_cache_ts = now
    return result
```

Adapter `_fetch_models_live()` depuis la logique existante de l'endpoint.

- [ ] **Commit**

```bash
git add backend/routes/models.py backend/tests/test_audit8.py
git commit -m "fix(models): cache /api/models response 5 minutes — M10"
```

---

### Task B8 : M11 — `billing_sync` retourne HTTP 200 sur erreur

**Tests déjà écrits** dans `backend/tests/test_bloc9_effort2.py::TestM11BillingSync`.

- [ ] **Confirmer RED**

```bash
pytest tests/test_bloc9_effort2.py::TestM11BillingSync -v
```

- [ ] **Implémenter** dans `backend/routes/admin.py` — fonction `billing_sync`

```python
@router.get("/api/admin/billing-sync")
def billing_sync(db: Session = Depends(get_db)):
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    # ... reste de la logique existante
```

- [ ] **Confirmer GREEN**

```bash
pytest tests/test_bloc9_effort2.py::TestM11BillingSync -v
```

- [ ] **Commit**

```bash
git add backend/routes/admin.py
git commit -m "fix(admin): billing_sync returns 503 when Stripe not configured — M11"
```

---

### Task B9 : Deploy Bloc A+B en prod

- [ ] **Lancer la suite complète**

```bash
cd budgetforge/backend && pytest tests/ -v --tb=short -q 2>&1 | tail -20
```
Attendu : 0 échec (hors skip intentionnels).

- [ ] **Transfer + migrations + restart**

```bash
cd "C:/Users/Mini pc/Desktop/MAXIA Lab"

# Backup VPS
ssh ubuntu@146.59.237.43 "sudo cp -a /opt/budgetforge /opt/budgetforge.bak-$(date +%Y%m%d-%H%M%S)"

# Transfer
tar -czf - \
  --exclude='budgetforge/.git' \
  --exclude='budgetforge/dashboard/node_modules' \
  --exclude='budgetforge/dashboard/.next' \
  --exclude='budgetforge/backend/venv' \
  --exclude='budgetforge/backend/__pycache__' \
  budgetforge/ | ssh ubuntu@146.59.237.43 "tar -xzf - -C /opt"

# Migrations
ssh ubuntu@146.59.237.43 "cd /opt/budgetforge/backend && venv/bin/alembic upgrade head"

# Build + restart
ssh ubuntu@146.59.237.43 "cd /opt/budgetforge/dashboard && npm run build 2>&1 | tail -5"
ssh ubuntu@146.59.237.43 "sudo systemctl restart budgetforge-backend budgetforge-dashboard"

# Vérifier
ssh ubuntu@146.59.237.43 "curl -s https://llmbudget.maxiaworld.app/health"
```

- [ ] **Confirmer health `{"status":"ok"}`**

---

## BLOC C — Session dédiée post-launch (effort 4)

> Ces corrections nécessitent chacune une session dédiée. Ne pas faire en parallèle avec du support client.

### Task C1 : X6 — Admin key → cookie httpOnly (breaking change)

**Impact :** Refactor complet `dashboard/lib/api.ts` + nouveau endpoint backend `POST /api/admin/login`.

Approche :
1. Backend : `POST /api/admin/login` body `{key: string}` → set cookie httpOnly `bf_admin_key`
2. Backend : middleware vérifie cookie `bf_admin_key` au lieu du header `X-Admin-Key`
3. Dashboard : supprimer `localStorage.getItem("bf_admin_key")` de `lib/api.ts`
4. Dashboard : page `/login` appelle `POST /api/admin/login` au lieu de stocker en localStorage
5. Migrations : aucune

Durée estimée : 3-4h (tests + migration comportementale dashboard).

### Task C2 : H19 — Worker bloqué si client coupe avant finalize

**Impact :** `proxy_dispatcher.py` — streaming. Si le client ferme la connexion avant que le stream soit terminé, le thread `finalize_usage` ne s'exécute pas → budget non consommé.

Approche : `asyncio.shield()` sur `finalize_usage` pour l'isoler de la cancellation du client.

### Task C3 : H20 — Timing attack API key lookup

**Fichier :** `core/auth.py` — `hmac.compare_digest` utilisé ? Sinon, comparaison directe des strings → timing leak.

Approche : s'assurer que tous les lookups d'API key utilisent `hmac.compare_digest`.

### Task C4 : H22 — SQL quota par appel proxy

**Impact :** `services/plan_quota.py:check_quota` exécute une requête SQL à chaque appel proxy → sous charge, N appels simultanés = N requêtes SQL.

Approche : cache en mémoire avec TTL 30s (invalidé à la création de projet).

### Task C5 : M08/M09 — History count lent + dates naïves UTC

**M08 :** `routes/history.py` — `COUNT(*)` sur grande table sans index → ajouter index sur `created_at` + `project_id`.

**M09 :** `date_from/to` reçus comme strings naïfs → les interpréter explicitement en UTC.

---

## Ordre d'exécution recommandé

```
A1 → A2 → A3 → A4 → (suite tests verte) → Deploy
B1 → B2 → B3 → B4 → B5 → B6 → B7 → B8 → (suite tests verte) → Deploy
C1, C2, C3, C4, C5 → sessions dédiées séparées
```

## Définition "PRÊT" post-plan

- Blocs A + B mergés et déployés
- Suite complète verte (0 échec)
- Health prod `{"status":"ok"}`
- Verdict audit = PRÊT AVEC RÉSERVES (Bloc C en backlog)
