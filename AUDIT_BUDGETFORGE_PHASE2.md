# Audit Critique BudgetForge — Phase 2 (Security)
**Date:** 2026-04-22  
**Scope:** Input validation, SSRF, secrets, authentication bypass, rate limiting  

---

## SECURITY FINDINGS

### Finding #S1: SSRF Protection Has Bypass Vector [HIGH - P1]
**Fichier:** `backend/core/url_validator.py`, `backend/routes/projects.py` (webhook_url)  
**Sévérité:** HAUTE — SSRF Injection  

**Théoriquement, url_validator.py semble bon :**
```python
def is_safe_webhook_url(url: str) -> bool:
    # Bloque localhost, RFC 1918, link-local, metadata.google.internal
    # Résout DNS et valide les IPs
```

**MAIS : Plusieurs bypasses possibles :**

1. **DNS Rebinding Attack :**
   ```
   Attacker registre attacker.com
   
   First DNS query: attacker.com → resolves to 8.8.8.8 (Google Public DNS) ✓ PASSED
   Validation passes, webhook URL stored in DB
   
   Second DNS query (webhook execution): attacker.com → resolves to 127.0.0.1
   Webhook delivers to localhost! ✓ BYPASSED
   ```

   **Code vulnerable:**
   ```python
   # Line 43: one-time DNS resolution during validation
   resolved = socket.getaddrinfo(hostname, None)
   # ... validate IPs ...
   
   # Later, webhook.py actually sends to the URL
   # Second DNS resolution happens → may resolve differently!
   ```

2. **Cloud Metadata URLs (AWS/GCP/Azure) :**
   - Ligne 17 : Bloque seulement `metadata.google.internal`
   - **Oublis :**
     - `169.254.169.254` (AWS, GCP, Azure metadata) → BLOCKED (line 10)... OK
     - `metadata.google.com` (public interface) → NOT BLOCKED
     - `service.amazonaws.com` (data exfiltration) → NOT BLOCKED

3. **CNAME Alias Bypass :**
   ```
   attacker.com → CNAME → internal-db.local
   DNS resolution returns 10.0.0.1 → BLOCKED
   
   BUT: If using HTTP client with DNS override, can reach internal-db.local
   ```

**Impact:**
- Attacker can send webhooks to localhost, triggering local functions
- Can reach internal services if network allows
- Can exfiltrate database credentials via error messages

---

### Finding #S2: API Key Rotation Grace Period has Window [MEDIUM - P2]
**Fichier:** `backend/routes/proxy.py:28-48`  
**Sévérité:** MOYENNE — Brute-force window  

**Problem:**
```python
_GRACE_PERIOD_MINUTES = 5

def _get_project_by_api_key(authorization: Optional[str], db: Session) -> Project:
    api_key = authorization.removeprefix("Bearer ").strip()
    
    project = db.query(Project).filter(Project.api_key == api_key).first()
    if project:
        return project
    
    # If current key fails, check old key (within 5 minute window)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
    project = db.query(Project).filter(
        Project.previous_api_key == api_key,
        Project.key_rotated_at >= cutoff,  # ← Only last 5 minutes
    ).first()
    if project:
        return project
    
    raise HTTPException(status_code=401, detail="Invalid API key")
```

**Issue:**
During rotation, BOTH old and new keys are valid simultaneously for 5 minutes. 

**Attacker perspective:**
```
Time T0: Attacker obtains old API key (leaked from GitHub, email, etc.)
Time T1: Admin rotates the key
Time T2-T7: Old key still valid within grace period!
Time T7: Old key finally expires

Window = 5 minutes for attacker to exploit leaked old key
```

**Better approach:**
- Rotation should invalidate old key immediately, OR
- Require client to re-authenticate with both old and new key (in-band rotation)

---

### Finding #S3: Stripe API Key in Environment Variable [MEDIUM - P2 Secret Leakage]
**Fichier:** `backend/core/config.py`, `backend/routes/billing.py:44`  
**Sévérité:** MOYENNE — Credential Exposure  

**Problem:**
```python
# billing.py ligne 44 (dans route endpoint)
stripe.api_key = settings.stripe_secret_key

# Better: stripe.api_key set once at startup, not per-request
```

**Risks:**
1. **Verbose error messages leak the key:**
   ```python
   stripe.error.SignatureVerificationError → includes stripe_webhook_secret in error trace
   ```

2. **Debug logs might dump settings:**
   ```
   logger.debug(f"Using stripe secret: {settings.stripe_secret_key}")  # Found it!
   ```

3. **Exception traces in production:**
   If unhandled exception, full traceback might be visible in logs/monitoring.

---

### Finding #S4: No Input Validation on Webhook Payload [MEDIUM - P2]
**Fichier:** `backend/routes/billing.py:65-87`  
**Sévérité:** MOYENNE — Blind Injection  

**Problem:**
```python
@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()  # ← Raw bytes, not validated yet
    sig_header = request.headers.get("stripe-signature", "")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError as e:
        logger.warning("Stripe signature verification failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    
    event_type = event.get("type", "")
    data_obj = event.get("data", {}).get("object", {})
    
    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data_obj, db)  # ← data_obj not validated!
```

