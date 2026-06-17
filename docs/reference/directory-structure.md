# Narrare — Directory Structure

> **This is the canonical structure.** New files go where this document says.
> If a file doesn't fit, that's a signal to ask the Architecture Agent first —
> not to create a new location.
>
> Maintained by: Architecture Agent
> Enforced by: `scripts/check_architecture.py` (module placement checks)

---

## Top-Level Layout

```
narrare/
├── apps/
│   ├── api/                    ← FastAPI application (WebUI backend)
│   ├── mcp/                    ← (planned) MCP server adapter
│   └── a2a/                    ← (planned) Agent-to-Agent adapter
│
├── packages/
│   ├── core/                   ← Shared domain logic (no HTTP, no users)
│   ├── i18n/                   ← Translation files and i18n utilities
│   └── web/                    ← Frontend (Next.js)
│
├── docs/
│   ├── _shared/                ← Constraints, Glossary, Tech Stack
│   ├── architecture/           ← ADRs, open questions
│   ├── development/            ← Coding standards, testing, UI, deployment
│   ├── features/               ← Feature specifications
│   ├── mvp/                    ← MVP plan
│   └── reference/              ← Directory structure, project vision
│
├── evals/                       ← Pydantic Evals suites (ADR-032)
│   ├── datasets/                ← Code-first Dataset/Case definitions
│   ├── evaluators/              ← Custom Evaluator implementations
│   ├── tasks/                   ← Smoke and runtime task entrypoints
│   ├── baselines/               ← Drift baselines
│   └── results/                 ← JSON reports (gitignored)
│
├── scripts/
│   ├── check_architecture.py   ← Hard constraint enforcement
│   ├── export_openapi.py       ← OpenAPI spec static export + CI drift check
│   └── ...
│
├── tests/
│   ├── unit/                   ← Unit tests (mirror source structure)
│   ├── integration/            ← Integration tests (API-level)
│   └── e2e/                    ← End-to-end tests
│
├── .github/
│   └── workflows/              ← CI/CD pipelines
│
├── pyproject.toml              ← Python project config, constraint registry
├── .pre-commit-config.yaml     ← Pre-commit hooks
└── justfile                    ← Task runner
```

---

## `packages/i18n/` — Translations (Source of Truth)

Single source of truth for all translation files. Consumed by the frontend (next-intl) today,
and by Python services (CLI, MCP, A2A) in the future.

```
packages/i18n/
├── messages/                      ← Source of truth for all translations
│   ├── en/                        ← English (reference locale)
│   │   ├── common.json            ← Shared UI strings (loading, save, cancel, etc.)
│   │   ├── auth.json              ← Login, register, logout
│   │   ├── wizard.json            ← Setup wizard (steps 1-5, structures, tones)
│   │   ├── dashboard.json         ← Novel list and dashboard
│   │   ├── editor.json            ← Editor UI, chapters, save status
│   │   ├── errors.json            ← Error messages and fallbacks
│   │   └── settings.json          ← Settings page
│   ├── de/                        ← German translations (mirrors en/)
│   └── fr/                        ← French translations (mirrors en/)
├── narrare_i18n/
│   └── __init__.py                ← Future Python loader (CLI/MCP/A2A)
└── pyproject.toml
```

---

## `packages/core/` — The Foundation

The core package has **no knowledge of HTTP, users, authentication, or databases**.
It is the layer that would work identically whether called from FastAPI, MCP, CLI, or a test.

