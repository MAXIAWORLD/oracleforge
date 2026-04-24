# Audit Critique BudgetForge — Phase 1 (Business Logic)
**Date:** 2026-04-22  
**Rigeur:** Senior QA Engineer — analyse exhaustive, zéro compromis  
**Scope:** Business logic, race conditions, architectural flaws  

---

## FINDINGS CRITIQUES (Blocker = Production Risk Immédiat)

### Finding #1: Multi-Worker Budget Lock Race Condition [BLOCKER - P0]
**Fichier:** `backend/services/budget_lock.py`, `backend/routes/proxy.py:130-136`  
**Sévérité:** CRITIQUE — Loss of Budget Integrity  

**Problème:**
```python
# budget_lock.py ligne 23 — commentaire explicite:
"# efficace pour un déploiement single-process (uvicorn --workers 1)"

# Implémentation:
_project_locks: dict[int, asyncio.Lock] = {}  # IN-MEMORY, per-process

# proxy.py ligne 130:
async with budget_lock(project.id):
    final_model = _check_budget(project, db, model)
    usage_id = proxy_dispatcher.prebill_usage(...)
```

**Réalité en production:**  
VPS déployé avec Uvicorn multi-worker (2-4 workers par défaut). Chaque worker a sa **propre copie** de `_project_locks` en mémoire.

**Scénario d'exploitation:**
1. Request A arrive sur worker 1, lock non obtenu (projet jamais verrouillé avant)
2. Request B arrive sur worker 2 **en même temps**, crée sa propre lock dans sa mémoire
3. Deux checks de budget simultanés:
   - Worker 1 lit: used=$5, budget=$10 → ALLOWED
   - Worker 2 lit: used=$5, budget=$10 → ALLOWED
4. Deux prebills exécutés:
   - Worker 1 écrit: used=$5 + $2 = $7
   - Worker 2 écrit: used=$5 + $3 = $8 (écrase worker 1!)
5. **Résultat:** Budget utilisé réellement = $7+$3=$10, mais DB enregistre seulement $8. Overbudget invisible.

**Impact:** 
- Budget bypass complèt en mode multi-worker
- Impossible de garantir qu'aucune requête ne dépasse le budget
- Utilisateurs peuvent consommer plusieurs fois plus que leur budget alloué

**Test pour confirmer:**  
```bash
curl -N "Authorization: Bearer bf-xxx" "X-Parallel: true" &
curl -N "Authorization: Bearer bf-xxx" "X-Parallel: true" &
# Vérifier que les deux requêtes passent même si budget=0
```

---

### Finding #2: Portal Token Email Enumeration Vulnerability [BLOCKER - P0 Security]
**Fichier:** `backend/routes/portal.py:92-110`  
**Sévérité:** HAUTE — Information Disclosure  

**Problème:**
```python
# Endpoint public, accessible sans auth
@router.post("/api/portal/request")
@limiter.limit("5/hour")  # Insuffisant pour brute-force
def portal_request(request: Request, body: PortalRequestBody, db: Session = Depends(get_db)):
    cleanup_expired_tokens(db)
    email = body.email.strip().lower()
    projects = db.query(Project).filter(Project.name == email).all()
    
    if not projects:
        return {"ok": True}  # ← PROBLEM: Silent success même si email inexistant
    
    # ... send token ...
    return {"ok": True}
```

**Attaque possible:**
```python
# Tester si alice@example.com existe dans BudgetForge
# Timing attack: pas de slowdown si email inexistant
response_time_unknown_email = request_time("/api/portal/request", "alice@example.com")
response_time_known_email = request_time("/api/portal/request", "bob@example.com")

# Le temps est identique → pas de timing-based detection possible
# MAIS: Combine avec password reuse (Alice a un compte BudgetForge?)
```

**Rate limit inadequate:**  
5/hour = 300/jour = 9000/mois. Pour un dictionnaire de 10,000 emails, un attaquant peut tester tous en ~3 mois sans être détecté.

**Impact:**
- Email enumeration: un attaquant découvre qui utilise BudgetForge
- Reconnaissance pour phishing/social engineering
- RGPD violation: divulgation d'existence de comptes utilisateurs

---

### Finding #3: Portal Token Grants Access to ALL Projects of Email [BLOCKER - P0 Security]
**Fichier:** `backend/routes/portal.py:165-191`  
**Sévérité:** HAUTE — Privilege Escalation  

**Problème:**
```python
# portal.py ligne 189-190
@router.get("/api/portal/verify")
def portal_verify(token: str, response: Response, db: Session = Depends(get_db)):
    record = db.query(PortalToken).filter(PortalToken.token == token).first()
    # ... validate token ...
    
    # Invalider le token (single-use) — BON
    db.delete(record)
    db.commit()
    
    # PROBLEM: Retourne TOUS les projets de cet email
    projects = db.query(Project).filter(Project.name == email).all()
    return {"email": email, "projects": _project_list(projects)}
```

**Scénario:**
1. Entreprise X a email="company@x.com" avec 5 projets (Prod, Staging, Dev, Test, Marketing)
2. Attaquant obtient un token valide par:
   - Compromission email (leaked password reused)
   - Phishing
   - SMTP interception (lab network)
