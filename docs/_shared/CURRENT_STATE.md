# Narrare — Current State

> **This document is the live status of the project.**
> Every agent reads this at the start of every session.
> Updated at the end of every session by the responsible agent.
>
> Location: `docs/_shared/CURRENT_STATE.md`

---

## Last Updated

Date: 2026-05-18
Updated by: NarrareDevCoordinator
Session summary: New Chapter Generation (WRITE-002) implemented — core writing pipeline, 4 generation modes, context assembly, bundled prompts, API with SSE+WebSocket, frontend generation UI, 98 tasks complete.

---

## Project Phase

```
Phase 0: Repository Foundation     ✅ COMPLETE
Phase 1: Core Infrastructure       ✅ COMPLETE
Phase 2: API Foundation            ✅ COMPLETE
Phase 3: Setup Wizard Backend      ✅ COMPLETE
Phase 4: Frontend Foundation       ✅ COMPLETE
Phase 5: Integration & Polish      ⏳ IN PROGRESS
```

---

## What Exists Right Now

### Documentation (complete)

**Shared Foundation (`docs/_shared/`):**
- `CONSTRAINTS.md` — 13 rules, CI-enforced
- `TECH_STACK.md` — canonical technology decisions
- `GLOSSARY.md` — shared vocabulary
- `CURRENT_STATE.md` — this file

**Development (`docs/development/`):**
- `coding-standards.md` — Python 3.14 + TypeScript standards
- `testing-standards.md` — test architecture, coverage targets, fixtures
- `ui-principles.md` — UX principles, component structure, state management
- `deployment-guide.md` — CI/CD, dev environment, release process
- `orchestrator.md` — orchestrator agent definition

**Reference (`docs/reference/`):**
- `project-vision.md` — why, what, for whom
- `directory-structure.md` — canonical file locations

**Architecture (`docs/architecture/`):**
- `decisions/INDEX.md` + ADR-001 through ADR-007
- `questions/INDEX.md` + Q-001 through Q-005

**Features (`docs/features/`):**
- `INDEX.md` — 40+ features catalogued
- `_TEMPLATE.md`
- Individual feature specs (SETUP-001, SETUP-002, WRITE-001) referenced in INDEX but not yet created as separate files

**MVP (`docs/mvp/`):**
- `mvp-plan.md` — 5-phase plan for first running version

### Demo Content (complete)

**German demo ("Im stillen Wald") — `scripts/demo_data/german/im-stillen-wald/`:**
- Chapter 1: "Das Flüstern im Wald" (`ch-de-001-fluestern.md`) ✅
- Chapter 2: "Grenze der Welten" (`ch-de-002-grenze-welten.md`) ✅
- KB: Der Waldgeist, Das Försterhaus, Der Wald, Das Dorf ✅
- KB: Charaktere — Anna Müller, Johann Bauer ✅

**Fantasy demo ("Echoes of the Thornwall") — `scripts/demo_data/english/echoes-of-the-thornwall/`:**
- 4 chapters (`ch-en-001` through `ch-en-004`) ✅
- 15 KB entries: 5 characters, 5 locations, 2 factions, 3 systems, 1 object ✅

**SciFi demo ("Dead Signal") — `scripts/demo_data/english/dead-signal/`:**
- 3 chapters (`ch-en-ds-001` through `ch-en-ds-003`) ✅
- 7 KB entries: 3 characters, 2 locations, 1 object, 2 systems ✅

### Code

#### `packages/core/narrare_core/` — Shared Domain Logic (Phase 1)

**LLM Layer (`llm/`):**
- `gateway.py` — Single LLM Gateway (ADR-001), ~290 lines
- `_providers/` — OpenAI, Anthropic, Ollama, ZAI, Others, Registry (6 providers); all accept explicit `api_key`/`base_url`
- `observability.py` — Langfuse integration (LLM tracing, cost tracking)
- `result.py`, `retry.py`, `metrics.py`, `embeddings.py`
- `intents.py` — `LLMIntent` enum (incl. `GENERATE`, `NAME_GENERATE`, `TITLE_GENERATE`), `IntentCategory` enum (incl. `GENERATION`), `INTENT_CATEGORY_MAP`, `ResolvedModelConfig`
- `model_routing.py` — `ModelRoutingResolver` protocol and `ResolvedModel` result type
- `override_schemas.py` — Pydantic schemas for category/intent/token limit overrides

