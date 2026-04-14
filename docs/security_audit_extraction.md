# MAXIA Oracle — Phase 2 security audit on extracted modules

**Date** : 14 avril 2026
**Session** : audit sécurité sur le code extrait de MAXIA V12 en Phase 1
**Plan** : `oracleforge/docs/plan-maxia-oracle-2026-04-14.md` §3 Phase 2
**Scope** : `oracleforge/backend/` uniquement (3 modules oracle + core/)

Ce document est le délivrable Phase 2 (cf. plan §3 Phase 2 "Délivrable :
`oracleforge/docs/security_audit_extraction.md`"). Chaque vulnérabilité de
`MAXIA V12/AUDIT_COMPLET_V12.md` est listée, son applicabilité à MAXIA Oracle
est évaluée, et le fix appliqué (ou sa phase cible) est documenté.

Référence source : `MAXIA V12/AUDIT_COMPLET_V12.md` — 6 critiques, 14 hautes,
26 moyennes, 19+ basses, score global 58/100.

---

## 1. Verdict global

**MAXIA Oracle Phase 2 état** : **clean**.

| Catégorie | État |
|---|---|
| Hardcoded secrets dans le code extrait | **0 trouvé** ✅ |
| Weak crypto (MD5/SHA1) | **0 trouvé** ✅ |
| `str(e)` retourné au client (H12) | **5 call sites patchés** → `safe_error()` ✅ |
| Logs qui pourraient leaker `api-key=` dans RPC URL | **0 call site** (helper `get_rpc_url_safe()` présent) ✅ |
| SSRF via user-controlled URL | **0 call site** ✅ |
| Input validation sur `feed_id` | **Ajouté** (64-char hex) ✅ |
| Validation startup stricte (C5) | Différé — voir §4 |
| JWT_SECRET persistant (C6) | N/A — pas d'auth avant Phase 3 |
| Rate limiting persistant (H7) | N/A — pas d'app avant Phase 3 |
| Security headers HTTP (H9) | N/A — pas d'app avant Phase 3 |
| Swagger public (H11) | N/A — pas d'app avant Phase 3 |

**Aucun secret n'a été exposé par les modules oracle extraits.** Le MAXIA V12
audit avait trouvé les 6 critiques et la majorité des 14 hautes dans des
**fichiers non extraits** (`main.py`, `auth.py`, `agent_credit_score.py`,
`escrow_client.py`, `public_api.py`, etc.). Les modules oracle (`pyth_oracle`,
`chainlink_oracle`, `price_oracle`) étaient listés dans la section §8 "Ce qui
fonctionne bien" de l'audit V12. Notre extraction conserve cette propriété.

---

## 2. Vulnérabilités critiques V12 vs MAXIA Oracle

### C1 — Secret HMAC hardcodé `maxia-credit-2026`
- **Source** : `MAXIA V12/backend/agent_credit_score.py:21`
- **Applicable à MAXIA Oracle** : **Non**. Le module `agent_credit_score.py`
  n'est pas extrait (credit score = scope régulé).
- **Vérification proactive** : `grep -iE '(api[_-]?key|secret|password|token)\s*=\s*"[^"$]{10,}"'`
  sur `oracleforge/backend/` → **0 match**.

### C2 — Endpoint GPU public sans auth
- **Source** : `MAXIA V12/backend/main.py:3895`
- **Applicable** : **Non**. Pas de GPU, pas de route `/api/public/gpu/rent`.

### C3 — Admin key en URL query parameter
- **Source** : `MAXIA V12/backend/main.py:1443`
- **Applicable** : **Non**. Aucune route admin extraite. À re-vérifier si/quand
  une route admin est ajoutée en Phase 3.

### C4 — `ESCROW_PRIVKEY_B58` en `.env` sans KMS
- **Source** : `MAXIA V12/backend/config.py:62-66`
- **Applicable** : **Non**. Surgery volontaire en Phase 1 — le nouveau
  `oracleforge/backend/core/config.py` (83 lignes) ne touche jamais à
  `ESCROW_PRIVKEY_B58`. MAXIA Oracle n'a pas d'escrow, pas de custody.

### C5 — Secrets sans validation startup stricte
- **Source** : `MAXIA V12/backend/config.py:7-12`
- **Applicable à MAXIA Oracle** : **Partiellement**, mais différé.
- **Raison du différé** : en l'état actuel, **aucune** variable d'environnement
  n'est strictement requise par les modules oracle. Toutes ont un fallback
  public (Pyth Hermes public, Chainlink public Base, CoinGecko public, etc.).
  La validation stricte deviendra pertinente :
    - Phase 3 quand on aura `X-API-Key` pour les clients MAXIA Oracle
    - Phase 4 quand on configurera un wallet x402 (secret server-side)
    - Phase 7 (deploy VPS) quand on validera que les env Helius/Chainstack
      sont bien injectées en prod vs juste absentes
- **Action Phase 2** : ajouter une TODO explicite dans `core/config.py`
  pointant vers les phases cibles. Ne PAS masquer le risque.

### C6 — `JWT_SECRET` aléatoire (sessions perdues au restart)
- **Source** : `MAXIA V12/backend/auth.py:28-39`
- **Applicable** : **Différé Phase 3**. Pas d'authentification avant la
  Phase 3 (API FastAPI). Quand Phase 3 ajoutera `X-API-Key`, on n'aura
  probablement pas de JWT du tout (API key simple stockée en DB). Si JWT
  devient nécessaire plus tard, on suivra le pattern "validate-at-startup +
  persistent secret" dès le départ.

---

## 3. Vulnérabilités hautes V12 vs MAXIA Oracle

### H1 — Endpoints "coming soon" / 404 camouflés
- **Applicable** : **Non**. Pas de routes stub dans MAXIA Oracle.

### H2 — Sandbox fake data en production
- **Applicable** : **Non**. Pas de mode sandbox.

### H3, H4, H5, H6 — CEO executor / escrow startup / tier logic / dynamic pricing
- **Applicable** : **Non** (aucun de ces modules extrait).

### H7 — Rate limiting in-memory non persistant
- **Applicable** : **Différé Phase 3**. Il n'y a pas encore de rate limiter.
  Phase 3 devra implémenter un rate limiter **DB-backed** (pas `dict` en
  mémoire) pour le free tier 100 req/jour.

### H8 — Injection SQL ORDER BY
- **Applicable** : **Non**. Les modules oracle extraits n'exécutent aucune
  requête SQL (ils parlent HTTP à des APIs externes + font des lookups dans
  des dicts Python en mémoire).

### H9 — Security headers absents
- **Applicable** : **Différé Phase 3**. L'app FastAPI n'existe pas encore.
  Phase 3 devra ajouter un middleware qui injecte :
    - `Content-Security-Policy` (même si V1 n'a pas de frontend, protège
      l'éventuelle landing page Phase 8)
    - `X-Frame-Options: DENY`
    - `X-Content-Type-Options: nosniff`
    - `Strict-Transport-Security` (activé uniquement sur le vhost HTTPS)
    - `Referrer-Policy: strict-origin-when-cross-origin`

### H10 — XSS via innerHTML
- **Applicable** : **Non** (pas de frontend Phase 1-7). Phase 8 landing page
  sera statique.

### H11 — Swagger UI public (559 endpoints exposés)
- **Applicable** : **Différé Phase 3**. À Phase 3, le `FastAPI(...)` doit être
  instancié avec `docs_url=None, redoc_url=None, openapi_url=None` en
  production (override possible en dev via env var).

### H12 — `str(e)` retourné aux clients
- **Applicable** : **OUI — patché en Phase 2**. Voir §4.1.

### H13 — Race condition TOCTOU solde sandbox
- **Applicable** : **Non** (pas de solde sandbox).

### H14 — IP whitelist CEO optionnelle
- **Applicable** : **Non** (pas d'endpoint CEO).

---

## 4. Fixes appliqués en Phase 2

### 4.1 — Correctif H12 : centralisation de la gestion d'erreur

**Problème** : les 3 modules oracle avaient 5 call sites qui retournaient
`{"error": f"... {str(e)[:100]}", "source": "..."}` aux clients. Le `str(e)`
peut contenir des paths système (`/etc/...`, `C:/...`), des noms de tables
SQL, des IPs internes, des versions de lib, etc.

**Fix** : nouveau module `backend/core/errors.py` avec `safe_error()` qui :
1. log le **type** de l'exception + le contexte + le traceback complet côté
   serveur (via `exc_info=True`)
2. retourne au client uniquement `"{context} ({ExceptionType})"` — jamais
   `str(exc)`, jamais le traceback

**Call sites patchés** :

| Fichier | Ligne V1 | Avant | Après |
|---|---|---|---|
| `pyth_oracle.py` | 366 | `f"Pyth error: {str(e)[:100]}"` | `safe_error("Pyth Hermes fetch failed", e, logger)` |
| `pyth_oracle.py` | 410 | `str(e)[:100]` | `safe_error("Pyth on-chain verification failed", e, logger)` |
| `pyth_oracle.py` | 454 | `f"Finnhub error: {str(e)[:100]}"` | `safe_error("Finnhub fetch failed", e, logger)` |
| `chainlink_oracle.py` | 177 | `str(e)[:100]` | `safe_error(f"Chainlink eth_call failed for {sym}", e, logger)` |
| `chainlink_oracle.py` | 239 | `str(e)[:100]` | `safe_error(f"Chainlink feed verification failed for {sym}", e, logger)` |

**Vérification** : `grep 'str(e)' oracleforge/backend/` → 1 seul match
restant, dans le docstring de `core/errors.py` lui-même qui documente le
fix (pas du code).

**Test manuel de non-régression leak** :
```python
>>> from core.errors import safe_error
>>> try:
...     raise ValueError("secret internal path /etc/passwd")
... except Exception as e:
...     msg = safe_error("fetch failed", e, logging.getLogger("test"))
>>> msg
'fetch failed (ValueError)'
>>> "/etc/passwd" in msg
False
```
Le traceback complet apparaît dans les logs serveur, pas dans la réponse client.

### 4.2 — Input validation sur `feed_id` Pyth

**Problème** : `get_pyth_price(feed_id: str, hft: bool = False)` acceptait
n'importe quelle string sans validation. Un appelant malicieux (via SDK ou
route en Phase 3) pourrait :
- Polluer le cache `_price_cache` avec des clés arbitraires jusqu'à
  déclencher l'eviction LRU (mémoire bornée, mais comportement observable)
- Générer du trafic gaspillé vers `hermes.pyth.network` avec des IDs invalides
- Théoriquement tenter une injection dans les query params HTTP (mitigée par
  l'encoding `httpx params=`)

**Fix** : nouveau helper `_is_valid_feed_id(feed_id)` dans `pyth_oracle.py`
qui vérifie :
- `isinstance(feed_id, str)`
- `len(feed_id) == 64`
- Tous les caractères sont dans `[0-9a-f]` (case-insensitive)

Early-return `{"error": "invalid feed_id format", "source": "pyth"}` avant
d'incrémenter les métriques, avant de toucher au cache, avant tout appel réseau.

**Propagation transitive** : `verify_price_onchain()` appelle
`get_pyth_price(feed_id, hft=True)` en interne, donc la validation s'applique
aussi à cette fonction sans modification directe.

`get_batch_prices()` accepte des `symbols` (tickers, pas des feed_ids) et
effectue le lookup via `ALL_FEEDS.get(lookup)` qui retourne soit un feed_id
connu soit `None` — aucune string arbitraire ne peut atteindre le réseau.

### 4.3 — PEP 8 + type hints cleanup

Hors scope strict de sécurité mais fait pendant la passe d'édition :
- Imports réordonnés PEP 8 dans `chainlink_oracle.py` (stdlib / third-party / local)
- Docstrings `get_stock_price`/`get_crypto_price` mises à jour pour refléter
  Surgery B (plus de "source 5 : fallback statique")
- Annotations `list | None`, `float | None` explicites sur les signatures
  modifiées (Python 3.12 target)

---

## 5. Audits proactifs — résultats

### 5.1 — Hardcoded secrets (grep)

Pattern scanné :
```
grep -iE '(api[_-]?key|secret|password|token)\s*=\s*"[^"$]{10,}"' oracleforge/backend/
grep -iE 'Bearer\s+[A-Za-z0-9]' oracleforge/backend/
```
**Résultat** : 0 match. Les Pyth feed IDs en dur dans `EQUITY_FEEDS` /
`CRYPTO_FEEDS` / `CHAINLINK_FEEDS` ne sont pas des secrets — ce sont des
identifiants **publics** des feeds Pyth / adresses on-chain de contrats
Chainlink Base. Ils sont documentés sur `docs.pyth.network` et
`docs.chain.link`.

### 5.2 — Weak crypto

Pattern scanné : `grep -iE '(md5|sha1|hashlib\.(md5|sha1))' oracleforge/backend/`
**Résultat** : 0 match.

Le seul usage de `hashlib` dans MAXIA V12 était pour des **cache keys non
sécurisés** (moyenne #2 dans l'audit V12), pas pour de la crypto. Les
modules extraits n'utilisent aucun hash.

### 5.3 — Logs potentiellement leaky (api-key dans RPC URL)

`MAXIA V12/backend/core/config.py` avait un commentaire "V-20: Helius requires
API key in URL (no header option). Never log this URL." — un vrai risque.

Dans `oracleforge/backend/core/config.py` le helper `get_rpc_url_safe()` est
exposé et le docstring de `get_rpc_url()` rappelle la contrainte :
```python
def get_rpc_url() -> str:
    """Return the highest-priority Solana RPC URL currently configured.

    Never log the returned URL: it may contain an API key in the query string.
    Use get_rpc_url_safe() for log lines.
    """
```

**Vérification** : `grep 'get_rpc_url()' oracleforge/backend/` → 1 seul site
d'utilisation (`price_oracle.py` ligne 289, **utilisé pour fetch HTTP, pas
pour log**). Aucun call à `get_rpc_url()` n'est passé à `logger.*`, `print`,
ou `f"..."` dans un log.

### 5.4 — SSRF

Les URLs externes du code extrait sont **toutes hardcodées** (constantes de
module) :
- `https://mainnet.base.org` (Base mainnet RPC, via `BASE_RPC_URL` env)
- `https://hermes.pyth.network` (Pyth Hermes, via `PYTH_HERMES_URL` env)
- `https://api.coinpaprika.com/v1/tickers`
- `https://api.coingecko.com/api/v3/simple/price`
- `https://query1.finance.yahoo.com/v8/finance/spark`
- `https://query1.finance.yahoo.com/v7/finance/quote`
- `https://finnhub.io/api/v1/quote`

Les parts dynamiques sont des tickers / feed_ids contrôlés par des dicts
statiques (`TOKEN_MINTS`, `EQUITY_FEEDS`, `CRYPTO_FEEDS`, `CHAINLINK_FEEDS`,
`SYM_TO_COINPAPRIKA`, `SYM_TO_COINGECKO`) **jamais par l'utilisateur final**.
La seule partie user-controlled qui touche une URL est `feed_id` dans
`get_pyth_price`, désormais validée 64-char hex (§4.2).

Les env vars `BASE_RPC_URL`, `PYTH_HERMES_URL`, `SOLANA_RPC`, `CHAINSTACK_RPC`
sont **côté opérateur** (set par l'admin du service), pas user-controlled.
Elles peuvent pointer vers un endpoint privé sans risque d'exfiltration.

**Aucun risque SSRF identifié.**

### 5.5 — Input validation

| Fonction publique | Argument | Validation |
|---|---|---|
| `get_pyth_price(feed_id, hft)` | `feed_id` | **Ajouté** 64-char hex (§4.2) |
| `get_pyth_price` | `hft` | `bool` par typage |
| `verify_price_onchain(feed_id, ...)` | `feed_id` | Transitive via `get_pyth_price` |
| `get_stock_price(symbol)` | `symbol` | `.upper()` + dict lookup (safe) |
| `get_crypto_price(symbol)` | `symbol` | `.upper()` + dict lookup (safe) |
| `get_batch_prices(symbols)` | `symbols` | Iterable, lookup safe. Taille cappée à 50 dans la route Phase 3 (`api_batch_prices`) |
| `get_stock_price_finnhub(symbol)` | `symbol` | `.upper()` + passé à l'API Finnhub |
| `get_chainlink_price(symbol)` | `symbol` | `.upper()` + dict lookup |
| `verify_price_chainlink(symbol, expected_price, ...)` | `symbol`, `expected_price` | dict lookup + numeric |
| `get_prices(symbols=None)` | `symbols` | list ou None, lookup dans dict |

---

## 6. Items différés aux phases ultérieures

Ces items sont **volontairement différés** parce qu'ils concernent des
couches qui n'existent pas encore. Chaque report est tracé pour qu'une session
Claude future ne les oublie pas.

| Item V12 | Reporté à | Raison |
|---|---|---|
| C5 — validation startup stricte | **Phase 3 + Phase 7** | Aucun secret requis aujourd'hui. À revoir quand API key MAXIA Oracle, wallet x402, Helius prod seront en place. |
| C6 — JWT_SECRET persistant | **Phase 3** | Pas d'auth avant Phase 3. Décider alors JWT vs API key simple. |
| H7 — rate limiting persistant | **Phase 3** | Pas d'app FastAPI. Implémenter DB-backed rate limiter (pas in-memory dict). |
| H9 — security headers HTTP | **Phase 3** | Nécessite `FastAPI()` + middleware. |
| H11 — Swagger désactivé en prod | **Phase 3** | `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` en prod. |
| H10 — XSS via innerHTML | **Phase 8** | Landing statique, pas de innerHTML dynamique prévu, mais audit à refaire à la livraison. |

**Règle** : avant de merger Phase 3, relire ce tableau et vérifier que chaque
item marqué "Phase 3" est résolu.

---

## 7. Checkpoint 2 — état des questions du plan

Le plan §3 Phase 2 liste 4 questions Checkpoint :

| Question du plan | Réponse |
|---|---|
| Aucun secret hardcodé ? | ✅ OUI — 0 match sur le sweep, documenté §5.1 |
| Validation startup en place pour tous les secrets critiques ? | ⚠️ **Différé à Phase 3/7** — aucun secret n'est critique aujourd'hui (tous optionnels avec fallback public). Documenté §2 C5 et §6. |
| `safe_error()` utilisé partout ? | ✅ OUI — 5 call sites patchés, 0 `str(e)` restant dans le code exécutable. |
| Security headers configurés ? | ⚠️ **Différé à Phase 3** — pas d'app FastAPI à sécuriser encore. Documenté §3 H9 et §6. |

**Phase 2 est validée** sous réserve que les 2 items différés (C5 + H9)
soient revisités avant le merge de Phase 3. Ce document est la trace qui les
rend non-oubliables.