3. Attaquant clique le lien, obtient l'API key pour TOUS les 5 projets
4. Attaquant utilise Prod project key pour vider le budget

**Correct design:**
- Portal token ne doit être lié qu'à **UN** seul projet
- Email peut avoir plusieurs projets → créer de Nseaux portals tokens (un par projet)

---

### Finding #4: Stripe Webhook Duplicate Project Creation [HIGH - P1]
**Fichier:** `backend/routes/billing.py:90-130`  
**Sévérité:** HAUTE — Duplicate Account Creation  

**Problème:**
```python
async def _handle_checkout_completed(session: dict, db: Session) -> None:
    email = session.get("customer_email")
    plan = session.get("metadata", {}).get("plan", "pro")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")  # ← Can be None!
    
    # Idempotence check — seulement si subscription_id existe
    if subscription_id:
        existing = db.query(Project).filter(
            Project.stripe_subscription_id == subscription_id
        ).first()
        if existing:
            existing.plan = plan
            db.commit()
            return  # ← Idempotent
    
    # PROBLEM: Si subscription_id est None, aucun idempotence check
    # Deuxième webhook identical → crée un NOUVEAU project!
    project = Project(name=email, plan=plan, ...)
    db.add(project)
    db.commit()
    # Maintenant: 2 projets pour la même email
```