```
packages/core/narrare_core/
│
├── agents/                     ← Pydantic-ai agents (NarrareAgent subclasses) — all agents live here
│                                   (ChatAgent lives in chat/ — see below)
├── ai_invocation/               ← AI Invocation Adoption Contract (ADR-038, INFRA-013)
│   ├── __init__.py             ← Exports: InvocationPipeline, PromptInvocationContext
│   ├── contracts.py            ← PromptInvocationContext, AdoptionPolicy, Protocol definitions
│   ├── pipeline.py             ← InvocationPipeline orchestrator
│   ├── enrichers/              ← Context enrichment chain
│   │   ├── preferences.py      ← PreferenceContextEnricher
│   │   └── ...
│   ├── validators/             ← Prompt validation
│   │   ├── runtime.py          ← RuntimeVariableValidator
│   │   ├── final_prompt.py     ← FinalPromptValidator
│   │   └── ...
│   ├── budgets/                ← Output budget resolution
│   │   ├── resolver.py         ← IntentOutputBudgetResolver
│   │   ├── _types.py           ← OutputBudget, OutputBudgetDecision
│   │   └── ...
│   └── ...
├── llm/                        ← Everything LLM. The only place LLM clients live.
│   ├── __init__.py             ← Exports: LLMGateway, LLMIntent, LLMResult
│   ├── gateway.py              ← THE gateway. All LLM calls go here. Max 300 lines.
│   ├── intents.py              ← LLMIntent enum, IntentCategory, INTENT_CATEGORY_MAP, ResolvedModelConfig
│   ├── model_routing.py        ← ModelRoutingResolver protocol, ResolvedModel result type
│   ├── override_schemas.py     ← Pydantic schemas for category/intent/token limit overrides
│   ├── result.py               ← LLMResult, StreamChunk, LLMError types
│   ├── retry.py                ← Retry logic, backoff, error classification
│   ├── metrics.py              ← Cost tracking, token counting, telemetry hooks
│   ├── embeddings.py           ← Embedding calls (approved RULE-01b exception)
│   └── _providers/             ← Provider-specific adapters (internal only)
│       ├── openai.py
│       ├── anthropic.py
│       └── registry.py         ← Maps provider name → adapter; infer_provider() (dev-only)
│
├── prompts/                    ← Everything prompts. The only place prompts are built.
│   ├── __init__.py             ← Exports: PromptComposer, PromptContext, PromptRegistry
│   ├── composer.py             ← Assembles final prompt from parts. Max 250 lines.
│   ├── registry.py             ← Single cascade resolver for all features
│   ├── context.py              ← PromptContext dataclass (carries all variables)
│   ├── meta.py                 ← Meta-prompt loader (one implementation, used by all)
│   ├── variable_engine.py      ← Variable substitution, validation, optionality
│   ├── cache.py                ← Prompt cache (fixed key strategy)
│   ├── service.py              ← CRUD for file-based prompt management (UI/API)
│   └── _bundled/               ← Bundled prompt files (not Python)
│       ├── meta/
│       │   ├── en/system.md
│       │   ├── en/system.lite.md
│       │   └── de/system.md
│       ├── writing/
│       ├── kb/
│       └── analysis/
│
├── context/                    ← Context assembly (KB, chapters → PromptContext)
│   ├── __init__.py
│   ├── assembler.py            ← 5-tier context pipeline
│   ├── budget.py               ← Token budget calculator
│   └── model_limits.py         ← Model registry and limits
│
├── writing/                    ← Writing generation pipeline
│   ├── __init__.py
│   ├── models.py               ← GenerationMode, GenerationStatus, WritingContext, GenerationRequest, SessionState, SceneState
│   ├── context_models.py       ← KBEntity, RecentChapter dataclasses
│   ├── contracts.py            ← WritingPipelineProtocol, ContextAssemblerProtocol, DraftProcessorProtocol, SessionManagerProtocol
│   ├── context_assembler.py    ← WritingContextAssembler with 5-tier ranking + token budgets
│   ├── budget.py               ← TokenBudgetManager for tier allocation
│   ├── draft_processor.py      ← DraftProcessor with artifact removal + markdown normalization
│   ├── _invocation_adapter.py  ← ADR-038 InvocationPipeline adapter around PromptComposer.build()
│   ├── pipeline.py             ← WritingPipeline with 4-mode dispatch
│   ├── pipeline_scene.py       ← Scene-by-scene mode logic
│   ├── pipeline_interview.py   ← Interview-assisted mode logic
│   └── session_manager.py      ← SessionManager with cache-backed persistence
│
├── embeddings/                 ← Vector operations
│   ├── __init__.py
│   ├── store.py                ← pgvector abstraction (only place pgvector is used)
│   └── similarity.py           ← Similarity search utilities
│
├── memory/                     ← Memory layer
│   ├── __init__.py
│   ├── service.py              ← MemoryService interface + implementation
│   └── client.py               ← mem0 adapter (only place mem0 is used)
│
├── cache/                      ← Caching abstraction
│   ├── __init__.py
│   └── client.py               ← Redis abstraction (only place redis is used)
│
├── chat/                       ← Free-Form Chat (CHAT-001, ADR-024)
│   ├── __init__.py             ← Exports: ChatAgent, ChatDeps, ChatServiceProtocol
│   ├── chat_agent.py           ← ChatAgent[ChatDeps, str] — conversational agent
│   ├── chat_deps.py            ← ChatDeps — prompt composition per turn
│   ├── chat_service_core.py    ← Pure business logic (context assembly)
│   ├── conversation_store.py   ← DB persistence for chat history
│   ├── contracts.py            ← ChatServiceProtocol
│   └── schemas.py              ← Pydantic schemas
│
├── notifications/              ← External notifications
│   ├── __init__.py
│   └── email.py                ← SMTP adapter (only place aiosmtplib is used)
│
├── research/                   ← Web research abstraction
│   ├── __init__.py
│   ├── contracts.py            ← SearchClientProtocol
│   └── search_client.py        ← Tavily/SerpAPI adapters
│
├── tasks/                      ← Background task infrastructure
│   ├── __init__.py
│   └── worker.py               ← TaskIQ broker (only place TaskIQ is configured)
│
├── init/                       ← Project initialization logic
│   ├── __init__.py
│   ├── service.py              ← ProjectInitialiser
│   └── template_resolver.py    ← Markdown template cascade for init
│
├── shared/                     ← Pure utilities used across core
│   ├── frontmatter.py          ← Frontmatter parsing (one implementation)
│   ├── file_utils.py           ← File locking, path helpers
│   ├── pagination.py           ← Shared pagination types
│   ├── crypto.py               ← Fernet encryption for API keys (NARRARE_ENCRYPTION_KEY)
│   ├── result.py               ← Result type pattern (Ok/Err)
│   └── errors.py               ← Shared error types
│
└── schemas/                    ← Shared Pydantic schemas (no business logic)
    ├── auth.py
    ├── novels.py
    ├── chapters.py
    ├── kb.py
    ├── writing.py
    ├── analysis.py
    ├── cost.py
    ├── context.py
    └── learning.py
```

