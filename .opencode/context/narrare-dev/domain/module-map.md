<!-- Context: narrare-dev/domain/module-map | Priority: high | Source: docs/reference/directory-structure.md (788 lines) | Updated: 2026-06-12 -->

# Module Map — Quick Reference

Where things live. Compact reference — not the full directory tree.

---

## Core Modules (`packages/core/narrare_core/`)

| Directory | Purpose | Key Files |
|-----------|---------|-----------|
| `llm/` | LLM Gateway, model routing, providers | `gateway.py`, `intents.py`, `model_routing.py`, `_providers/registry.py` |
| `prompts/` | Prompt building, cascade resolution | `composer.py`, `registry.py`, `variable_engine.py`, `_bundled/` |
| `agents/` | pydantic-ai Agent definitions | `base.py`, domain-specific agents |
| `context/` | Context assembly for prompts | `assembler.py`, `budget.py`, `model_limits.py` |
| `writing/` | Writing generation pipeline | `pipeline.py`, `session_manager.py`, `draft_processor.py` |
| `embeddings/` | Vector operations (pgvector) | `store.py`, `similarity.py` |
| `memory/` | Memory layer (mem0) | `service.py`, `client.py` |
| `cache/` | Redis abstraction | `client.py` |
| `tasks/` | TaskIQ background tasks | `worker.py` |
| `shared/` | Pure utilities | `result.py`, `errors.py`, `crypto.py`, `frontmatter.py`, `pagination.py` |
| `schemas/` | Shared Pydantic schemas | `auth.py`, `novels.py`, `chapters.py`, `kb.py`, `writing.py`, `analysis.py` |

---

## API Modules (`apps/api/narrare/`)

| Module | Purpose | Key Service Files |
|--------|---------|-------------------|
| `_app/` | App wiring, DB, middleware | `main.py`, `database.py`, `dependencies.py`, `lifespan.py` |
| `auth/` | Authentication | `service.py`, `security.py`, `router.py` |
| `novels/` | Novel CRUD | `service.py`, `repository.py`, `router.py` |
| `chapters/` | Chapter CRUD + summaries | `service.py`, `summarize_service.py`, `router.py` |
| `volumes/` | Volume management | `service.py`, `router.py` |
| `writing/` | AI writing (4 modes) | `service.py`, `scene_service.py`, `suggest_service.py`, `router.py`, `router_sessions.py` |
| `kb/` | Knowledge Base | `management_service.py`, `editor_service.py`, `analyzer_service.py`, `worldbuilding_service.py` |
| `analysis/` | All analysis features | `sentiment_service.py`, `beta_reader_service.py`, `voice/` sub-package |
| `settings/` | User/project AI config | `user_service.py`, `project_service.py`, `model_routing_resolver.py` |
| `setup/` | Setup wizard + demo data | `service.py`, `_validation.py`, `demo_loader.py` |
| `prompts/` | User prompt templates | `user_template_service.py`, `repository.py` |
| `generation/` | Name gen, plot gen | `plot_service.py`, `name_service.py` |
| `graph/` | Knowledge graph | `service.py`, `facts_service.py` |
| `consistency/` | Consistency checking | `checker_service.py`, `rules_service.py` |
| `planning/` | Story structure | `service.py`, `router.py` |
| `storyboard/` | Storyboard view | `service.py`, `router.py` |
| `memory/` | Memory API (thin) | `router.py` (delegates to `core/memory/`) |
| `providers/` | Provider model lists | `service.py` (caches in Redis) |

---

## Web Modules (`packages/web/`)

| Directory | Purpose |
|-----------|---------|
| `app/` | Next.js App Router pages: `(auth)/` (public), `(app)/` (authenticated) |
| `components/editor/` | Editor: EditorLayout, EditorSurface (TipTap v3), ChapterSidebar, ContextPanel |
| `components/studio/` | AI writing: GenerationPanel, GenerationConfig, SessionPanel |
| `components/dashboard/` | DashboardView, NovelCard |
| `components/setup/` | WizardShell, WizardStep1-5 |
| `components/settings/` | ProviderList, ProviderForm, ModelRoutingPanel |
| `components/ui/` | shadcn/ui primitives: Button, Input, Select |
| `lib/api/` | `client.ts` (fetchApi + token refresh), `streaming.ts` (connectSSE) |
| `lib/stores/` | Zustand: editorStore, authStore, wizardStore |
| `lib/i18n/` | `request.ts` (namespace registry), `routing.ts` |
| `styles/` | `globals.css` (CSS variable design tokens, Tailwind v4) |

---

## Shared (`packages/i18n/`)

| Path | Purpose |
|------|---------|
| `messages/en/` | English translations (reference locale) |
| `messages/de/` | German translations (mirrors en/) |
| `messages/fr/` | French translations (mirrors en/) |

---

## Cross-Reference: "Working on X? Look in Y"

| Task | Core | Backend | Frontend |
|------|------|---------|----------|
| New LLM feature | `core/llm/`, `core/prompts/` | `apps/api/{domain}/service.py` | `components/studio/` |
| New API endpoint | `core/{domain}/` | `apps/api/{domain}/` (all files) | `lib/api/client.ts` |
| New UI component | — | — | `components/{area}/` + `lib/stores/` |
| New analysis type | `core/analysis/` | `apps/api/analysis/` | `components/studio/analysis/` |
| KB changes | `core/context/`, `core/embeddings/` | `apps/api/kb/` | `components/editor/` |
| Auth changes | — | `apps/api/auth/` | `lib/api/client.ts`, `app/proxy.ts` |
| Settings/config | — | `apps/api/settings/` | `components/settings/` |
| i18n changes | — | — | `lib/i18n/request.ts`, `packages/i18n/messages/` |
| New agent | `core/agents/`, `core/prompts/` | `apps/api/{domain}/service.py` | SSE via `lib/api/streaming.ts` |
| Background task | `core/tasks/` | `apps/api/{domain}/tasks.py` | — |

---

**Reference**: `docs/reference/directory-structure.md` (788 lines)
**Related**: narrare-dev/domain/architecture-concepts · narrare-dev/lookup/directory-structure · narrare-dev/lookup/tech-stack