**Quand subscription_id peut être None:**
- Free plan checkout (Stripe parfois n'attache pas de subscription)
- Certains régions/configurations Stripe
- Webhook retry sans subscription (edge case)

**Impact:**
- Duplicate API keys pour le même utilisateur
- Confabulation dans les statistiques (2 projects au lieu de 1)
- Utilisateur confused par deux entries dans le dashboard

---

### Finding #5: Float Type for Monetary Amounts [HIGH - P1 Data Integrity]
**Fichier:** `backend/core/models.py:22, 30`, `backend/routes/portal.py:146`  
**Sévérité:** HAUTE — Accounting Precision Loss  

**Problème:**
```python
# models.py
budget_usd = Column(Float, nullable=True)
max_cost_per_call_usd = Column(Float, nullable=True)

# portal.py ligne 146
"spend": round(by_day.get((start + timedelta(days=i)).isoformat(), 0.0), 9)
# Round à 9 décimales? USD devrait être à 2 max (cents)
```

**Float IEEE 754 issue:**
```python
# Exemple réel:
budget = 100.00 (stocké en float)
# Internalement = 100.0000000000000142... (représentation imprécise)

cost1 = 0.01  # 0.009999999999999... 
cost2 = 0.02  # 0.020000000000000...
sum = cost1 + cost2  # 0.030000000000000...

# Après 100 opérations:
used = 3.14 (DBB dit 3.14, réalité = 3.140000000000001)
if used >= budget: ...  # Peut échouer ou passer au mauvais moment
```

**Impact:**
- Budget calculations can drift over time
- Long-running projects accumulate rounding errors
- Audit reports don't match actual consumption

**Correct approach:**
- Utiliser `Decimal` pour les USD
- Ou stocker en cents (integer: budget_cents = 10000 = $100.00)

---

### Finding #6: Reset Period Timezone Issue [MEDIUM - P2]
**Fichier:** `backend/services/budget_guard.py:44-51`  
**Sévérité:** MOYENNE — Fairness Issue  

**Problème:**
```python
def get_period_start(reset_period: str) -> datetime:
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # Always UTC
    if reset_period == "monthly":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if reset_period == "weekly":
        monday = now - timedelta(days=now.weekday())
        return monday.replace(hour=0, minute=0, second=0, microsecond=0)
    return datetime.min
```

**Exemple:**
- User in Los Angeles (UTC-7)
- Reset period = "monthly"
- Expected reset: 1st of month at 00:00 LA time (08:00 UTC)
- **Actual reset:** 1st of month at 00:00 UTC (previous day at 17:00 LA time!)

**Impact:**
- Monthly budget resets at wrong time for non-UTC users
- User sees budget "reset" at 5 PM instead of midnight
- Confusing UX ("Why did my budget reset 7 hours early?")

---

### Finding #7: Downgrade Chain Missing Validation [MEDIUM - P2]
**Fichier:** `backend/services/budget_guard.py:22-41, 64-75`  
**Sévérité:** MOYENNE — Logic Flaw  

**Problems:**
1. **No cycle detection:**
   ```python
   downgrade_chain = ["gpt-4o", "gpt-4o", "gpt-4o"]  # Infinite loop possible
   # Returns gpt-4o → gpt-4o → gpt-4o...
   ```

2. **No cost validation:**
   ```python
   # Attacker configures:
   downgrade_chain = ["gpt-4o"]  # Same cost as original
   # Budget guard downgrades to same cost model → loop forever
   ```

3. **Empty chain handling:**
   ```python
   downgrade_chain = []  # Returns BudgetStatus(allowed=False)
   # No logging, user sees "Budget exceeded" with no alternative
   ```

---

### Finding #8: Portal Session Cookie TTL vs Token TTL Mismatch [MEDIUM - P2 Security]
**Fichier:** `backend/routes/portal.py:21-22, 180-188`  
**Sévérité:** MOYENNE — Session Longevity Issue  

**Problem:**
```python
_TOKEN_TTL_HOURS = 1  # Token expires after 1 hour
_SESSION_MAX_AGE = 90 * 24 * 3600  # But session cookie lasts 90 days!

@router.get("/api/portal/verify")
def portal_verify(token: str, response: Response, ...):
    # ... validate token (expires in 1 hour) ...
    response.set_cookie(
        key="portal_session",
        max_age=_SESSION_MAX_AGE,  # 90 days!
        ...
    )
```

**Impact:**
- Token is single-use (deleted after 1 verification)
- But session cookie allows access for 90 days
- If session cookie stolen, attacker has permanent access to all projects

---

### Finding #9: Budget Check Happens BEFORE Acquiring Lock [HIGH - P1 Race Condition]
**Fichier:** `backend/routes/proxy.py:74-92`  
**Sévérité:** HAUTE — Budget Bypass (Subtle)  

**Problem:**
```python
# proxy.py ligne 74-92
def _check_budget(project: Project, db: Session, model: str) -> str:
    if project.budget_usd is None:
        return model
    used = proxy_dispatcher.get_period_used_sql(...)  # ← QUERY (unlocked)
    action = BudgetAction(...)
    status = guard.check(budget_usd=..., used_usd=used, ...)  # ← CHECK
    if not status.allowed:
        raise HTTPException(...)
    return status.downgrade_to or model

# THEN in proxy_openai (ligne 130):
async with budget_lock(project.id):
    final_model = _check_budget(project, db, model)  # ← Decision made!
    usage_id = proxy_dispatcher.prebill_usage(...)    # ← Write locked
```

**Race window:**
```
Time T0: Request A checks budget → used=$5, budget=$10 → ALLOWED
Time T1: Request B checks budget → used=$5, budget=$10 → ALLOWED
Time T2: Request A acquires lock, prebills $4 → used=$9
Time T3: Request B acquires lock, prebills $2 → used=$11 (OVER!)
```

The lock only protects the write, not the decision. Both requests decided to proceed before either wrote.

---

### Finding #10: Project.name (Email) Design Flaw [MEDIUM - P2]
**Fichier:** `backend/core/models.py:18`, `backend/routes/portal.py:97`  
**Sévérité:** MOYENNE — Design Issue  

**Problem:**
```python
# models.py
name = Column(String, unique=True, nullable=False, index=True)
# Assumption: name is always an email

# portal.py ligne 97
projects = db.query(Project).filter(Project.name == email).all()
# Works IF all projects have email as name

# BUT: Nothing prevents:
Project(name="production", plan="pro")  # Non-email name!
# Later, portal lookup fails for this project
```

**Better design:**
- Separate columns: `owner_email`, `project_name`
- owner_email: many projects per email
- project_name: user-friendly name within owner scope

---

### Finding #11: No CSRF Protection on Portal Endpoints [LOW-MEDIUM - P3]
**Fichier:** `backend/routes/portal.py:92-110, 165-191`  
**Sévérité:** BASSE-MOYENNE — CSRF Risk  

**Problem:**
```python
@router.post("/api/portal/request")  # POST but no CSRF token
def portal_request(request: Request, body: PortalRequestBody, ...):
    # Attacker can CSRF this from another site
    # POST request to /api/portal/request with attacker's email
    # Victim's browser sends cookies, request succeeds
    # Attacker receives portal token for victim's email
```

**Mitigation:**
- Add CSRF token validation
- OR: Use SameSite=Strict on cookies (already done in verify, but request doesn't validate)

---

## SUMMARY TABLE

| Finding | Type | Severity | Component | Fix Complexity |
|---------|------|----------|-----------|-----------------|
| #1 | Logic | P0 | budget_lock | HIGH (need DB locking) |
| #2 | Security | P0 | portal.py | MEDIUM (timing attack) |
| #3 | Security | P0 | portal.py | MEDIUM (scope token to 1 project) |
| #4 | Logic | P1 | billing.py | MEDIUM (add email+timestamp check) |
| #5 | Data | P1 | models.py | HIGH (refactor to Decimal) |
| #6 | UX | P2 | budget_guard.py | LOW (add timezone param) |
| #7 | Logic | P2 | budget_guard.py | LOW (validate downgrade chain) |
| #8 | Security | P2 | portal.py | LOW (align TTLs) |
| #9 | Logic | P1 | proxy.py | HIGH (move check inside lock) |
| #10 | Design | P2 | models.py | HIGH (redesign schema) |
| #11 | Security | P3 | portal.py | LOW (add CSRF token) |

---

## BLOCKER SUMMARY (Cannot Ship)
1. **Budget integrity compromised in multi-worker** — Any concurrency scenario breaks budget enforcement
2. **Email enumeration attack possible** — Silent success on unknown email allows discovery
3. **Portal token grants all-projects access** — Single token compromises all projects of an email

**Recommendation:** Block production deployments until Finding #1, #2, #3 are fixed. Everything else is post-ship.

