# Prochaine Session — TODO

> Derniere session : 13 avril 2026
> Etat : GuardForge backend P0 + dashboard P0 livres et testes en live (port 8004 + 3003)

---

## 0. GuardForge — i18n FR a finir (Priorite haute, ~30 min)

Session du 13 avril 2026 : pages /playground, /reports, scanner risk badges et tuiles home creees,
mais beaucoup de strings sont restees hardcodees en anglais alors qu'Alexis tourne en FR.
Audit complet fait par sous-agent Haiku — 20+ chaines a traduire.

### Fichiers a modifier
- `guardforge/dashboard/src/app/playground/page.tsx`
- `guardforge/dashboard/src/app/reports/page.tsx`
- `guardforge/dashboard/src/app/page.tsx` (sections risk distribution + tuiles playground/reports)
- `guardforge/dashboard/src/app/scanner/page.tsx` (boutons Tokenizing/Restoring)
- `guardforge/dashboard/src/messages/fr.json`
- `guardforge/dashboard/src/messages/en.json` (ajouter les memes cles cote EN si absentes)

### Cles manquantes (a wrapper en `t(...)` puis ajouter au JSON)

**playground :**
- `playground.backend_offline` → "Backend hors ligne" (line ~170)
- `playground.reset_btn` → "Reinitialiser" (line ~201)
- `playground.paste_placeholder` → "Collez le texte contenant des PII a tokeniser..." (line ~209)
- `playground.tokenizing` → "Tokenisation en cours..." (line ~225)
- `playground.safe_badge` → "SUR" (line ~271)
- `playground.copy_btn` / `playground.copied_btn` → "Copier" / "Copie" (line ~279)
- `playground.click_restore` → "Cliquez sur Restaurer pour reveler les valeurs originales" (line ~318)
- `playground.entities_detected` → "entites detectees" (line ~357)
- `playground.explainer_body` → "Envoyez uniquement les tokens a OpenAI / Anthropic — les vrais noms, IBAN et e-mails ne quittent jamais votre infrastructure. Apres la reponse du LLM, GuardForge restaure les vraies valeurs a l'aide du coffre-fort de session. Zero fuite de PII." (line ~397-399)
- `playground.step_1` / `step_2` / `step_3` → "Tokeniser les PII" / "Envoyer les tokens au LLM" / "Restaurer dans votre application" (line ~403-405)

**reports :**
- `reports.subtitle` → "Conformite & analyse des risques" (line ~192)
- `reports.empty_state_subtitle` → "Cliquez sur Actualiser pour charger les donnees, ou utilisez d'abord le Scanner / Playground." (line ~261)
- `reports.no_timeline_data` → "Aucune donnee chronologique" (line ~82, 407)

**page.tsx (home) :**
- `dashboard.policy_label` → "Politique : " (line ~382)
- `dashboard.action_label` → "Action : " (line ~389)
- `dashboard.playground_desc` → "Tokeniser et de-tokeniser les PII de maniere interactive" (line ~732)
- `dashboard.reports_desc` → "Conformite analytics & rapports d'audit" (line ~752)

**scanner/page.tsx :**
- `scanner.tokenizing` → "Tokenisation..." (line ~252)
- `scanner.restoring` → "Restauration..." (line ~331)

### Workflow recommande
1. Delegation Sonnet (1 agent) avec instructions precises : pour chaque file:line, wrapper le literal en `t("cle.nom")` puis ajouter la cle dans fr.json ET en.json
2. `npm run build` pour confirmer 0 erreur TypeScript
3. Hard refresh browser pour valider visuel

### Note importante Next.js 16
- Le dashboard a un fichier `guardforge/dashboard/AGENTS.md` qui dit "This is NOT the Next.js you know — read node_modules/next/dist/docs/ before writing any code"
- Donc consulter cette doc AVANT de toucher au code Next.js (Turbopack, App Router 16.x, breaking changes vs training data)

### Etat services au moment de la sauvegarde
- Backend GuardForge port 8004 : live, 11 scans seedes, dedup fix actif
- Dashboard GuardForge port 3003 : live, env vars OK (NEXT_PUBLIC_API_KEY + NEXT_PUBLIC_SECRET_KEY ajoutes dans .env.local)
- Bug fixe en live : SIRET 14 digits collisionnait avec credit_card → fix `_deduplicate_overlapping()` dans pii_detector.py:144

---

## 1. REVIEW VISUEL — Priorite haute

Alexis n'a pas encore valide le rendu de tous les dashboards. A faire :
- [ ] Ouvrir chaque dashboard (localhost:3000-3006) et verifier le design
- [ ] Verifier que le bouton dark/light fonctionne sur CHAQUE page
- [ ] Verifier que TOUS les liens sidebar menent a une vraie page (pas de 404)
- [ ] Corriger les problemes visuels signales par Alexis

## 2. ~~SUPPRESSION MOCK DATA — MissionForge page principale~~ ✅ FAIT

