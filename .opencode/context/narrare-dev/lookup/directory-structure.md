<!-- Context: narrare-dev/lookup/directory-structure | Priority: P1 | Source: docs/reference/directory-structure.md | Updated: 2026-08-10 -->

# Directory Structure

Canonical file layout for Narrare. New files go where this doc says. If a file doesn't fit, ask Architecture Agent first.

## Top-Level Layout

```
narrare/
├── apps/api/          ← FastAPI backend
├── packages/core/     ← Domain logic (no HTTP, no users, no DB)
├── packages/i18n/     ← Translations (source of truth)
├── packages/web/      ← Next.js 16 frontend
├── docs/              ← Documentation (_shared, architecture, development, features, mvp, reference)
├── scripts/           ← check_architecture.py, export_openapi.py
├── tests/             ← unit/, integration/, e2e/
└── justfile           ← Task runner
```

## packages/core/ — 17 Submodules

| Module | Key Files |
|--------|-----------|
| `llm/` | `gateway.py` (THE gateway), `intents.py`, `model_routing.py`, `result.py`, `retry.py`, `metrics.py`, `embeddings.py`, `_providers/` |
| `prompts/` | `composer.py`, `registry.py` (cascade), `context.py`, `meta.py`, `variable_engine.py`, `cache.py`, `service.py`, `_bundled/` |
| `context/` | `assembler.py` (5-tier), `budget.py`, `model_limits.py` |
| `writing/` | `pipeline.py` (4-mode), `context_assembler.py`, `draft_processor.py`, `session_manager.py`, `pipeline_scene.py`, `pipeline_interview.py` |
| `embeddings/` | `store.py` (pgvector), `similarity.py` |
| `memory/` | `service.py`, `client.py` (mem0) |
| `cache/` | `in_memory.py` (TTL-capable InMemorySessionCache; Redis removed by ADR-080) |
| `notifications/` | `email.py` (SMTP) |
| `research/` | `contracts.py`, `search_client.py` |
| `init/` | `service.py`, `template_resolver.py` |
| `shared/` | `frontmatter.py`, `file_utils.py`, `pagination.py`, `crypto.py`, `result.py`, `errors.py` |
| `schemas/` | `auth.py`, `novels.py`, `chapters.py`, `kb.py`, `writing.py`, `analysis.py`, `cost.py`, `context.py`, `learning.py` |

## apps/api/ — 20 Domain Modules

`_app/` (main, database, dependencies, middleware, lifespan), `auth/` (router + router_me, security, cookie_helpers), `novels/`, `chapters/` (summarize_service), `volumes/`, `writing/` (ws_handler, scene_service, stats_service), `kb/` (6 services: management, editor, analyzer, suggest, worldbuilding, extraction), `analysis/` (8 service files + voice/ sub-package), `planning/`, `ai_assist/`, `chat/`, `generation/` (plot_service, name_service), `graph/` (facts_service), `consistency/` (checker + rules), `timeline/`, `learning/`, `context/`, `embeddings/` (tasks.py), `prompts/`, `settings/` (4 repos, 5 services, resolver), `analytics/`, `cost/`, `export/`, `import_service/`, `research/`, `sync/`, `setup/` (demo_data/), `storyboard/`, `memory/`, `metrics/`

## packages/web/ — Key Structure

```
app/ → (auth)/login,register | (app)/dashboard,settings,novel/[id]/editor
components/ → editor/, dashboard/, setup/, settings/, ui/, studio/editor/, shared/
lib/ → api/(client,streaming,generation), stores/(editor,auth,wizard), i18n/, utils.ts
styles/ → globals.css (tokens + Tailwind v4 + editor prose)
types/ → index.ts
```

## packages/i18n/

```
messages/{en,de,fr}/ → common.json, auth.json, wizard.json, dashboard.json, editor.json, errors.json, settings.json
```

## tests/

```
tests/unit/core/  → llm/, prompts/, ...
tests/unit/api/   → setup/, writing/, ...
tests/integration/ → writing/, kb/, ...
tests/e2e/        → conftest.py, test_helpers.py, mocks/
```

## File Size Limits

| Pattern | Hard Limit |
|---------|-----------|
| `router*.py` | 150 lines |
| `service.py`, `*_service.py` | 300 lines |
| `repository.py` | 250 lines |
| `contracts.py` | 200 lines |
| `models.py`, `schemas.py` | 200 lines |
| `gateway.py` | 300 lines |
| Page component (`page.tsx`) | 100 lines |
| Feature component | 200 lines |
| Store, Hook | 150 lines |

When a file exceeds its limit → **split into a new module**, never compress.

**Reference**: `docs/reference/directory-structure.md` (788 lines)
**Related**: narrare-dev/examples/python-patterns · narrare-dev/examples/typescript-patterns · narrare-dev/guides/testing