**Prompt System (`prompts/`):**
- `composer.py` — Prompt composition with preference auto-injection and culture injection (`{{culture_guidelines}}`)
- `registry.py` — Prompt registry with `resolve_culture()` method (EN fallback)
- `management.py` — `PromptManagementService` — list, get, save, reset, cascade, updates, diff
- `variable_metadata.py` — Variable registry with descriptions for UI sidebar
- `variable_engine.py` — Variable interpolation
- `context.py` — `PromptContext` with `user_preferences`, `avoidance_patterns`, `style_constraints` fields
- `meta.py`
- `_bundled/generation/` — 3 name generation prompts (en/de/fr) + 9 culture definitions (fantasy/modern/scifi × 3 langs)

**Memory Layer (`memory/`):**
- `protocols.py` — `MemoryClientProtocol`, `FeedbackServiceProtocol`, `PreferenceServiceProtocol`
- `models.py` — `FeedbackEvent`, `Preference`, `FeedbackAction` enum
- `mem0_client.py` — `Mem0Client` factory + `NullMemoryClient` graceful degradation (RULE-01 exception)
- `feedback_service.py` — `FeedbackService` — records feedback to PostgreSQL + mem0
- `preference_service.py` — `PreferenceService` — extracts preferences from mem0 for prompt injection

**Shared Utilities (`shared/`):**
- `result.py` — Result type pattern (Ok/Err)
- `crypto.py` — Fernet encryption for API keys (reads `NARRARE_ENCRYPTION_KEY`)
- `pagination.py`, `frontmatter.py`, `file_utils.py`, `errors.py`

**Stub Modules (interfaces only):**
- `context/`, `cache/`, `schemas/`, `embeddings/`

**Writing Layer (`writing/`):**
- `models.py` — GenerationMode, GenerationStatus, WritingContext, GenerationRequest, SessionState, SceneState
- `context_models.py` — KBEntity, RecentChapter dataclasses
- `contracts.py` — WritingPipelineProtocol, ContextAssemblerProtocol, DraftProcessorProtocol, SessionManagerProtocol
- `context_assembler.py` — WritingContextAssembler with 5-tier ranking + token budgets
- `budget.py` — TokenBudgetManager for tier allocation
- `draft_processor.py` — DraftProcessor with artifact removal + markdown normalization
- `pipeline.py` — WritingPipeline with 4-mode dispatch (full_draft, scene_by_scene, interview_assisted, interactive_session)
- `pipeline_scene.py` — Scene-by-scene mode logic
- `pipeline_interview.py` — Interview-assisted mode logic
- `session_manager.py` — SessionManager with cache-backed persistence (SessionCacheProtocol)
- `prompts/_bundled/writing/` — 12 system prompts (4 modes × 3 languages) + 4 tone variants

**Event System (`events/`):**
- Event types, bus protocol (Protocol-based), NullEventBus for testing

#### `apps/api/narrare/` — FastAPI Backend (Phase 2 & 3)

**App Infrastructure (`_app/`):**
- `main.py`, `config.py`, `database.py`, `dependencies.py`, `lifespan.py`, `middleware.py`
- `lifespan.py` runs `alembic upgrade head` on startup (auto-migration), logs schema version, fails fast if migrations break
- `telemetry.py` — OpenTelemetry setup (traces, metrics, FastAPI instrumentation)
- `events.py` — Redis Pub/Sub event bus implementation
- `event_listener.py` — Event → TaskIQ task routing

**Domain Modules (all contract-first per ADR-003):**
- `auth/` — JWT auth: models, service, router, router_me, repository, contracts, schemas, security, cookie_helpers
  - argon2id password hashing (bcrypt backward compatibility for existing hashes)
  - httpOnly refresh token cookie (`narrare_refresh`) — set on login/register, cleared on logout