---

## `packages/web/` — Next.js 16 Frontend
The web frontend for Narrare. Next.js App Router with TypeScript.
**Styling:** Tailwind CSS v4 only (no styled-jsx, no CSS modules).
**State:** TanStack Query for server state, Zustand for UI state.

```
packages/web/
├── app/                            ← Next.js App Router pages
│   ├── layout.tsx                  ← Root layout (QueryProvider, NextIntlClientProvider)
│   ├── page.tsx                    ← Root redirect
│   ├── proxy.ts                    ← Route protection (JWT exp check via jose)
│   ├── global-error.tsx            ← Last-resort error boundary
│   ├── error.tsx                   ← General error fallback
│   ├── (auth)/                     ← Public auth route group
│   │   ├── login/page.tsx          ← Login form
│   │   ├── register/page.tsx       ← Registration form
│   │   └── loading.tsx             ← Auth page skeleton
│   └── (app)/                      ← Authenticated route group
│       ├── layout.tsx              ← Auth shell (user info, top bar)
│       ├── loading.tsx             ← App-level skeleton
│       ├── error.tsx               ← Authenticated error fallback
│       ├── dashboard/
│       │   ├── page.tsx            ← Novel list + create
│       │   └── loading.tsx         ← Dashboard skeleton
│       ├── settings/               ← User settings pages
│       │   ├── ai-providers/page.tsx ← Manage AI providers (add/edit/delete)
│       │   └── ai-model/page.tsx   ← Model routing & token limit profiles
│       └── novel/[id]/editor/
│           ├── page.tsx            ← Editor page (thin — delegates to EditorLayout)
│           ├── loading.tsx         ← Editor skeleton
│           └── error.tsx           ← Editor-specific error fallback
│
├── components/
│   ├── editor/                     ← Writing editor components
│   │   ├── EditorLayout.tsx        ← Orchestrator: toolbar + sidebar + surface + panel + focus mode (ESC/Minimize2)
│   │   ├── EditorSurface.tsx       ← TipTap v3 editor with Autosave extension + Cmd+S
│   │   ├── EditorToolbar.tsx       ← Toolbar with sidebar/panel/focus toggles
│   │   ├── ChapterSidebar.tsx      ← Chapter list with DnD reorder (@dnd-kit)
│   │   ├── ContextPanel.tsx        ← Right panel (AI features slot)
│   │   ├── StatusBar.tsx           ← Word count, reading time, save status
│   │   ├── CommandPalette.tsx      ← Cmd+K palette with format + editor commands
│   │   ├── commands.ts             ← Command registry (extensible for AI features)
│   │   └── extensions/
│   │       ├── NarrareDocument.ts  ← Chapter-scoped document node
│   │       ├── SceneBreak.ts       ← Custom TipTap node (--- → * * *)
│   │       ├── DialogueMark.ts     ← Dialogue span mark (future: character attribution)
│   │       └── Autosave.ts         ← Debounced save extension (configurable interval)
│   ├── dashboard/
│   │   └── DashboardView.tsx       ← Novel grid with NovelCard (create + delete with confirm dialog)
│   ├── setup/                      ← Setup wizard
│   │   ├── WizardShell.tsx         ← Wizard layout + navigation
│   │   └── WizardStep1-5.tsx       ← Individual wizard steps
│   ├── settings/                   ← AI settings components
│   │   ├── ProviderList.tsx        ← Provider management (add/edit/delete)
│   │   ├── ProviderForm.tsx        ← Provider form with credential validation
│   │   ├── ModelRoutingPanel.tsx   ← Category/intent model overrides
│   │   └── TokenLimitPanel.tsx     ← Token limit profile selector + overrides
│   ├── ui/                         ← UI primitives
│   │   ├── Button.tsx              ← shadcn/cva-based button (primary/secondary/ghost/danger + loading)
│   │   ├── Input.tsx               ← Text input with label/error/hint
│   │   └── Select.tsx              ← Select dropdown
│   ├── studio/                       ← AI-assisted writing studio components
│   │   └── editor/
│   │       ├── GenerationPanel.tsx    ← Generation trigger + streaming display
│   │       ├── GenerationConfig.tsx   ← Mode selection + options (4 modes, tone variants)
│   │       ├── GenerationDraft.tsx    ← Draft zone + controls (accept, reject, save)
│   │       ├── SessionPanel.tsx       ← Interactive session chat UI
│   │       └── ChatMessage.tsx        ← Chat message bubble component
│   ├── shadcn/                     ← shadcn/ui generated components (future use)
│   └── shared/
│       ├── QueryProvider.tsx       ← TanStack Query client provider
│       └── ErrorBoundary.tsx       ← Client-side React error boundary
│
├── lib/
│   ├── api/
│   │   ├── client.ts              ← fetch-based API client with token refresh (230 lines)
│   │   ├── streaming.ts           ← SSE streaming client for AI responses
│   │   └── generation.ts          ← API client for writing generation (SSE streaming + WebSocket client)
│   ├── stores/
│   │   ├── editorStore.ts         ← UI state: activeChapterId, saveStatus, toggles, editor ref (for CommandPalette)
│   │   ├── authStore.ts           ← Auth state + login/register/restoreSession actions
│   │   └── wizardStore.ts         ← Wizard form state
│   ├── i18n/
│   │   ├── request.ts             ← next-intl request config
│   │   └── routing.ts             ← i18n routing config
│   └── utils.ts                   ← cn(), debounce, formatWordCount, formatRelativeTime, truncate
│
├── styles/
│   └── globals.css                ← Design tokens (CSS variables), Tailwind v4 import, editor prose styles
│
├── types/
│   └── index.ts                   ← Shared TypeScript types (Novel, Chapter, User, etc.)
│
├── components.json                ← shadcn/ui configuration
├── biome.json                     ← Biome linter and formatter configuration
├── next.config.ts                 ← Next.js config with next-intl plugin + API rewrite
├── tsconfig.json                  ← TypeScript strict config
└── package.json                   ← Dependencies
```