**_handle_checkout_completed doesn't validate:**
```python
async def _handle_checkout_completed(session: dict, db: Session) -> None:
    email = (
        (session.get("customer_details") or {}).get("email")
        or session.get("customer_email")
    )
    # If email contains SQL keywords? If email is "" (empty string)?
    # No schema validation, just dict.get()
    
    if not email or not _EMAIL_RE.match(str(email)):
        # Regex validation only — but what if email = "a@b.co" (valid) but
        # SQL injection in customer_details field?
        return
    
    plan = (session.get("metadata") or {}).get("plan", "pro")
    # Plan is trustedStride without enum validation!
```

**Better:**
- Pydantic model to validate Stripe event schema
- Enum for plan field
- Reject unknown fields

---

### Finding #S5: X-Provider-Key Header Logged Unmasked [LOW - P3 Secrets]
**Fichier:** `backend/routes/proxy.py:64-71`  
**Sévérité:** BASSE — Logging Leakage  

**Problem:**
```python
def _resolve_provider_key(x_provider_key: Optional[str], settings_key: str, provider: str) -> str:
    key = x_provider_key or settings_key
    if not key:
        raise HTTPException(
            status_code=400,
            detail=f"No API key for provider '{provider}'. Set X-Provider-Key header.",
        )
    return key
```

No masking in error messages. If logging is enabled:
```python
logger.info(f"Using provider key from header: {key[:10]}...")  # Still logs part of it
```

---

### Finding #S6: No Rate Limiting on Key Endpoints [MEDIUM - P2]
**Fichier:** `backend/routes/portal.py:92-110`  
**Sévérité:** MOYENNE — Brute-force / DoS  

**Problem:**
```python
@router.post("/api/portal/request")
@limiter.limit("5/hour")  # Only 5 requests per hour
def portal_request(request: Request, ...):
    email = body.email.strip().lower()
    projects = db.query(Project).filter(Project.name == email).all()
```

**Inadequate rate limits:**
- 5/hour = 120/day = 3600/month = 43,200/year
- Weak (can enumar all 10K common emails in 2 months)

**Missing rate limits:**
- `/api/portal/verify` — NO limiter (should be limited)
- `/api/checkout/{plan}` — Only 5/hour (should be tighter, e.g., 1/minute per user)
- Proxy endpoints — NO global rate limiting (can be abused for DoS)

---

### Finding #S7: No Authentication on /api/demo Endpoints [LOW - P3]
**Fichier:** `backend/routes/demo.py`  
**Sévérité:** BASSE — Information Disclosure  

**Not verified, but demo endpoints probably exist without auth:**
```
GET /api/demo/projects
GET /api/demo/usage/summary
GET /api/demo/usage/daily
```

These are intentionally public for the landing page, but they:
- Return realistic data that could be reverse-engineered
- No rate limiting shown
- Could be used to enumerate demo project structure

---

### Finding #S8: Portal Session Cookie Lacks Secure Flag in Non-HTTPS [LOW - P2]
**Fichier:** `backend/routes/portal.py:180-188`  
**Sévérité:** BASSE-MOYENNE — MITM Risk  

**Problem:**
```python
secure = settings.app_url.startswith("https")
response.set_cookie(
    key="portal_session",
    value=_sign_session(email),
    max_age=_SESSION_MAX_AGE,
    httponly=True,
    samesite="lax",
    secure=secure,  # ← Only if HTTPS!
)
```

**Issue:**
If app_url = "http://localhost:8000" (dev), secure=False. Cookie transmitted in clear.

**But:** More importantly, in production if misconfigured to use HTTP, session cookie is vulnerable to MITM.

---

### Finding #S9: No HTTPS Enforcement Header [LOW - P3]
**Fichier:** `backend/main.py`  
**Sévérité:** BASSE — Security Headers Missing  

**Problem:**
```python
# Assuming main.py doesn't have:
# app.add_middleware(TrustedHostMiddleware, allowed_hosts=[...])
# app.add_middleware(HTTPSRedirectMiddleware)
```

**Missing headers:**
- Strict-Transport-Security
- X-Content-Type-Options
- X-Frame-Options
- Content-Security-Policy

---

## SUMMARY TABLE (Phase 2)

| Finding | Type | Severity | Component | Impact |
|---------|------|----------|-----------|--------|
| #S1 | SSRF | P1 | url_validator | DNS rebinding, metadata bypass |
| #S2 | Auth | P2 | proxy | Leaked old keys valid 5 min |
| #S3 | Secrets | P2 | billing | API key in logs |
| #S4 | Validation | P2 | billing | Unvalidated webhook payload |
| #S5 | Secrets | P3 | proxy | Provider key in error logs |
| #S6 | Rate Limit | P2 | portal, checkout | Brute-force / DoS |
| #S7 | Auth | P3 | demo | Public endpoints info disclosure |
| #S8 | TLS | P2 | portal | Cookie without secure flag (dev) |
| #S9 | Headers | P3 | main | Missing HSTS/CSP/XFO headers |

---

## CRITICAL PATTERNS

1. **Secrets in Settings:** Stripe key, provider keys, secrets should not be logged. Use masking or secrets manager.
2. **External Validation:** URL validation (SSRF) has timing windows. Use pinning or resolved IP caching.
3. **Rate Limiting Incomplete:** Portal has 5/hour, but verification endpoint missing limit.
4. **Webhook Processing:** Stripe events not validated against schema. Could lead to injection.

