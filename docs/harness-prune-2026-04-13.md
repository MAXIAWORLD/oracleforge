# Harness pruning — 2026-04-13

Élagage des skills/agents/rules/commands non utilisés pour OracleForge, dans le but de réduire la consommation de tokens par tour.

**Rien n'a été supprimé.** Tout est dans `~/.claude/*.archive/` et restaurable via `mv`.

## Avant / Après

| Catégorie | Avant | Après | Archivés |
|---|---|---|---|
| Skills (`~/.claude/skills/`) | 122 | 44 | 78 |
| Agents (`~/.claude/agents/`) | 36 | 12 | 24 |
| Commands (`~/.claude/commands/`) | 63 | 27 | 36 |
| Rules common (`~/.claude/rules/common/`) | 10 | 4 | 6 |
| Rules python (`~/.claude/rules/python/`) | 5 | 1 | 4 |
| Project CLAUDE.md | 163 lignes | 50 lignes | (verbose part → `docs/maxia-lab-overview-archive.md`) |

**Économie estimée par tour de conversation** : ~18-25k tokens.
**Économie sur une session longue (100 tours)** : ~2 millions de tokens.

## Critères de keep

**Gardés** :
- Tout ce qui est utilisé pour Python/FastAPI (backend OracleForge)
- Tout ce qui est utilisé pour TypeScript/Next.js (dashboard OracleForge)
- Quality / TDD / verification / review tools
- Marketing skills nécessaires en Phase 3-4 du plan OracleForge
- SEO basics pour la doc/landing en Phase 3
- Tools d'économie de tokens (`cost-aware-delegation`, `strategic-compact`, `iterative-retrieval`, `dispatching-parallel-agents`, `context-budget`)
- Planning / workflow tools (`writing-plans`, `executing-plans`, `the-fool`, `brainstorming`)

**Archivés** :
- Tout langage non-utilisé (C++, Java, Kotlin, Rust, Go, Perl, Laravel/PHP, Django, Flutter, Android)
- Marketing skills prématurés (paid-ads, cold-email, twitter-algo, brand-guidelines, etc.)
- SEO skills overkill pour un produit API (audit, hreflang, sitemap, programmatic, local, images)
- Skills méta non quotidiens (`continuous-learning`, `eval-harness`, `mcp-builder`, `plankton-code-quality`, `graphify`, `developer-growth-analysis`)
- Slash commands de langues non-utilisées (cpp-, go-, kotlin-, rust-)
- Multi-model orchestration (premature)
- Rules redondantes avec les skills (python/hooks, python/patterns, python/security, python/testing — chaque fichier disait "see skill X")
- Rules méta (common/agents, common/hooks, common/performance, common/skills-workflow)

## Liste complète des items archivés

### Skills (78) — `~/.claude/skills.archive/`

```
ab-test-setup, ad-creative, ai-regression-testing, analytics-tracking,
android-clean-architecture, brand-guidelines, churn-prevention, cold-email,
competitive-ads-extractor, competitor-alternatives, compose-multiplatform-patterns,
configure-ecc, content-research-writer, continuous-learning, continuous-learning-v2,
cpp-coding-standards, cpp-testing, developer-growth-analysis, django-patterns,
django-tdd, django-verification, domain-name-brainstormer, email-sequence,
eval-harness, form-cro, free-tool-strategy, frontend-slides, golang-patterns,
golang-testing, graphify, java-coding-standards, kotlin-coroutines-flows,
kotlin-exposed-patterns, kotlin-ktor-patterns, kotlin-patterns, kotlin-testing,
laravel-patterns, laravel-tdd, laravel-verification, lead-magnets,
lead-research-assistant, mcp-builder, mcp-server-patterns, onboarding-cro,
page-cro, paid-ads, paywall-upgrade-cro, perl-patterns, perl-testing,
plankton-code-quality, popup-cro, postgres-pro, product-marketing-context,
programmatic-seo, project-guidelines-example, referral-program, revops,
rust-patterns, rust-testing, sales-enablement, schema-markup, seo-audit,
seo-competitor-pages, seo-hreflang, seo-images, seo-local, seo-plan,
seo-programmatic, seo-sitemap, signup-flow-cro, site-architecture,
skill-stocktake, springboot-patterns, springboot-tdd, springboot-verification,
tdd-workflow, twitter-algorithm-optimizer, writing-skills
```

### Agents (24) — `~/.claude/agents.archive/`

```
chief-of-staff, cpp-build-resolver, cpp-reviewer, database-reviewer,
flutter-reviewer, go-build-resolver, go-reviewer, harness-optimizer,
java-build-resolver, java-reviewer, kotlin-build-resolver, kotlin-reviewer,
loop-operator, pytorch-build-resolver, rust-build-resolver, rust-reviewer,
seo-content, seo-geo, seo-local, seo-performance, seo-schema, seo-sitemap,
seo-technical, seo-visual
```

### Slash commands (36) — `~/.claude/commands.archive/`

```
claw, cpp-build, cpp-review, cpp-test, devfleet, eval, evolve, execute-plan,
go-build, go-review, go-test, gradle-build, instinct-export, instinct-import,
kotlin-build, kotlin-review, kotlin-test, loop-start, loop-status,
multi-backend, multi-execute, multi-frontend, multi-plan, multi-workflow,
orchestrate, pm2, projects, promote, prune, rules-distill, rust-build,
rust-review, rust-test, setup-pm, update-codemaps, write-plan
```

### Rules (10) — `~/.claude/rules.archive/`