### Frontend File Size Limits (from ui-principles.md)

| Pattern | Hard limit |
|---------|-----------|
| Page component (`page.tsx`) | 100 lines |
| Feature component | 200 lines |
| Hook (`use*.ts`) | 150 lines |
| Store (`*Store.ts`) | 150 lines |
| API function file | 300 lines |
| Type definition file | 200 lines |

---

## `apps/api/` — The Service Layer

Each domain module is self-contained. The structure inside every module is identical.

```
apps/api/narrare/
│
├── _app/                       ← Application wiring (not a domain)
│   ├── main.py                 ← FastAPI app factory
│   ├── database.py             ← SQLAlchemy async engine + get_db()
│   ├── dependencies.py         ← Shared FastAPI dependencies
│   ├── middleware.py           ← CORS, rate limiting, logging middleware
│   └── lifespan.py             ← Startup/shutdown handlers
│
├── auth/
│   ├── __init__.py             ← Public exports only
│   ├── contracts.py            ← AuthServiceProtocol  ← WRITTEN FIRST
│   ├── schemas.py              ← Request/response Pydantic models
│   ├── models.py               ← SQLAlchemy User model
│   ├── repository.py           ← DB queries (select, insert, update)
│   ├── service.py              ← Business logic (uses repository)
│   ├── security.py             ← JWT, password hashing
│   ├── cookie_helpers.py       ← httpOnly refresh cookie set/clear (narrare_refresh)
│   ├── router.py               ← FastAPI routes (login, register, refresh, logout)
│   └── router_me.py            ← GET /me route (extracted for file size limit)
│
├── novels/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── models.py
│   ├── repository.py
│   ├── service.py
│   └── router.py
│
├── chapters/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── models.py
│   ├── repository.py
│   ├── service.py
│   ├── summarize_service.py    ← Separate service: one responsibility
│   └── router.py
│
├── volumes/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── models.py
│   ├── repository.py
│   ├── service.py
│   └── router.py
│
├── writing/                    ← Writing generation module (4 modes: full_draft, scene_by_scene, interview_assisted, interactive_session)
│   ├── __init__.py
│   ├── contracts.py            ← WritingServiceProtocol, GenerationRepositoryProtocol, SuggestServiceProtocol
│   ├── schemas.py              ← 11 Pydantic request/response schemas
│   ├── models.py               ← GenerationRequest SQLAlchemy model
│   ├── repository.py           ← GenerationRepository (CRUD, status transitions, concurrent prevention)
│   ├── service.py              ← WritingService (orchestration of pipeline + repo + feedback)
│   ├── suggest_service.py      ← InlineSuggestService (ghost text — lightweight, no pipeline)
│   ├── scene_service.py        ← Scene-by-scene methods
│   ├── stats_service.py        ← Generation analytics
│   ├── ws_handler.py           ← WebSocket session handler
│   ├── _ws_cache.py            ← WebSocket connection cache for active sessions
│   ├── router.py               ← REST + SSE endpoints (generate, stream, status, cancel)
│   ├── router_sessions.py      ← WebSocket route (WS /api/v1/writing/sessions/{chapter_id})
│   └── router_stats.py         ← Stats endpoints
│
├── kb/                         ← Knowledge Base
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── schemas_merge.py         ← Merge schemas (RULE-04 split from schemas.py)
│   ├── models.py
│   │
│   ├── management_service.py   ← CRUD: kb_add, kb_get, kb_update, kb_delete
│   ├── editor_service.py       ← Interactive AI sessions
│   ├── analyzer_service.py     ← Consistency checks, relationship suggestions
│   ├── suggest_service.py      ← Proactive KB suggestions
│   ├── worldbuilding_service.py← Worldbuilding operations
│   ├── extraction_service.py   ← Entity/fact extraction
│   ├── merge_contracts.py      ← KBMergeServiceProtocol
│   ├── merge_service.py        ← KBMergeService (calls KBMergeAgent)
│   │
│   ├── repository.py
│   ├── context_builder.py      ← Builds KB summary for context injection
│   │
│   ├── router_management.py    ← Routes: CRUD
│   ├── router_sessions.py      ← Routes: interactive sessions
│   ├── router_suggest.py       ← Routes: proactive suggestions
│   └── router_merge.py         ← Routes: merge/deduplication
│
├── analysis/                   ← All analysis features
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas/                ← One schema file per analysis type
│   │   ├── sentiment.py
│   │   ├── sensitivity.py
│   │   ├── readability.py
│   │   ├── pov.py
│   │   ├── coreference.py
│   │   ├── beta_reader.py
│   │   ├── voice.py
│   │   └── literary.py
│   │
│   ├── sentiment_service.py
│   ├── sensitivity_service.py
│   ├── readability_service.py
│   ├── pov_service.py
│   ├── coreference_service.py
│   ├── beta_reader_service.py
│   ├── literary_service.py
│   │
│   ├── voice/                  ← Voice analysis is complex enough for a sub-package
│   │   ├── __init__.py
│   │   ├── contracts.py
│   │   ├── author_service.py
│   │   ├── character_service.py
│   │   └── drift_service.py
│   │
│   ├── router_text.py          ← Routes: per-text analysis
│   ├── router_chapter.py       ← Routes: chapter-level
│   └── router_novel.py         ← Routes: novel-level
│
├── planning/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── models.py
│   ├── repository.py
│   ├── service.py
│   ├── _character_arc_factory.py    ← Factory for CharacterArcService DI
│   ├── _timeline_factory.py         ← Factory for TimelineService DI
│   ├── character_arc_service.py     ← CharacterArcService (calls CharacterArcAgent)
│   ├── timeline_service.py          ← TimelineService (calls TimelineAgent)
│   └── router.py
│
├── ai_assist/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── service.py
│   └── router.py
│
├── chat/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── service.py
│   └── router.py
│
├── generation/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── plot_service.py
│   ├── name_service.py
│   └── router.py
│
├── graph/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── models.py
│   ├── repository.py
│   ├── service.py
│   ├── facts_service.py        ← Fact extraction (separate responsibility)
│   └── router.py
│
├── consistency/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── checker_service.py
│   ├── rules_service.py        ← Rule-based checks (separate from AI checks)
│   └── router.py
│
├── timeline/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── models.py
│   ├── repository.py
│   ├── service.py
│   └── router.py
│
├── learning/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── models.py
│   ├── repository.py
│   ├── service.py
│   └── router.py
│
├── context/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   └── router.py               ← Thin: delegates to core/context/assembler
│
├── embeddings/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── service.py              ← Queue status, reprocessing management
│   ├── tasks.py                ← TaskIQ tasks (embedding generation)
│   └── router.py
│
├── prompts/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── models.py               ← UserPromptTemplate DB model
│   ├── repository.py
│   ├── user_template_service.py
│   └── router.py
│
├── settings/
│   ├── __init__.py
│   ├── contracts.py            ← Repository + service protocols (RULE-03)
│   ├── schemas.py
│   ├── models.py
│   ├── repository.py
│   ├── user_providers_repository.py  ← CRUD for user_providers table
│   ├── user_ai_settings_repository.py ← User AI settings DB queries
│   ├── project_ai_settings_repository.py ← Project AI overrides DB queries
│   ├── user_service.py
│   ├── project_service.py
│   ├── user_providers_service.py     ← Provider CRUD + credential validation + encryption
│   ├── user_ai_settings_service.py   ← Default model, overrides, token limits
│   ├── project_ai_settings_service.py ← Project overrides + source metadata
│   ├── model_routing_resolver.py     ← Resolves ResolvedModelConfig via cascade
│   ├── resolver.py             ← Effective settings resolution
│   └── router.py
│
├── analytics/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── models.py
│   ├── repository.py
│   ├── service.py
│   └── router.py
│
├── cost/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── models.py
│   ├── repository.py
│   ├── service.py
│   └── router.py
│
├── export/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── service.py
│   └── router.py
│
├── import_service/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── analyze_service.py
│   ├── execute_service.py
│   └── router.py
│
├── research/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── service.py
│   └── router.py
│
├── sync/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── service.py
│   └── router.py
│
├── setup/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── service.py              ← Main service (delegates validation to _validation.py)
│   ├── _validation.py          ← Step validation pure functions (RULE-04 split)
│   ├── demo_loader.py
│   ├── demo_data/               ← Bundled demo project files
│   │   ├── en/
│   │   │   ├── echoes-of-the-thornwall/
│   │   │   │   ├── metadata.json  ← Demo project metadata (author, logline, pov, tags)
│   │   │   │   ├── chapters/
│   │   │   │   └── kb/
│   │   │   └── dead-signal/
│   │   │       ├── metadata.json
│   │   │       ├── chapters/
│   │   │       └── kb/
│   │   └── de/
│   │       └── im-stillen-wald/
│   │           ├── metadata.json
│   │           ├── chapters/
│   │           └── kb/
│   └── router.py
│
├── storyboard/
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── service.py
│   └── router.py
│
├── memory/
│   ├── __init__.py
│   ├── schemas.py
│   └── router.py               ← Thin: delegates to core/memory/service
│
├── providers/
│   ├── __init__.py
│   ├── schemas.py
│   ├── service.py              ← Caches model lists in Redis
│   └── router.py
│
└── metrics/
    └── router.py               ← Prometheus scraping endpoint
```

