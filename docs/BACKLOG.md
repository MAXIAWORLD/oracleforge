# Forge Suite — Backlog

**Derniere MAJ** : 12 avril 2026
**Status** : 5 CRITICAL resolus, 185 tests PASS

---

## 1. ISSUES RESTANTES (a fixer avant production)

### HIGH — Bloquant cloud deploy

- [ ] **H1 — Auth middleware global** : Ajouter API key auth sur TOUS les endpoints des 5 produits (sauf AuthForge qui l'a). Actuellement toutes les APIs sont ouvertes. `Produits: MissionForge, LLMForge, OracleForge, GuardForge, OutreachForge`
- [ ] **H2 — Rate limiting global** : Ajouter rate limiting sur les 5 produits sans. LLMForge endpoints appellent des APIs payantes sans throttle. `Produits: MissionForge, LLMForge, OracleForge, GuardForge, OutreachForge`
- [ ] **H3 — LLMRouter singleton** : MissionForge re-instancie LLMRouter a chaque requete HTTP, donc stats et budget caps sont perdus. Stocker dans `app.state` comme le MissionEngine le fait deja. `Fichiers: missionforge/backend/routes/llm.py:54, missionforge/backend/routes/chat.py:57`
- [ ] **H4 — Groq class variable** : `_groq_last_call` est un class variable partage entre instances = race condition. Migrer en instance variable. `Fichiers: missionforge/backend/services/llm_router.py:87, llmforge/backend/services/llm_router.py:73`
- [ ] **H5 — Email validation** : `RegisterRequest.email` accepte n'importe quel string de 3+ chars. Utiliser `pydantic.EmailStr`. `Fichiers: authforge/backend/core/models.py:43, outreachforge/backend/routes/outreach.py:11, outreachforge/backend/core/models.py:58`
- [ ] **H6 — _execute_step >50 lignes** : Splitter en methodes separees `_handle_rag_retrieve`, `_handle_llm_call`, etc. `Fichier: missionforge/backend/services/mission_engine.py`
- [ ] **H7 — Tests routes manquants** : Ajouter tests HTTP pour AuthForge routes (register/login/refresh/me), GuardForge routes (scan/vault/policies), OutreachForge routes (score/batch/personalize). `3 produits`
- [ ] **H8 — _oai() KeyError** : `.get("message", {}).get("content", "")` au lieu de `["message"]["content"]` pour gerer les reponses malformees. `Fichiers: missionforge/backend/services/llm_router.py, llmforge/backend/services/llm_router.py`
- [ ] **H9 — Password hashing faible** : PBKDF2-SHA256 100k iterations est le minimum. Migrer vers bcrypt (cost 12+) ou argon2id. `Fichier: authforge/backend/services/auth_service.py:31-35`
- [ ] **H10 — Vault in-memory** : Secrets perdus au restart. Persister les `VaultEntry` dans SQLAlchemy. Bloquer l'auto-generation de cle en prod (DEBUG=false). `Fichier: guardforge/backend/services/vault.py`
- [ ] **H11 — SECRET_KEY placeholder** : Valider au demarrage que SECRET_KEY != "change-me...". `Tous les produits`

### MEDIUM — Important mais pas bloquant

- [ ] **M1 — JWT secret = app secret** : `jwt_secret` fallback sur `secret_key`. Separer les deux. `Fichier: authforge/backend/core/config.py:25`
- [ ] **M2 — Security headers** : Ajouter middleware X-Content-Type-Options, X-Frame-Options, Referrer-Policy. `Tous les produits`
- [ ] **M3 — IngestRequest untyped** : `sources: list[dict]` → typer avec `IngestSource(path, tag)` Pydantic. `Fichier: missionforge/backend/routes/missions.py:26`
- [ ] **M4 — Cron naive datetime** : `datetime.now()` → `datetime.now(timezone.utc)` dans schedule_loop. `Fichier: missionforge/backend/services/mission_engine.py:356`
- [ ] **M5 — Error message leak** : `str(e)` renvoye au client. Logger server-side, renvoyer message generique. `Fichier: missionforge/backend/services/mission_engine.py:321`
- [ ] **M6 — _per_key_cost unbounded** : Dict qui grossit sans limite. Ajouter LRU ou cap. `Fichier: llmforge/backend/services/llm_router.py:306`
- [ ] **M7 — Vault auto-key en prod** : Bloquer quand DEBUG=false. `Fichier: guardforge/backend/services/vault.py:43`
- [ ] **M8 — OracleForge symbol validation** : Pas de validation sur le path param {symbol}. `Fichier: oracleforge/backend/routes/prices.py:32`
- [ ] **M9 — PersonalizeRequest.prospect untyped** : `dict` → Pydantic model. `Fichier: outreachforge/backend/routes/outreach.py:19`
- [ ] **M10 — FAST2/FAST3 jamais classifies** : Aucun keyword ne route vers Gemini/Groq. Documenter ou ajouter des keywords. `Fichiers: llmforge + missionforge llm_router.py`

### LOW — Nice to have

- [ ] **L1 — Exceptions swallowed** : `except Exception: pass` dans VectorMemory.search. Ajouter logger.warning. `Fichier: missionforge/backend/services/memory.py:136`
- [ ] **L2 — Fallback chain implicite** : LLMForge utilise `list(Tier)` au lieu d'une liste explicite. `Fichier: llmforge/backend/services/llm_router.py:67`
- [ ] **L3 — Groq model hardcode** : `"llama-3.3-70b-versatile"` hardcode au lieu de `settings.groq_model`. `2 fichiers`
- [ ] **L4 — Refresh token non-revocable** : Pas de token blacklist. Ajouter table de revocation. `AuthForge`
- [ ] **L5 — CORS localhost en prod** : Valider que cors_origins != localhost quand DEBUG=false. `Tous`
- [ ] **L6 — Return type annotations manquantes** : ~10 fonctions helper sans `-> Type`. `Multiple fichiers`

---

## 2. FONCTIONNALITES MANQUANTES (pre-lancement)

### MissionForge
- [ ] Execution history persistee en DB (ExecutionLog table existe mais pas utilisee)
- [ ] Streaming SSE pour `/missions/{name}/logs/stream` (declare mais pas implemente)
- [ ] Mission YAML editor dans le dashboard
- [ ] Hot-reload file watcher automatique

### LLMForge
- [ ] Dashboard Next.js (le produit est "LiteLLM avec un dashboard" — pas de dashboard)
- [ ] Streaming response (token par token pour UX chat)
- [ ] Usage persistee en DB (perdue au restart)

### OracleForge
- [ ] Dashboard visualisation temps reel
- [ ] WebSocket/SSE live prices
- [ ] Historique prix en DB
- [ ] Yahoo Finance + Finnhub (sources declarees mais pas implementees)

### GuardForge
- [ ] Dashboard scan history + vault management
- [ ] Audit trail en DB (chaque scan logge pour compliance)
- [ ] Mode dry-run (scanner sans anonymiser)
- [ ] PII detection multi-langue NER (spaCy)

### AuthForge
- [ ] Dashboard users (gestion comptes, roles, sessions)
- [ ] OAuth Google flow complet
- [ ] 2FA TOTP
- [ ] Email verification flow

### OutreachForge
- [ ] Envoi SMTP reel
- [ ] Campagnes multi-etapes (sequencing)
- [ ] A/B testing emails
- [ ] Dashboard campagnes

---

## 3. STABILITE (post-lancement)

- [ ] PostgreSQL migration scripts (SQLite cassera a >100 users concurrents)
- [ ] Connection pooling httpx (eviter epuisement sockets)
- [ ] Graceful shutdown (missions en cours doivent finir)
- [ ] Health check deep (verifier DB + services externes, pas juste "ok")
- [ ] Retry logic avec backoff (OracleForge, LLMForge)
- [ ] Request ID / correlation ID (tracer requetes dans les logs)
- [ ] Structured logging JSON (pour Loki/ELK)
- [ ] Error tracking Sentry
- [ ] Docker healthcheck dans Dockerfile
- [ ] CI/CD pipeline (GitHub Actions : tests + build + deploy)

---

## 4. SECURITE (post-lancement)

- [ ] HTTPS enforcement (redirect HTTP → HTTPS)
- [ ] Helmet security headers middleware
- [ ] Dependency audit (`pip audit` pour CVEs)
- [ ] Content-Length limit middleware (DoS prevention)
- [ ] API key rotation mechanism
- [ ] Audit log pour toutes les actions admin
- [ ] IP whitelist optionnel pour endpoints sensibles
- [ ] CSRF protection sur les dashboards

---

## 5. INNOVATIONS (post-lancement)

### MissionForge
- [ ] **Mission Marketplace** : les users partagent/vendent leurs missions YAML, MAXIA prend 20% commission
- [ ] **Mission Chaining (DAG)** : une mission declenche une autre (workflow complexe)
- [ ] **Human-in-the-loop** : step `approval` qui pause et attend validation humaine
- [ ] **Agent Memory persistante** : l'agent apprend entre executions via ChromaDB
- [ ] **Vision/Multimodal** : step `image_analyze` qui envoie une image au LLM
- [ ] **Triggers** : declencher une mission sur event externe (webhook entrant, cron, email recu)

### LLMForge
- [ ] **Semantic Cache** : cacher par similarite embeddings (pas hash exact). "Quel temps?" et "Meteo?" = meme cache
- [ ] **Quality-based routing** : benchmark automatique par tier, router par qualite mesuree pas juste cout
- [ ] **A/B test models** : 10% trafic vers nouveau modele, comparer metriques
- [ ] **Token budget optimizer** : ajuster max_tokens automatiquement selon complexite prompt
- [ ] **Streaming multiplexing** : recevoir tokens de plusieurs providers en parallele, garder le plus rapide

### OracleForge
- [ ] **Price prediction ML** : modele leger qui predit prix 5min/1h en avance
- [ ] **Anomaly alerting** : webhook quand prix devie >X% (detection front-running)
- [ ] **Historical confidence** : tracker fiabilite source sur 30j, ponderer dynamiquement
- [ ] **DEX integration** : Uniswap/Jupiter comme sources on-chain
- [ ] **Arbitrage detection** : alerter quand spread >X% entre sources

### GuardForge
- [ ] **LLM output safety** : scanner reponses LLM pour contenu dangereux, hallucinations, PII genere
- [ ] **Prompt injection detection** : detecter tentatives injection dans prompts utilisateur
- [ ] **Compliance report PDF** : rapport RGPD/HIPAA exportable pour audits
- [ ] **Real-time PII streaming** : middleware FastAPI qui scanne TOUTES les reponses
- [ ] **NER avance** : spaCy/transformer pour noms, adresses, dates au-dela des regex
- [ ] **Data masking reversible** : tokeniser PII (UUID), restaurer apres traitement LLM

### AuthForge
- [ ] **Magic link login** : lien par email, zero password
- [ ] **Passkey/WebAuthn** : auth biometrique
- [ ] **Multi-tenant** : un AuthForge gere les users de N apps
- [ ] **Session analytics** : quand, d'ou, combien de temps
- [ ] **SSO SAML/OIDC** : pour enterprise (code existe dans V12)
- [ ] **Impersonation admin** : admin peut voir l'app comme un user specifique

### OutreachForge
- [ ] **LLM personalisation** : corps email genere par LLM a partir du profil prospect
- [ ] **Reply detection** : webhook qui detecte reponses et met a jour statut auto
- [ ] **LinkedIn enrichment** : enrichir profils via LinkedIn
- [ ] **Warm-up automatique** : volume progressif pour eviter spam flag
- [ ] **Conversation AI** : quand prospect repond, agent continue la conversation
- [ ] **Sentiment analysis** : analyser le ton des reponses pour adapter la suite

### Cross-produits — Forge Suite Intelligence
- [ ] **Auto-discovery** : les produits se detectent mutuellement quand co-installes
- [ ] **Forge Hub** : dashboard unifie pour les 6 produits
- [ ] **Shared auth** : AuthForge authentifie tous les autres produits
- [ ] **Event bus** : produits communiquent via events (mission → email → log GuardForge)
- [ ] **Usage-based billing** : facturer par token/appel/scan via LemonSqueezy metered
- [ ] **Plugin system** : les users creent des extensions pour chaque produit
- [ ] **CLI unifiee** : `forge mission start`, `forge llm chat`, `forge guard scan`

---

## 6. ROADMAP SPRINTS

### Sprint 1 (cette semaine) — Issues HIGH
Fixer H1-H11 (auth middleware, rate limiting, LLMRouter singleton, email validation)

### Sprint 2 — MissionForge ship
Execution history DB, SSE logs, mission editor dashboard, test E2E avec Groq

### Sprint 3 — LLMForge ship
Dashboard minimal, streaming, usage DB

### Sprint 4 — OracleForge + GuardForge ship
Yahoo/Finnhub, dashboard Oracle, audit trail Guard, NER

### Sprint 5 — AuthForge + OutreachForge ship
Dashboard users, OAuth Google, SMTP reel, campagnes

### Sprint 6+ — Innovations
Mission Marketplace, Semantic Cache, Anomaly Alerting, Forge Hub