- `novels/` — CRUD: models → repository → service → router, contracts, schemas
- `chapters/` — CRUD: models → repository → service → router, contracts, schemas
  - Content versioning: ChapterVersion model, version repository/service/router endpoints
- `volumes/` — Full CRUD + stats + reorder: models → repository → service → router, contracts, schemas; enriched model (subtitle, description, word_count_target, is_default); default volume auto-creation; stats aggregation; deletion protection
- `settings/` — Full AI settings: contracts, provider management, model routing, token limits
  - `contracts.py`, `schemas.py`, `models.py`, `repository.py`, `router.py`
  - `user_providers_repository.py`, `user_ai_settings_repository.py`, `project_ai_settings_repository.py`
  - `user_providers_service.py`, `user_ai_settings_service.py`, `project_ai_settings_service.py`
  - `model_routing_resolver.py`
  - Migration: `0004_ai_settings.py`
- `setup/` — Setup wizard: router, service, contracts, schemas, provider_service, provider_schemas, demo_loader
  - `_validation.py` — Step validation pure functions (extracted from service.py, RULE-04 split)
  - `service.py` now writes to both `user_providers` + `user_ai_settings` AND legacy `project_settings`
  - Z.AI dual endpoint selector (General vs Coding API) in Step 4
  - After setup, AI Settings pages work immediately — no more "No key configured"
  - Demo loader reads `metadata.json` from demo_data dirs (author, logline, pov, tags) — no more hardcoded data
  - `demo_data/*/metadata.json` — demo project metadata for each starter template
- `metrics/` — Health/metrics router
- `memory/` — Memory layer: contracts, schemas, models (feedback_events), repository, service, router
  - POST /memory/feedback — Record AI suggestion feedback
  - GET /memory/preferences — Get preference profile
  - DELETE /memory/preferences — Reset preferences
- `prompts/` — Prompt management: contracts, schemas, service, router
  - GET /prompts — List all prompts with source indicators
  - GET /prompts/{id} — Get prompt content + metadata
  - PUT /prompts/{id} — Save/update prompt override
  - DELETE /prompts/{id} — Reset to default
  - GET /prompts/{id}/updates — Check for bundled updates
  - GET /prompts/{id}/diff — Side-by-side diff comparison
  - GET /prompts/variables — List available variables with descriptions
- `generation/` — Generation features: contracts, schemas, name_service, router
  - POST /generation/names — Generate names with culture/type/count options

**Writing Module (`writing/`):**
- `models.py` — GenerationRequest SQLAlchemy model
- `schemas.py` — 11 Pydantic request/response schemas
- `contracts.py` — WritingServiceProtocol, GenerationRepositoryProtocol
- `repository.py` — GenerationRepository (CRUD, status transitions, concurrent prevention)
- `service.py` — WritingService (orchestration of pipeline + repo + feedback)
- `scene_service.py` — Scene-by-scene methods
- `stats_service.py` — Generation analytics
- `ws_handler.py` — WebSocket session handler
- `_ws_cache.py` — WebSocket connection cache for active sessions
- `router.py` — REST + SSE endpoints (generate, stream, status, cancel)
- `router_sessions.py` — WebSocket route (`WS /api/v1/writing/sessions/{chapter_id}`)
- `router_stats.py` — Stats endpoints
- Migration 0008 — generation_requests table + FK to chapter_versions

**Database:**
- Alembic migration `0001_initial.py` — initial schema
- Alembic migration `0004_ai_settings.py` — `user_providers`, `user_ai_settings`, project AI override columns
- Alembic migration `0005_project_settings.py` — adds missing `token_limit_profile` column to `project_settings` (forgotten in 0004)
- Alembic migration `0006_feedback_events.py` — creates `feedback_events` table for memory layer
- `env.py` imports all model modules (auth, chapters, novels, settings, volumes, memory) — autogenerate works correctly
- Auto-migration on startup via `lifespan.py` — no manual `alembic upgrade head` needed

