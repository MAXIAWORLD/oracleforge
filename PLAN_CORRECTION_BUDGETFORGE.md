# Plan de Correction Complet BudgetForge
**Scope:** 30 findings (3 blockers, 9 P1, 6 P2, 12 P3)  
**NO CODE** — stratégie et étapes uniquement  
**Durée estimée:** 80-120 heures réparties sur 4-6 semaines

---

## 🎯 STRATÉGIE GÉNÉRALE

### Ordre de Correction (Impact x Urgence)

```
PHASE 0: Blockers (2-3 jours) — ARRÊTE tout, fix ces 3 bugs
  └─ #1: Budget lock multi-worker
  └─ #2: Portal email enumeration  
  └─ #3: Portal token all-projects access

PHASE 1: P1 Findings (3-5 jours) — Critique path, dépendant de Phase 0
  └─ #4: Stripe webhook duplication
  └─ #5: Float → Decimal migration
  └─ #9: Budget check race window
  └─ #S1: SSRF DNS rebinding
  └─ #S4: Webhook payload validation
  └─ #D1: Float precision in reports

PHASE 2: P2 Findings (1 semaine) — High severity, réduisent risque
  └─ #S2: API key rotation grace period
  └─ #S6: Rate limiting inadequate
  └─ #A1: Error messages leak details
  └─ #L1: Pricing UX
  └─ #6: Reset period timezone
  └─ #7: Downgrade chain validation
  └─ #8: Session/token TTL mismatch
  └─ #10: Project schema design
  └─ #S3: Secrets in logs

PHASE 3: P3 Findings (2 semaines) — Scaling + polish
  └─ #S5: Provider key logging
  └─ #S7: Demo endpoint auth
  └─ #S8: Cookie secure flag
  └─ #S9: HTTPS headers
  └─ #A2: HTTP status codes
  └─ #A3: Pydantic validation models
  └─ #F2: Portal frontend integration
  └─ #D2: Query performance
  └─ #D4: Caching layer

DEPLOY PROD: Avec alerte monitoring 24/7
```

---

## 📍 PHASE 0: BLOCKERS (2-3 jours)

### BLOCKER #1: Budget Lock Multi-Worker Race Condition

**Current State:**
- `budget_lock.py` utilise `asyncio.Lock` in-memory, per-process
- Déploiement multi-worker (2-4) → chaque worker a sa propre copie de lock
- Deux requests simultanés = deux locks indépendants → bypass

**Strategy A: Database-Level Locking (RECOMMANDÉ)**

1. **Ajouter une table de versioning:**
   ```
   budget_lock_version:
     - project_id (PK)
     - version (int)  # Incremented on each write
     - locked_at (timestamp)
   ```

2. **Remplacer budget_lock.py:**
   - Remove in-memory asyncio.Lock
   - New budget_lock function uses optimistic locking:
     - Read project.budget_lock_version
     - Do budget check + prebill
     - UPDATE with WHERE version = old_version
     - If UPDATE fails (row count = 0), retry from start
   - Max retries = 3, else raise 429 Too Many Requests

3. **Avantages:**
   - Works across all workers
   - Database handles concurrent writes atomically
   - No separate lock service needed

4. **Risques:**
   - Retry loop could increase latency
   - High contention projects might retry often
   - Mitigation: Backoff + jitter on retries

5. **Tests à écrire:**
   - Parallel request simulation (2+ workers)
   - Budget never exceeds limit under concurrent load
   - Idempotence: same request twice = billed once

**Temps:** 1-2 jours (+ test)

---

**Strategy B: Message Queue (Alternative)**

1. All requests enqueue to single budget-processing worker
2. Sequential processing guarantees budget integrity
3. Trade-off: Latency increases, throughput decreases

**Not recommended for this product** (real-time API).

---

### BLOCKER #2: Portal Email Enumeration

**Current State:**
- `/api/portal/request` returns `{"ok": true}` silently whether email exists
- Rate limit: 5/hour = brute-force 10K emails in 3 months

**Strategy:**

1. **Return `{"ok": true}` for ALL emails** (known + unknown)
   - Don't check if Project exists
   - Just return success
   - Attacker can't enumerate by response

2. **Add timing randomization:**
   - If email exists: 50-100ms delay
   - If email doesn't exist: 50-100ms delay + random jitter
   - Prevents timing attack