---

## `apps/mcp/` — MCP Adapter (Planned)

```
apps/mcp/
├── __init__.py
├── server.py                   ← MCP server entry point
├── tools/                      ← One file per tool group
│   ├── writing_tools.py        ← Calls apps/api writing services
│   ├── kb_tools.py
│   ├── analysis_tools.py
│   └── planning_tools.py
└── schemas/                    ← MCP-specific input/output schemas
```

No business logic here. Every tool handler calls a Service Layer method.

---

## `apps/a2a/` — A2A Adapter (Planned)

```
apps/a2a/
├── __init__.py
├── server.py                   ← A2A server entry point
├── agents/                     ← One file per agent capability
│   ├── writing_agent.py
│   └── research_agent.py
└── schemas/                    ← A2A-specific message schemas
```

---

## `docs/` — Documentation Structure

```
docs/
│
├── _shared/                    ← Shared documentation
│   ├── CONSTRAINTS.md          ← Architecture rules (machine-enforced)
│   ├── GLOSSARY.md             ← Shared vocabulary
│   └── TECH_STACK.md           ← Technology decisions
│
├── architecture/               ← Architecture documentation
│   ├── decisions/              ← ADRs (Architecture Decision Records)
│   │   ├── INDEX.md
│   │   ├── ADR-001-llm-gateway.md
│   │   ├── ADR-002-prompt-system.md
│   │   └── ...
│   └── questions/              ← Open questions
│       ├── INDEX.md
│       └── Q-*.md
│
├── development/                ← Developer documentation
│   ├── coding-standards.md     ← Python 3.14 + TypeScript standards
│   ├── testing-standards.md    ← Test strategy and coverage goals
│   ├── ui-principles.md        ← UX principles and component patterns
│   ├── deployment-guide.md     ← CI/CD, dev environment, releases
│   └── orchestrator.md         ← Conversation patterns and routing
│
├── features/                   ← Feature specifications
│   ├── INDEX.md
│   ├── _TEMPLATE.md
│   └── [FEATURE-*.md]
│
├── mvp/                        ← MVP planning
│   └── mvp-plan.md             ← 5-phase plan for first running version
│
└── reference/                  ← Reference documentation
    ├── directory-structure.md  ← This file
    ├── openapi.json            ← Static OpenAPI spec (auto-generated, CI-checked)
    └── project-vision.md       ← Why Narrare exists, for whom
```