#### `packages/i18n/` — Translations (Source of Truth)

- Namespace-based file structure: `messages/{locale}/{namespace}.json` (7 namespaces × 3 locales)
- Locales: en (reference), de, fr
- Frontend loads via `next-intl` from `packages/web/lib/i18n/request.ts`
- `narrare_i18n/` stub: will become Python loader for CLI/MCP/A2A
- Validation: key completeness + placeholder consistency in pre-commit and CI

#### `packages/web/` — Next.js 16 Frontend (Phase 4)

**App Structure (App Router):**
- `app/(auth)/` — Login, Register pages with form validation (react-hook-form + zod)
- Login/Register redirect: `has_providers ? /dashboard : /wizard` (checks `user_providers` table)
- `auth/me` endpoint (in `router_me.py`) returns `has_providers: bool`
- `app/(app)/` — Authenticated pages with shared layout (auth shell + user info)
  - `dashboard/` — Novel list with create/navigate
  - `wizard/` — Setup wizard (5-step, inherits app layout with header/user info)
  - `novel/[id]/editor/` — Full TipTap v3 editor with autosave, chapter sidebar (DnD), context panel
- Route-level `loading.tsx` (skeleton boundaries) and `error.tsx` (error boundaries) at all levels
- `global-error.tsx` as last resort

**Components:**
- `components/editor/` — EditorLayout, EditorSurface (TipTap), EditorToolbar, ChapterSidebar (DnD Kit), ContextPanel, MetadataSidebar, CommandPalette (Cmd+K)
  - `MetadataSidebar.tsx` — Right sidebar with live statistics, session delta, chapter metadata, novel progress (replaces bottom status bar)
  - `extensions/` — 4 custom TipTap extensions: NarrareDocument, SceneBreak, DialogueMark, Autosave
  - `commands.ts` — Command registry for palette (format + editor actions, extensible for AI features)
- `components/editor/EditorLayout.tsx` — Focus mode: ESC handler + floating Minimize2 button (semi-transparent, focus-mode only)
- `components/dashboard/` — DashboardView with NovelCard grid + delete functionality (Trash2 icon, confirm dialog via `novelsApi.delete()`)
- `components/setup/` — 5-step Wizard (WizardShell + WizardStep1-5); steps 2↔3 swapped (starter selection first, then novel details); demo prefill from metadata.json
- `components/settings/` — AI provider management, model routing, token limit profiles, project AI settings
  - `PromptSettings.tsx` — AI Prompts tab with category grouping, source indicators, update badges
  - `PromptEditor.tsx` — Prompt editor with edit mode, variables sidebar
  - `PromptDiff.tsx` — Side-by-side diff comparison
- `components/generation/` — Generation features
  - `NameGenerator.tsx` — Name generator form (type, culture, count, gender selectors)
  - `NameResults.tsx` — Results display with pronunciation, meaning, duplicate badges
- `components/studio/editor/` — Writing generation UI
  - `GenerationPanel.tsx` — Generation trigger + streaming display
  - `GenerationConfig.tsx` — Mode selection + options (4 modes, tone variants)
  - `GenerationDraft.tsx` — Draft zone + controls (accept, reject, save)
  - `SessionPanel.tsx` — Interactive session chat UI
  - `ChatMessage.tsx` — Chat message bubble component
  - Generation commands registered in CommandPalette
- `components/ui/` — Button (shadcn/cva-based), Input, Select
- `components/shadcn/` — shadcn/ui generated primitives (future component source)
- `components/shared/` — QueryProvider, ErrorBoundary

**State Management (three-layer):**
- **Server state:** TanStack Query v5 — all API data (novels, chapters, user, settings)
- **UI state:** Zustand — sidebar toggles, focus mode, save status, active chapter ID, editor ref (set by EditorSurface, read by CommandPalette)
- **Local state:** useState for component-ephemeral state