3. **Increase rate limit:**
   - Change from 5/hour to 1/minute per IP (if sending email)
   - Add CAPTCHA after 5 attempts per IP per hour
   - Log suspicious patterns (100+ requests from one IP)

4. **Security headers:**
   - Add `X-Content-Type-Options: nosniff`
   - Prevent MIME type detection attacks

5. **Tests:**
   - Confirm endpoint always returns 200 + `{"ok": true}`
   - Verify timing is unpredictable
   - Rate limiting blocks at correct threshold

**Temps:** 1 jour

---

### BLOCKER #3: Portal Token Grants All-Projects Access

**Current State:**
- Portal token validates email
- System returns API keys for ALL projects of that email
- Token should be 1:1 with a project, not 1:N

**Strategy: Redesign Token Model**

1. **Change PortalToken schema:**
   ```
   PortalToken:
     - token (unique, indexed)
     - project_id (FK to Project, NOT email)
     - expires_at
     - used (boolean, for single-use enforcement)
   ```
   - Remove: email field
   - Add: project_id field

2. **Change /api/portal/request flow:**
   - Input: email + project_id (both required)
   - Validate: Project exists AND project.name == email
   - Create token linked to that PROJECT
   - Send magic link with token (same as before)

3. **Change /api/portal/verify flow:**
   - Token maps to single project_id
   - Return ONLY that project's API key + metadata
   - Create session cookie valid for that project only

4. **Change /api/portal/usage flow:**
   - Already correct (filters by project_id from query param)

5. **Changes needed:**
   - `PortalToken` model: add project_id, remove email
   - `portal_request` endpoint: require project_id param
   - `portal_verify`: return single project instead of list
   - `portal_session`: return single project instead of list
   - Frontend: request magic link for specific project (not email)

6. **Tests:**
   - Verify token only grants access to specified project
   - Other projects still require separate tokens
   - Sharing token with attacker = access to 1 project only