**Note:** `docs/agents/` still exists as reference for the original agent definitions, but the active documentation structure is now under `docs/` as shown above.

---

## `tests/` — Test Structure

```
tests/
├── unit/                       ← Fast, no I/O, no DB, no LLM
│   ├── core/
│   │   ├── llm/
│   │   │   ├── test_gateway.py
│   │   │   └── test_intents.py
│   │   ├── prompts/
│   │   │   ├── test_composer.py
│   │   │   ├── test_registry.py
│   │   │   └── test_variable_engine.py
│   │   └── ...
│   └── api/
│       ├── setup/
│       │   ├── test_setup_service.py
│       │   ├── test_setup_schemas.py
│       │   ├── test_demo_loader.py
│       │   ├── test_provider_service.py
│       │   ├── _complete_helpers.py     ← Shared helpers for setup completion tests
│       │   ├── test_setup_complete_providers.py  ← Provider creation + AI settings after setup
│       │   └── ...
│       ├── writing/
│       │   ├── test_draft_service.py
│       │   ├── test_session_service.py
│       │   └── ...
│       └── ...
│
├── integration/                ← Real DB, real Redis, mocked LLM
│   ├── writing/
│   │   └── test_writing_api.py
│   ├── kb/
│   └── ...
│
├── e2e/                        ← Full stack, real services
│   └── ...
│
└── conftest.py                 ← Shared fixtures (db, gateway mock, etc.)
```