**API Client:**
- `lib/api/client.ts` — Native fetch with token refresh, no axios; `setAccessToken`/`clearAccessToken` sync `narrare_auth` cookie for proxy
- `lib/api/streaming.ts` — SSE streaming client for AI responses (fetch + ReadableStream)
- API clients: `promptsApi` (7 methods for prompt CRUD) + `generationApi` (1 method for name generation)
- `lib/api/generation.ts` — API client for writing generation (SSE streaming + WebSocket client for sessions)

**Styling:**
- Tailwind CSS v4 as sole styling system (styled-jsx removed)
- CSS variables in `globals.css` for all design tokens (light + dark mode)
- shadcn/ui for component primitives (Radix-based, not a runtime dep)

**i18n:**
- next-intl with 3 languages (en, de, fr)
- Translations at `packages/i18n/messages/` (namespace-based structure)
- `validate-i18n.ts`: hardcoded string detection + key completeness + placeholder consistency

**Auth & Security:**
- In-memory access token (not localStorage)
- httpOnly refresh token cookie (`narrare_refresh`) — backend sets on login/register, refresh endpoint reads from cookie; cleared by `POST /api/v1/auth/logout`
- `cookie_helpers.py` — backend helper for setting/clearing refresh cookies (httpOnly, SameSite=Lax)
- `POST /api/v1/auth/logout` — clears `narrare_refresh` cookie; no server-side token invalidation needed (cookie is the sole revocation mechanism)
- `restoreSession()` — frontend function to restore session from httpOnly cookie via silent refresh
- `proxy.ts` — Next.js route-level proxy verifying JWT cookie (`narrare_auth`) via jose for server-side auth protection on `/dashboard`, `/wizard`, `/novel/*`; redirects to `/login` if invalid
- Client syncs `narrare_auth` cookie alongside in-memory token (for proxy consumption)
- `_sessionChecked` guard in authStore — prevents infinite 401 refresh loops by tracking `loadUser()` terminal state; breaks retry cycle after first failed session check
- Auto-redirect to /login on 401

**Testing:**
- Vitest 3.x + Testing Library + MSW
- 453 tests across proxy, utils, stores, API client, UI components, wizard steps
- `npm run test` / `vitest run`

#### `tests/` — Test Suite

**Unit tests (31 files):**
- `core/llm/` — gateway, intents, retry, providers_registry, embeddings (5 files)
- `core/prompts/` — registry, composer, variable_engine, meta, variable_engine_hypothesis (5 files)
- `core/shared/` — frontmatter, result, errors, file_utils, result_hypothesis, frontmatter_hypothesis (6 files)
- `api/setup/` — setup_service, setup_schemas, demo_loader, provider_service, _complete_helpers, test_setup_complete_providers (6 files)
- `api/auth/` — auth_service, security (2 files)
- `api/chapters/` — chapter_service (1 file)
- `api/novels/` — novel_service (1 file)
- `api/volumes/` — volume_service (1 file)
- `api/metrics/` — metrics_router (1 file)
  - `api/` — test_contracts.py, test_fake_conformance.py (2 files)
  - **LLM testing infrastructure**: `ALLOW_MODEL_REQUESTS=False` global guard, `TestModel`/`FunctionModel` fixtures, `capture_run_messages` fixture for tool call assertions
  - Plus 3 hypothesis property-based tests (in core/shared and core/prompts)

**Integration tests (7+ files):**
- `setup/test_setup_api.py`, `novels/test_novels_api.py`
- `chapters/test_chapters_api.py`, `auth/test_auth_api.py`
- `settings/test_settings_api.py`, `volumes/test_volumes_api.py`
- `health/test_health.py`
- `conftest.py` with shared fixtures (registered_user, novel_id, auth helpers)
- `conftest.py` runs `alembic upgrade head` (not `Base.metadata.create_all()`) to validate migrations
- `conftest.py` provides `NARRARE_ENCRYPTION_KEY` via autouse fixture

**E2E:** Directory exists, no tests yet.

#### Frontend Tests (packages/web/)