- [x] Donnees 100% API pour tous les KPI, charts, tables
- [x] `—` quand le backend est offline (pas de faux chiffres)
- [x] Charts avec message "Connect backend" si pas de donnees API
- [x] DONUT_DATA derive de obs.missions (plus hardcode)
- [x] Metrics derives de obs.llm.by_tier (plus de 94%, 340ms, etc.)
- [x] Badges fake "-3% vs yesterday" et "+8% indexed today" supprimes

## 3. ~~COHERENCE DESIGN — DashboardShell harmonise~~ ✅ FAIT

- [x] DashboardShell cree pour LLMForge, OracleForge, GuardForge, AuthForge
- [x] Meme sidebar 200px avec texte (via composant partage)
- [x] Meme header avec ThemeToggle, LIVE/OFFLINE badge, clock
- [x] Health check polling toutes les 30s sur chaque produit
- [x] 18 pages refactorees pour utiliser le shell

## 4. PAGES "BACKEND REQUIS"

Certaines pages affichent "Cette fonctionnalite necessite la configuration du backend" car les endpoints n'existent pas encore :
- [ ] AuthForge : /users (GET /api/auth/users), /roles (PUT /api/auth/users/:id/role), /settings (POST /api/auth/change-password, PUT /api/auth/me)
- [ ] OutreachForge : /campaigns (CRUD campaigns), /templates (CRUD templates)
- [ ] GuardForge : /vault (peut necesser config NEXT_PUBLIC_SECRET_KEY)

Decision a prendre : creer les endpoints backend ou retirer les pages.

## 5. BUNDLE DASHBOARD — Enrichir

Le hub Forge Suite (localhost:3006) est basique. A enrichir :
- [ ] Metriques agreges cross-produit (total LLM calls tous produits, total missions, etc.)
- [ ] Graphique timeline des health checks
- [ ] Liens directs vers les sous-pages cles de chaque produit
- [ ] Navigation entre produits depuis le hub

## 6. ~~COMPOSANT PARTAGE DashboardShell~~ ✅ FAIT

- [x] DashboardShell cree pour LLMForge (violet→blue, Zap)
- [x] DashboardShell cree pour OracleForge (emerald→cyan, Zap)
- [x] DashboardShell cree pour GuardForge (amber→orange, Shield)
- [x] DashboardShell cree pour AuthForge (blue→violet, Shield)
- [x] MissionForge DashboardShell upgrade avec health check
- [x] OutreachForge deja fait (reference)
- [x] Sidebar dupliquee eliminee de toutes les pages

## 7. BACKENDS

Aucun backend n'est lance dans cette session. Pour tester les dashboards avec des vraies donnees :
```bash
# Lancer chaque backend
cd missionforge/backend && python -m uvicorn main:app --port 8001
cd llmforge/backend && python -m uvicorn main:app --port 8002
cd oracleforge/backend && python -m uvicorn main:app --port 8003
cd guardforge/backend && python -m uvicorn main:app --port 8004
cd authforge/backend && python -m uvicorn main:app --port 8005
cd outreachforge/backend && python -m uvicorn main:app --port 8006
```

## 8. COUTS LLM

Alexis a insiste : les couts affiches doivent etre 100% reels (tokens x prix modele x marge abonnement). Verifier :
- [ ] Que le backend LLMForge calcule correctement les couts par modele
- [ ] Que MissionForge remonte les couts reels via /api/observability/summary
- [ ] Que les dashboards n'affichent jamais de faux montants $

## 9. PRODUCTION READINESS

Avant deploy :
- [ ] Variables d'environnement .env.local configurees pour chaque dashboard
- [ ] CORS configure sur chaque backend pour accepter le frontend
- [ ] Tests E2E sur les flux critiques
- [ ] Security review (API keys, tokens)
- [ ] Docker compose pour lancer les 7 dashboards + 6 backends

## 10. ~~PAGES STUB MissionForge~~ ✅ FAIT

- [x] /observability : vraie page avec KPIs (LLM Calls, Cost, Latency, Tiers), tier breakdown, memory/RAG summary
- [x] /rag : vraie page avec KPIs (Status, Chunks, Cached, Memory), cache breakdown, collections list
- [x] Toutes les pages affichent "—" quand backend offline
- [x] Zero "Coming soon" restant

---

## Ports Reference

| Service | Port |
|---|---|
| MissionForge backend | 8001 |
| LLMForge backend | 8002 |
| OracleForge backend | 8003 |
| GuardForge backend | 8004 |
| AuthForge backend | 8005 |
| OutreachForge backend | 8006 |
| MissionForge dashboard | 3000 |
| LLMForge dashboard | 3001 |
| OracleForge dashboard | 3002 |
| GuardForge dashboard | 3003 |
| AuthForge dashboard | 3004 |
| OutreachForge dashboard | 3005 |
| Forge Suite hub | 3006 |