**Caveat:** 
- User experience changes slightly (can't request "all projects at once")
- But much more secure + aligned with OAuth patterns

**Temps:** 1.5-2 jours (+ migrations)

---

## 📍 PHASE 1: P1 FINDINGS (3-5 jours)

### P1 #4: Stripe Webhook Duplicate Project Creation

**Current State:**
- Idempotence check only if subscription_id exists
- Free plans sometimes omit subscription_id → duplicate on retry

**Strategy:**

1. **Add secondary idempotence key:**
   - Use: email + session_id (Stripe checkout session is unique)
   - Query: WHERE email = ? AND stripe_checkout_session_id = ?
   - Store checkout_session_id in Project table (new column)

2. **Stripe event validation:**
   - Webhook can be replayed by Stripe (same event_id multiple times)
   - Use event.id as primary key in Event log table (new table)
   - Only process event if NOT already logged

3. **Atomicity:**
   - Single INSERT with CHECK constraint:
     - If subscription_id: unique on subscription_id
     - If no subscription_id: unique on email + checkout_session_id

4. **Tests:**
   - Send checkout.session.completed twice → only 1 project created
   - Free plan + Pro plan → different projects, both created once

**Temps:** 1-1.5 jours

---

### P1 #5: Float → Decimal Migration

**Current State:**
- budget_usd, cost_usd, max_cost_per_call_usd all Float
- Rounding to 9 decimals in portal, 6 in history
- IEEE 754 precision loss accumulates

**Strategy:**

1. **Decision: Store as Decimal in DB**
   - Decimal(precision=10, scale=4) for USD amounts
   - Allows up to $999,999.9999 with 4 decimals (cents + 1)
   - Accurate for all financial calculations

2. **Migration path:**
   - Create NEW columns: budget_usd_decimal, cost_usd_decimal, etc.
   - Backfill: Cast existing Float values to Decimal
   - Test: Verify no data loss in conversion
   - Update queries to use new columns
   - Drop old Float columns

3. **Python side (SQLAlchemy):**
   - Use `sqlalchemy.types.Numeric` with (10, 4)
   - SQLAlchemy automatic conversion Float ↔ Decimal

4. **Display formatting:**
   - Always show 2 decimals in UI: `${amount:.2f}`
   - Store 4 decimals in DB for accuracy

5. **Tests:**
   - Round-trip: float input → decimal storage → float output (no loss)
   - Sum of individual costs = aggregate cost
   - Audit reconciliation (external vs internal)

**Temps:** 2-3 jours (migration + testing)

---

### P1 #9: Budget Check Happens Before Lock

**Current State:**
```
1. _check_budget() reads used from DB (unlocked)
2. _check_budget() validates used < budget
3. THEN acquire lock
4. THEN prebill
```

Race window between step 2 and 3.

**Strategy:**

1. **Move entire validation into lock scope:**
   ```
   async with budget_lock(project.id):
       used = proxy_dispatcher.get_period_used_sql(...)
       final_model = guard.check(used, ...)
       usage_id = proxy_dispatcher.prebill_usage(...)
   ```

2. **Extract helpers:**
   - Move `_check_budget()` logic into the lock
   - Keep API endpoint clean

3. **Performance impact:**
   - DB query now inside lock → lock held longer
   - Mitigation: Query is fast (<10ms), acceptable

4. **Tests:**
   - Concurrent requests: lock prevents interleaving
   - No request passes if total exceeds budget

**Temps:** 0.5-1 jour

---

### P1 #S1: SSRF DNS Rebinding Bypass

**Current State:**
- `is_safe_webhook_url()` validates URL once at setup
- DNS resolved again during webhook sending
- Attacker can rebind DNS between validation and send

**Strategy A: IP Pinning (RECOMMENDED)**

1. **Store resolved IP in Project:**
   - New column: webhook_resolved_ip (if webhook_url set)
   - During webhook setup: resolve DNS, store IP
   - During webhook send: use stored IP directly (bypass DNS)

2. **Implementation:**
   - `dns.resolve(hostname) → IP`
   - Store IP in DB
   - Pass IP to HTTP client (httpx with custom host override)

3. **Trade-off:**
   - If webhook host changes IP, webhook breaks (acceptable)
   - Admin must reconfigure if IP changes

4. **Tests:**
   - Webhook URL with rebinding attack = blocked (uses pinned IP)

**Temps:** 1-1.5 jours

---

**Strategy B: In-Band Verification (Alternative)**

1. Challenge-response webhook:
   - Send webhook with nonce
   - Expect challenge response from same IP
   - Only then activate webhook

Too complex for this phase.

---

### P1 #S4: Stripe Webhook Unvalidated Payload

**Current State:**
- Stripe signature verified ✓
- But event fields not validated against schema

**Strategy:**

1. **Create Pydantic models for Stripe events:**
   ```
   StripeCheckoutSession:
     - customer: str (optional)
     - customer_email: str (optional, email regex)
     - customer_details: {...} (dict, optional)
     - metadata: {...} (dict with plan enum)
     - subscription: str (optional)
     - subscription_id: str (optional)  ← Standardize naming
   ```

2. **Validate in webhook handler:**
   - Parse event JSON → Pydantic model
   - Raises validation error if mismatch
   - Prevents injection via unexpected fields

3. **Enum for plan:**
   - Valid values: "free", "pro", "agency" only
   - Reject "ltd" (deprecated)

4. **Tests:**
   - Valid event → processed
   - Invalid email format → rejected
   - Unknown plan → rejected
   - Extra fields → stripped (pydantic default)

**Temps:** 1 jour

---

### P1 #D1: Float Precision in Reports

**Current State:**
- `history.py:118`: `round(total_cost, 6)`
- `portal.py:146`: `round(spend, 9)`
- Should be 2 decimals max

**Strategy:**

1. **Standardize all rounding to 2 decimals:**
   - Change all `round(x, 6)` and `round(x, 9)` to `round(x, 2)`
   - Format for display: `f"{amount:.2f}"`

2. **After Decimal migration (P1 #5):**
   - Decimal type ensures precision automatically
   - Rounding only needed for display

3. **Tests:**
   - Reports show USD with 2 decimals exactly
   - No floating point artifacts ($10.000000)

**Tempo:** 0.5 dias (post-migration)

---

## 📍 PHASE 2: P2 FINDINGS (1 semaine)

### P2 #S2: API Key Rotation Grace Period Too Long

**Current State:**
- 5 minutes grace period for old key
- Leaked key can be exploited immediately

**Strategy:**

1. **Option A: Reduce to 30 seconds**
   - Change `_GRACE_PERIOD_MINUTES = 5` to 0.5
   - Fast rotation, minimal compatibility window
   - Risk: Older clients using old key miss 30s window

2. **Option B: Eliminate grace period entirely**
   - Old key invalid immediately
   - New key only valid after rotation
   - Risk: Race condition if client hasn't received new key yet

3. **Option C: In-band rotation (Future)**
   - Client signs with both old + new key
   - Server accepts either
   - Eliminates grace period entirely

**Recommendation:** Option A (30 seconds) for now.

**Temps:** 0.5 jour

---

### P2 #S6: Rate Limiting Inadequate

**Current State:**
- `/api/portal/request`: 5/hour (inadequate for enumeration)
- `/api/portal/verify`: NO limit
- `/api/checkout/{plan}`: 5/hour (too strict)
- Proxy endpoints: NO global limit (DoS risk)

**Strategy:**

1. **Portal request:**
   - Increase to 10/hour globally (less vulnerable)
   - OR: 2/hour per IP (more effective)
   - Add CAPTCHA after 3 failed attempts

2. **Portal verify:**
   - Add 10/hour global limit
   - OR: 5/hour per IP

3. **Checkout:**
   - Keep 5/hour global (reasonable for signups)
   - OR: 2/minute per IP (more UX friendly)

4. **Proxy endpoints:**
   - Add soft limit: log if project exceeds 100 req/min
   - Alert ops on sustained >500 req/min per project
   - Hard limit: 1000 req/min per project (graceful degrade)

5. **Implementation:**
   - Use existing limiter dependency (already in project)
   - Add Redis backend for distributed rate limiting
   - OR: In-memory with cleanup on startup (acceptable for <100 projects)

**Temps:** 1-1.5 jours

---

### P2 #A1: Error Messages Leak Budget Details

**Current State:**
```python
detail=f"Budget exceeded for project '{project.name}'. Used: ${used:.4f} / ${project.budget_usd:.2f}"
```

Attacker learns exact remaining budget.

**Strategy:**

1. **Generic error message:**
   ```
   detail="Budget limit exceeded. Contact support for details."
   ```

2. **Detailed error in logs (server-side only):**
   ```
   logger.warning(f"Budget exceeded for {project.id}: used={used}, budget={budget}")
   ```

3. **Apply across all endpoints:**
   - Search for all `HTTPException` + budget messages
   - Replace with generic text
   - Keep logs detailed

4. **Tests:**
   - Error message doesn't reveal amounts
   - Logs still contain full details

**Temps:** 0.5 jour

---

### P2 #L1: Pricing UX — Free Plan Value Prop

**Current State:**
- Free: 0-1 projects (looks broken)
- Pro: 10 projects
- Agency: unlimited

Confusing why Free exists if 0 projects.

**Strategy:**

1. **Change Free plan:**
   - From: 0-1 projects
   - To: 1 project (small limit, reasonable trial)
   - Marketing: "Perfect for testing"

2. **Update pricing cards:**
   - Free: "1 project, 5 API keys, basic alerts"
   - Pro: "10 projects, unlimited keys, premium support"
   - Agency: "Unlimited everything"

3. **Landing page:**
   - Add CTA on Free card: "Start free, no card required"
   - Add comparison table (features per plan)

4. **Tests:**
   - New Free projects can create 1 project
   - Cannot create 2nd without upgrading

**Temps:** 1 jour (product + engineering)

---

### P2 #6: Reset Period Timezone

**Current State:**
- Monthly/weekly resets always UTC
- Users in LA see "reset" at 5 PM instead of midnight

**Strategy:**

1. **Add timezone field to Project:**
   - `reset_timezone: str` (e.g., "America/Los_Angeles", default "UTC")
   - Use pytz or zoneinfo library

2. **Update `get_period_start()`:**
   - Convert user's timezone to local midnight
   - Then calculate period start in UTC for storage

3. **Dashboard:**
   - Show reset time in user's local timezone
   - Display: "Budget resets daily at midnight Pacific Time"

4. **Tests:**
   - User in LA + monthly reset = resets on 1st at 00:00 LA
   - Verified against UTC equivalent

**Temps:** 1-1.5 jours

---

### P2 #7: Downgrade Chain Validation

**Current State:**
- No cycle detection (A→B→A possible)
- No cost validation (downgrade to same cost model)
- Empty chain = silent failure

**Strategy:**

1. **Add validation method:**
   - Check: chain has no cycles (use graph traversal)
   - Check: each model in chain is in _DOWNGRADE_MAP or built-in
   - Check: chain terminates at Ollama fallback or valid model

2. **On project update (set downgrade_chain):**
   - Validate chain
   - Reject if invalid (return 400 Bad Request)

3. **On budget check:**
   - If no valid downgrade found, use built-in map
   - If built-in map empty, block request (same as before)

4. **Tests:**
   - Cycle detection catches A→B→A
   - Invalid model in chain rejected at save time
   - Empty chain doesn't crash

**Temps:** 1 dia

---

### P2 #8: Session TTL Mismatch

**Current State:**
- Token TTL: 1 hour
- Session cookie TTL: 90 days

**Strategy:**

1. **Align TTLs:**
   - Option A: Reduce cookie to 1 hour (safer, requires re-auth)
   - Option B: Extend token to 7 days (less secure, but more UX friendly)
   - Option C: Implement refresh token pattern

2. **Recommendation: Option A + refresh pattern**
   - Session cookie: 1 hour (same as token)
   - Silent refresh: when user active, extend cookie to 1 more hour
   - After 1 hour idle: force re-auth

3. **Implementation:**
   - Session middleware: check cookie age
   - If >55 minutes: force redirect to `/portal?token=...` (refresh)
   - Else: extend cookie max-age by 1 hour

4. **Tests:**
   - Session expires after 1 hour idle
   - Active session extends automatically
   - Compromised session token = 1 hour max access

**Temps:** 1-1.5 jours

---

### P2 #10: Project Schema Design

**Current State:**
- `Project.name` is email (unique, indexed)
- Assumes 1:1 email → project
- Actually many:1 email → projects (confusing)

**Strategy:**

1. **Add new columns:**
   - `owner_email: str` (FK to User table — future)
   - `display_name: str` (user-friendly name like "Production", "Testing")

2. **Keep backward compatibility:**
   - Still allow `name` = email for existing projects
   - But allow `display_name` to differ

3. **Dashboard:**
   - Display `display_name` instead of `name`
   - Show owner email separately

4. **Future migration (Post-Phase 0):**
   - Create User table (separate authentication context)
   - Migrate email → User.id FK
   - Make display_name required

5. **Tests:**
   - Multiple projects per email work correctly
   - Display names don't collide

**Temps:** 1.5-2 jours (+ migration)

---

### P2 #S3: Secrets in Logs

**Current State:**
- Stripe key passed to stripe.Webhook.construct_event()
- Could appear in error traces
- Provider keys in headers (could be logged)

**Strategy:**

1. **Set Stripe key once at startup:**
   - In main.py or FastAPI app initialization
   - Not in every route

2. **Mask secrets in error handling:**
   - Create custom exception handler
   - Log full error server-side (secure logging)
   - Return generic message to client

3. **Provider key headers:**
   - Don't log X-Provider-Key header value
   - Log only: "X-Provider-Key present" or "missing"

4. **Tests:**
   - Verify secrets never appear in logs
   - Error pages show generic messages only

**Tiempo:** 1 día

---

## 📍 PHASE 3: P3 FINDINGS (2 semaines)

### P3 #S5, #S7, #S8, #S9: Security Polish

**Strategy — Batch these together:**

1. **#S5 - Provider key logging:**
   - Mask provider key in log output (first 10 chars only)
   - Already handled if logging middleware fixed in #S3

2. **#S7 - Demo endpoint auth:**
   - Demo endpoints intentionally public (for landing page)
   - Add rate limiting: 100 req/hour globally
   - Document: "Demo data is read-only and public"
   - No action needed if design is intentional

3. **#S8 - Cookie secure flag:**
   - Already correct in code (secure=settings.app_url.startswith("https"))
   - In dev (http://localhost), secure=False (expected)
   - In prod (https://...), secure=True (correct)
   - No fix needed

4. **#S9 - HTTPS headers:**
   - Add middleware at startup:
     - Strict-Transport-Security: max-age=31536000
     - X-Content-Type-Options: nosniff
     - X-Frame-Options: DENY
     - X-XSS-Protection: 1; mode=block
     - Content-Security-Policy: default-src 'self'

**Temps:** 1-1.5 jours

---

### P3 #A2, #A3: API Contract

1. **#A2 - HTTP status codes:**
   - Consider 402 Payment Required for budget exceeded (nice-to-have)
   - Can fix post-launch

2. **#A3 - Pydantic models:**
   - Add request/response models for type safety
   - Not critical for functionality
   - Can do incremental (10% of routes per week)

**Temps:** 1 semaine (piecemeal)

---

### P3 #F2: Portal Frontend Integration

**Strategy:**

1. **Verify portal page renders after token verification**
2. **Test session persistence (90d cookie)**
3. **Test logout/re-auth flow**
4. **Fix any UI issues (layout, responsive, dark mode)**

**Temps:** 2-3 jours (QA + minor fixes)

---

### P3 #D2, #D4: Performance

1. **#D2 - Query optimization:**
   - Add indexes on `Usage.project_id`, `Usage.created_at`
   - Monitor slow queries in production

2. **#D4 - Caching layer:**
   - Cache portal usage aggregation (5 min TTL)
   - Cache demo data (1 min TTL)
   - Use Redis if available, else in-memory with cleanup

**Temps:** 1-1.5 jours

---

## 🚀 DEPLOYMENT STRATEGY

### Pre-Deployment Checklist

- [ ] All Phase 0 blockers fixed + tested
- [ ] All Phase 1 P1 findings fixed + tested
- [ ] Database migrations tested (Decimal, new columns)
- [ ] Load test with 2+ workers (budget concurrency)
- [ ] Security audit of SSRF + webhook changes
- [ ] Monitoring alerts configured:
  - Budget overages
  - Duplicate projects
  - Authentication failures
  - Query timeouts

### Deployment Plan

1. **T=0:** Deploy to staging, run full test suite
2. **T+2h:** Manual QA (browser testing, API calls)
3. **T+4h:** Load test (100 concurrent users)
4. **T+6h:** Deploy to prod (blue-green, if possible)
5. **T+7h:** Monitor 24/7 for first 7 days
6. **T+30d:** Post-deployment retrospective

### Rollback Plan

- Keep previous DB schema (migrations are reversible)
- Keep old float columns during transition
- If P0 issue found: rollback within 1 hour
- Alert Alexis immediately on any budget overage

---

## 📋 SUMMARY TABLE

| Phase | Blockers | P1 | P2 | P3 | Days | Cumulative |
|-------|----------|----|----|----|----|---------|
| 0     | 3        | -  | -  | -  | 2-3 | 2-3 |
| 1     | -        | 6  | -  | -  | 3-5 | 5-8 |
| 2     | -        | -  | 9  | -  | 7   | 12-15 |
| 3     | -        | -  | -  | 12 | 14  | 26-29 |
| QA    | -        | -  | -  | -  | 3-5 | 29-34 |
| **TOTAL** | **3** | **6** | **9** | **12** | **29-34** | **29-34** |

---

## 👥 TEAM ASSIGNMENT (Recommendations)

**Phase 0 (Blockers):**
- 1 senior backend (budget lock)
- 1 senior backend (portal redesign)
- Duration: 2-3 days

**Phase 1 (P1):**
- 2 backend + 1 DBA (Decimal migration)
- 1 backend (SSRF, webhook validation)
- Duration: 3-5 days

**Phase 2 (P2):**
- 2 backend (rate limiting, error handling)
- 1 frontend (pricing UX)
- 1 DevOps (monitoring setup)
- Duration: 1 week

**Phase 3 (P3):**
- 1 backend (API models, caching)
- 1 frontend (portal integration)
- 1 QA (full integration testing)
- Duration: 2 weeks

**Total:** 4-5 engineers, 4-6 weeks end-to-end

---

## 🎯 SUCCESS CRITERIA

✅ All Phase 0 tests pass (budget integrity, email privacy, token scope)
✅ All Phase 1 tests pass (no race conditions, float accuracy, SSRF protection)
✅ Phase 2 findings resolved (rate limiting works, error messages generic)
✅ Staging = Prod, no regressions in demo or dashboard
✅ Load test: 2+ workers sustain 100 concurrent users without budget bypass
✅ Security audit passes (SSRF, webhook, rate limiting)
✅ Monitoring alerts functional + tested

---

## ⚠️ RISKS & MITIGATIONS

| Risk | Mitigation |
|------|-----------|
| Decimal migration breaks existing queries | Test thoroughly on staging, keep float columns until verified |
| Portal redesign breaks existing workflows | Feature-flag new token model, gradual rollout |
| Database locking adds latency | Benchmark on staging, set acceptable threshold |
| Rate limiting too strict | Start permissive (10/hour), tighten based on usage |
| Timezone changes break reset logic | Extensive testing, log all period start calculations |