**243 tests across:**
- `proxy.test.ts` — 10 tests (JWT verification, route protection, redirects)
- `lib/utils.test.ts` — 32 tests (cn, debounce, formatWordCount, etc.)
- `lib/stores/editorStore.test.ts` — 21 tests
- `lib/api/client.test.ts` — 17 tests (token management + cookie sync)
- `lib/stores/authStore.test.ts` — 15 tests
- `components/ui/` — 19 tests (Button, Input)
- `components/setup/` — WizardStep1-5 + WizardShell tests

#### Infrastructure

- `scripts/` — `check_architecture.py`, `seed_dev_user.py`, `check_commit_message.py`, `demo_data/`, `local/`
- `.devcontainer/` — full dev container setup
- `.github/workflows/` — CI (`ci.yml`), architecture check (`architecture.yml`), release (`release-please.yml`)
- Docker Compose (`docker-compose.dev.yml`) for PostgreSQL (pgvector) + Redis
- `justfile`, `pyproject.toml`, `uv.lock`

### AI Tooling (opencode + OAC)

- opencode CLI installed in dev container
- OpenAgentsControl (OAC) installed with full profile
- Custom Narrare Orchestrator agent (`.opencode/agent/narrare-orchestrator.md`)
- Narrare behavioral rules (`.opencode/context/narrare/` — 5 files: architecture, documentation, implementation, navigation, orchestration)
- Narrare navigation pointing to `docs/` as single source of truth

---

## What Is In Progress

Phase 5 (current) — writing generation feature complete:
1. ✅ Writing generation pipeline (WRITE-002) — fully implemented
2. KB dedup integration for name generator
3. Backend test coverage gaps (memory service, prompt management)
4. Frontend test coverage gaps (generation panel, session panel)
5. E2E tests with Playwright

Next focus: extend chapter (WRITE-003), rewrite selection (WRITE-004), KB editor UI.

---

## What Is Blocked

Nothing blocking Phase 5.

All demo content is complete — sufficient for testing through Phase 5.

---

## Resolved Since Last Update