**common/** :
- `agents.md` (redondant avec la liste agents harness)
- `development-workflow.md` (overlap git-workflow)
- `hooks.md` (méta sur les hooks)
- `patterns.md` (trop générique)
- `performance.md` (méta sur model selection)
- `skills-workflow.md` (méta sur workflow)

**python/** :
- `hooks.md` (renvoie au skill)
- `patterns.md` (renvoie à python-patterns)
- `security.md` (renvoie à python-review)
- `testing.md` (renvoie à python-testing)

## Liste complète des items gardés

### Skills gardés (44)

**Token efficiency** : `cost-aware-delegation`, `strategic-compact`, `iterative-retrieval`, `dispatching-parallel-agents`, `using-superpowers`

**Python/FastAPI** : `python-patterns`, `python-testing`, `fastapi-expert`, `test-driven-development`, `systematic-debugging`, `backend-patterns`

**TypeScript/Next** : `coding-standards`, `frontend-patterns`, `frontend-design`, `e2e-testing`, `webapp-testing`

**Quality** : `verification-before-completion`, `verification-loop`, `requesting-code-review`, `receiving-code-review`

**Planning** : `writing-plans`, `executing-plans`, `subagent-driven-development`, `using-git-worktrees`, `finishing-a-development-branch`, `brainstorming`, `the-fool`

**API design** : `api-design`, `api-designer`, `database-optimizer`

**Marketing (Phase 3-4)** : `launch-strategy`, `pricing-strategy`, `marketing-ideas`, `marketing-psychology`, `social-content`, `copywriting`, `copy-editing`, `content-strategy`

**SEO basics** : `seo-content`, `seo-page`, `seo-schema`, `seo-technical`, `ai-seo`, `seo-geo`

### Agents gardés (12)

`architect`, `build-error-resolver`, `code-reviewer`, `doc-updater`, `docs-lookup`, `e2e-runner`, `planner`, `python-reviewer`, `refactor-cleaner`, `security-reviewer`, `tdd-guide`, `typescript-reviewer`

### Slash commands gardés (27)

`aside`, `brainstorm`, `build-fix`, `checkpoint`, `code-review`, `context-budget`, `docs`, `e2e`, `harness-audit`, `instinct-status`, `learn`, `learn-eval`, `model-route`, `plan`, `prompt-optimize`, `python-review`, `quality-gate`, `refactor-clean`, `resume-session`, `save-session`, `sessions`, `skill-create`, `skill-health`, `tdd`, `test-coverage`, `update-docs`, `verify`

### Rules gardées (5)

- `common/coding-style.md`
- `common/git-workflow.md`
- `common/security.md`
- `common/testing.md`
- `python/coding-style.md`

## Comment restaurer

Pour ré-activer un item archivé, un simple `mv` suffit :

```bash
# Exemple : restaurer le skill `kotlin-patterns`
mv ~/.claude/skills.archive/kotlin-patterns ~/.claude/skills/

# Exemple : restaurer l'agent `rust-reviewer`
mv ~/.claude/agents.archive/rust-reviewer.md ~/.claude/agents/

# Exemple : restaurer plusieurs commandes d'un coup
cd ~/.claude/commands.archive
mv rust-build.md rust-review.md rust-test.md ../commands/

# Restaurer toutes les rules python
mv ~/.claude/rules.archive/python/* ~/.claude/rules/python/
```

Le dossier `*.archive/` reste tel quel jusqu'à ce que tu décides de le supprimer définitivement (ne le supprime pas tant que tu n'es pas sûr, ces fichiers ne consomment pas de tokens — seulement de l'espace disque négligeable).

## Items NON touchés (à examiner toi-même plus tard si besoin)

1. **Plugins** (`~/.claude/plugins/`) — contient `rust-analyzer-lsp` activé via `enabledPlugins` dans `settings.json`. Tu n'utilises pas Rust, tu peux le désactiver dans `settings.json` (passer à `false` ou retirer la ligne) pour économiser le LSP rust-analyzer.

2. **Marketplaces plugins** (`~/.claude/plugins/marketplaces/`) — contient ~70 plugins externes (discord, telegram, imessage, fakechat, agent-sdk-dev, clangd-lsp, postgres-mcp, etc.). Aucun n'est activé sauf `rust-analyzer-lsp`. Les fichiers prennent du disque mais 0 tokens car non chargés.

3. **MCP servers (Gmail, Calendar)** — pas dans `settings.json`. Probablement injectés par le harness Claude Code lui-même via une autre config (peut-être `~/.claude.json` ou `~/.claude/managed_mcp/`). Si tu veux les retirer complètement, cherche dans :
   ```bash
   grep -rln 'claude_ai_Gmail\|claude_ai_Google_Calendar' ~/.claude*
   ```

4. **`~/.claude/.opencode/`** — duplicate des commands pour le projet OpenCode (autre tool). N'affecte pas Claude Code, ignorer ou supprimer si tu n'utilises pas OpenCode.

5. **Hook `Stop` dans `settings.json`** — affiche "FIN: pense a /save-session et /learn avant de fermer". Inoffensif, économie négligeable.

6. **TaskCreate reminder** — système qui injecte un reminder "considère TaskCreate" toutes les 5-10 tool calls. Origine inconnue (probablement built-in du harness, pas dans `settings.json`). Si trouvable, désactiver.

## Vérification post-pruning

Pour vérifier l'économie réelle au prochain démarrage de session :
```
/context-budget
```
Et compare avec le baseline avant l'élagage (~50-70k tokens contexte fixe).