---

## File Size Limits (from CONSTRAINTS.md RULE-04)

| Pattern | Hard limit |
|---------|-----------|
| `router*.py` | 150 lines |
| `service.py`, `*_service.py` | 300 lines |
| `repository.py` | 250 lines |
| `contracts.py` | 200 lines |
| `models.py`, `schemas.py` | 200 lines |
| `agent.py`, `*_agent.py` | 200 lines |
| `gateway.py` | 300 lines |
| `composer.py`, `registry.py` | 250 lines |
| All others | 400 lines |

When a file needs to grow beyond its limit, **split into a new module** — never compress to fit.

---

## Naming Conventions

| Thing | Convention | Example |
|-------|-----------|---------|
| Domain module | `snake_case/` | `writing/`, `kb/`, `ai_assist/` |
| Service file | `<name>_service.py` | `draft_service.py` |
| Router file | `router.py` or `router_<group>.py` | `router_sessions.py` |
| Contract file | `contracts.py` | — |
| Protocol name | `<Name>Protocol` | `DraftServiceProtocol` |
| Schema (request) | `<Action>Request` | `WriteChapterRequest` |
| Schema (response) | `<Name>Response` | `ChapterResponse` |
| Schema (internal) | `<Name>` | `PromptContext`, `LLMResult` |
| Test file | `test_<source_file>.py` | `test_draft_service.py` |
| TaskIQ task | `<verb>_<noun>_task` | `embed_chapter_task` |

---

> Last updated: project initialization
> Maintained by: Architecture Agent
> Changes require a DECISIONS.md entry