| Item | Resolution |
|------|-----------|
| Q-004 Celery vs arq | → TaskIQ. ADR-007 created. arq in maintenance-only mode. |
| Q-005 GLM/Z.AI/pydantic-ai | → OpenAI-compatible endpoints. Factory function in `core/llm/_providers/zai.py`. |
| Dead links in docs/ | Fixed: CURRENT_STATE.md created, PROJECT_VISION path corrected, Q-005 reference fixed |
| Deployment guide gaps | CI pipeline specs, pre-commit config, justfile catalog, env vars added |
| Coding standards gaps | Result type pattern, service DI pattern added |
| CURRENT_STATE.md drift | Audited and corrected — Phases 1–3 were implemented but not reflected |
| Frontend stack optimized | axios→fetch, styled-jsx→Tailwind v4, shadcn/ui, motion, jose middleware, i18n lint |
| editorStore duplication removed | Server state now exclusively in TanStack Query, Zustand for UI state only |
| Error handling added | Route-level error.tsx + global-error.tsx + ErrorBoundary component |
| Loading states added | Skeleton loading.tsx at all route levels |
| debounce autosave bug fixed | useRef-based debounce pattern replaces broken useCallback |
| Tech Stack Audit | Complete — 16 changes across Core, Backend, Platform, Docs |
| bcrypt → argon2 | ADR-009, security.py rewritten |
| slowapi → fastapi-limiter | ADR-009, async-native Redis rate limiting |
| OpenTelemetry | ADR-010, replaces prometheus-client |
| Langfuse LLM Observability | ADR-010, integrated in gateway via observability.py |
| Content Versioning | ADR-011, chapter_versions table + API endpoints |
| Event-Driven Architecture | ADR-012, core/events + Redis Pub/Sub + TaskIQ |
| infer_provider heuristics | Fixed: explicit model registration + declarative prefix mapping |
| Error Classification | Fixed: layered exceptions (pydantic-ai typed → stdlib → string fallback) |
| Correlation IDs | Enhanced: full UUID + OTel trace context + response headers |
| pgBouncer | Added to Docker Compose (production profile) |
| pydantic-ai v1.93 migration | OpenAIProvider wrapper + output_type rename for API compat |
| Z.AI endpoint selector | Wizard offers General vs Coding API for Z.AI users |
| Provider error pass-through | Real provider errors surfaced to users, not generic messages |
| TYPE_CHECKING ForwardRef fix | All schemas + routers: moved runtime types out of TYPE_CHECKING |
| Dashboard New Novel → Wizard | "New Novel" now launches setup wizard instead of direct creation |
| Q-006 Configurable Model Routing | → Runtime cascade with multi-provider, encrypted API keys, 7 intent categories |
| Setup wizard DB gap | Fixed: `complete()` now writes to `user_providers` + `user_ai_settings` — AI Settings pages work immediately after setup |
| Auto-migration on startup | `lifespan.py` runs `alembic upgrade head` before serving — no manual migration step needed |
| Post-login redirect | `/auth/me` returns `has_providers` flag; login/register redirects to `/wizard` if no providers |
| Alembic env.py | All 5 model modules imported — `alembic revision --autogenerate` detects all schema changes |
| Integration test migrations | Tests use real Alembic migrations (not `create_all()`) — catches migration bugs in CI |
| Setup RULE-04 split | `_validation.py` extracted from `service.py` (325→190 lines) |
| Frontend toggle switches | Fixed dimensions: `w-11 h-6` track, `w-5 h-5` knob in CategoryOverrides + IntentOverrides |
| AI Providers migration warning | Changed to subtle hint, hidden for Ollama, i18n key `migrationWarning` → `addKeyHint` |
| Migration 0004 schema gap | Fixed: migration 0005 adds `token_limit_profile` to `project_settings` — was only added to `user_ai_settings` |
| RULE-14 Migration Discipline | New rule: every model column needs a migration, cross-table check required, regression test mandatory |
| Issue 4: Auth session | httpOnly refresh token cookie (`narrare_refresh`) set on login/register; refresh endpoint reads from cookie; frontend `restoreSession()` via silent refresh |
| Issue 1: Focus mode exit | ESC handler + floating Minimize2 button (semi-transparent, focus-mode only) in EditorLayout |
| Issue 2: Dashboard delete | Trash2 icon on NovelCards (hover-revealed, confirm dialog); `novelsApi.delete()` mutation |
| Issue 3: Wizard flow | Steps 2↔3 swapped (starter selection → novel details); demo metadata.json with author/logline/pov/tags; WizardStep3 prefills store |
| Issue 5: Editor extensions | NarrareDocument, DialogueMark, Autosave extensions + CommandPalette (Cmd+K) + commands.ts registry; EditorSurface refactored for Autosave; editorStore holds editor ref |
| Memory layer implementation | Core memory module: mem0 AsyncMemory with pgvector, FeedbackService, PreferenceService, NullMemoryClient, dual storage architecture, RULE-01 exception |
| Prompt management implementation | PromptManagementService with 7 API endpoints for CRUD, update detection, diff comparison; variable metadata registry; frontend PromptSettings/PromptEditor/PromptDiff |
| Culture injection | {{culture_guidelines}} placeholder, resolve_culture() with EN fallback, 9 culture definitions (fantasy/modern/scifi × en/de/fr) |
| Generation intents | GENERATE, NAME_GENERATE, TITLE_GENERATE in IntentCategory.GENERATION |
| Name generator implementation | API endpoint POST /generation/names, frontend NameGenerator + NameResults components, i18n for 3 locales |
| Migration 0006 | feedback_events table for memory layer dual storage |
| mem0 integration | mem0ai>=1.0 added to core dependencies, psycopg[binary]>=3.0 for pgvector |
| Metadata sidebar (replaces status bar) | EditorView: bottom status bar replaced by collapsible right MetadataSidebar with live stats, session tracking, chapter metadata, and novel progress |
| Volume Management | WRITE-011 fully implemented — backend enrichment, stats, reorder, frontend UI with volume selector and management page |
| Pydantic AI testing tools | `TestModel`/`FunctionModel`/`capture_run_messages` fixtures, `ALLOW_MODEL_REQUESTS=False` guard, FakeLLMGateway in integration tests |

---

## Decisions Made (full log in ADR files)

| ADR | Decision | Status |
|-----|---------|--------|
| ADR-001 | Single LLM Gateway | ✅ Implemented in `core/llm/gateway.py` |
| ADR-002 | Unified Prompt System | ✅ Implemented in `core/prompts/` |
| ADR-003 | Protocol-First Development | ✅ Applied across all API modules |
| ADR-004 | Hard File Size Limits | ✅ Enforced via `check_architecture.py` |
| ADR-005 | Directory Structure & Module Ownership | ✅ Applied |
| ADR-006 | Technology Stack | ✅ Applied |
| ADR-007 | TaskIQ for Background Tasks | ✅ Decided, integration pending |
| ADR-009 | Security Stack Modernization (argon2 + fastapi-limiter) | ✅ Implemented |
| ADR-010 | Observability Strategy (OpenTelemetry + Langfuse) | ✅ Implemented |
| ADR-011 | Content Versioning for Chapters | ✅ Implemented |
| ADR-012 | Event-Driven Architecture (Redis Pub/Sub) | ✅ Implemented |
| ADR-013 | Internationalization Architecture | ✅ Implemented |
| ADR-014 | RULE-14: Model-Migration Consistency | ✅ Enforced |

---

## Open Questions (summary)

| ID | Question | Status | Blocks |
|----|---------|--------|--------|
| Q-001 | MCP auth strategy | 🟡 Open | apps/mcp/ (post-MVP) |
| Q-002 | A2A streaming requirement | 🟡 Open | apps/a2a/ (post-MVP) |
| Q-003 | Embedding provider abstraction | 🟡 Open | core/llm/embeddings.py (post-MVP) |
| Q-004 | Celery vs arq | ✅ Resolved → TaskIQ | — |
| Q-005 | GLM/Z.AI compatibility | ✅ Resolved → OpenAI-compatible | — |
| Q-006 | Configurable Model Routing | ✅ Resolved → Runtime cascade | — |

---

## Known Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Python 3.14 missing type stubs for some deps | Low | Low | Tried `reportMissingTypeStubs = true` — 261 false positives from inline-typed first-party code. Documented with TODO in pyproject.toml |
| TipTap v3 extension API changes | Low | Medium | Pin exact version in package.json |
| Feature spec files not yet individualized | Low | Low | INDEX.md has catalogue, can be expanded per-feature as needed |
| Frontend Button tests use semantic token assertions (not class names) — may break if shadcn tokens change | Low | Low | Update test assertions when tokens change |
| Editor uses h-full inside flex container — new pages must handle their own scroll | Low | Low | Follow DashboardView pattern: h-full overflow-y-auto wrapper |

---

## Next Session Should Start With

**Phase 5 (current):**
1. Writing module tests — unit tests for core writing pipeline, context assembler, draft processor, session manager
2. Writing module integration tests — API-level tests for generation endpoints, SSE streaming, WebSocket sessions
3. KB dedup integration for name generator (currently a placeholder)
4. AI features in editor toolbar slots (using commands.ts registry pattern)
5. E2E tests with Playwright (route mocking for LLM responses)
6. Backend test coverage gaps (memory service, prompt management, generation, settings, gateway error classification, retry logic)
7. Frontend test coverage gaps (prompt settings, name generator, editor extensions, CommandPalette, dashboard delete, focus mode)

**Post-MVP (future):**
1. Connect writing features to the editor (SSE streaming sessions)
2. Build KB editor UI (interactive AI sessions)
3. Add analysis panels to the ContextPanel
4. Embedding provider abstraction (Q-003)
5. Fallback chains for model routing (if primary fails, try secondary)
6. Model recommendation and benchmarking

Infrastructure now includes: OpenTelemetry tracing, Langfuse LLM observability, event-driven
architecture (Redis Pub/Sub → TaskIQ), content versioning, argon2id auth, async rate limiting,
memory layer (mem0 + pgvector), prompt management (override CRUD + diff), culture-aware generation.

---

> Maintained by: Architecture Agent, updated by Orchestrator at session end
