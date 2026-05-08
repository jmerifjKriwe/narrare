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
│   ├── agents/                 ← Agent definitions and context packages
│   └── developer/              ← Human-facing developer documentation
│
├── scripts/
│   ├── check_architecture.py   ← Hard constraint enforcement
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

## `packages/core/` — The Foundation

The core package has **no knowledge of HTTP, users, authentication, or databases**.
It is the layer that would work identically whether called from FastAPI, MCP, CLI, or a test.

```
packages/core/narrare_core/
│
├── llm/                        ← Everything LLM. The only place LLM clients live.
│   ├── __init__.py             ← Exports: LLMGateway, LLMIntent, LLMResult
│   ├── gateway.py              ← THE gateway. All LLM calls go here. Max 300 lines.
│   ├── intents.py              ← LLMIntent enum + intent → model/params mapping
│   ├── result.py               ← LLMResult, StreamChunk, LLMError types
│   ├── retry.py                ← Retry logic, backoff, error classification
│   ├── metrics.py              ← Cost tracking, token counting, telemetry hooks
│   ├── embeddings.py           ← Embedding calls (approved RULE-01 exception)
│   └── _providers/             ← Provider-specific adapters (internal only)
│       ├── openai.py
│       ├── anthropic.py
│       └── registry.py         ← Maps provider name → adapter
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
│   └── worker.py               ← Celery app (only place Celery is configured)
│
├── init/                       ← Project initialization logic
│   ├── __init__.py
│   ├── service.py              ← ProjectInitialiser
│   └── template_resolver.py    ← Markdown template cascade for init
│
├── shared/                     ← Pure utilities used across core
│   ├── frontmatter.py          ← Frontmatter parsing (one implementation)
│   ├── file_utils.py           ← File locking, path helpers
│   └── pagination.py           ← Shared pagination types
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
│   └── router.py               ← FastAPI routes (thin, delegates to service)
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
├── writing/                    ← Split by responsibility (was 1200-line monolith)
│   ├── __init__.py
│   ├── contracts.py            ← All writing Protocols defined here
│   ├── schemas.py
│   ├── models.py               ← WritingSession, WritingMessage
│   │
│   ├── draft_service.py        ← One-shot: new/extend/rewrite chapter
│   ├── session_service.py      ← Interactive writing sessions
│   ├── multi_draft_service.py  ← Multi-draft generation
│   ├── unblock_service.py      ← Writer's block tools
│   ├── co_author_service.py    ← Co-author sessions
│   ├── voice_checker_service.py← Voice consistency checking
│   │
│   ├── session_store.py        ← Redis + filesystem session persistence
│   │
│   ├── router_drafts.py        ← Routes: /writing/new, /extend, /rewrite
│   ├── router_sessions.py      ← Routes: /writing/session/*
│   └── router_tools.py         ← Routes: /writing/unblock, /check-voice, /co-author
│
├── kb/                         ← Knowledge Base
│   ├── __init__.py
│   ├── contracts.py
│   ├── schemas.py
│   ├── models.py
│   │
│   ├── management_service.py   ← CRUD: kb_add, kb_get, kb_update, kb_delete
│   ├── editor_service.py       ← Interactive AI sessions
│   ├── analyzer_service.py     ← Consistency checks, relationship suggestions
│   ├── suggest_service.py      ← Proactive KB suggestions
│   ├── worldbuilding_service.py← Worldbuilding operations
│   ├── extraction_service.py   ← Entity/fact extraction
│   │
│   ├── repository.py
│   ├── context_builder.py      ← Builds KB summary for context injection
│   │
│   ├── router_management.py    ← Routes: CRUD
│   ├── router_sessions.py      ← Routes: interactive sessions
│   └── router_suggest.py       ← Routes: proactive suggestions
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
│   ├── tasks.py                ← Celery tasks (imports from core/tasks/)
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
│   ├── contracts.py
│   ├── schemas.py
│   ├── models.py
│   ├── repository.py
│   ├── user_service.py
│   ├── project_service.py
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
│   ├── service.py
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

## `docs/agents/` — Agent Definitions

```
docs/agents/
│
├── _shared/                    ← Every agent loads this automatically
│   ├── CONSTRAINTS.md          ← The rules (read-only for all agents)
│   ├── GLOSSARY.md             ← Shared vocabulary
│   ├── PROJECT_VISION.md       ← The why
│   └── CURRENT_STATE.md        ← What exists now (updated after each session)
│
├── architecture/
│   ├── AGENT.md                ← Role, behaviors, limits
│   ├── CONTEXT.md              ← Architecture summary (current)
│   ├── DECISIONS.md            ← Decision log
│   └── OPEN_QUESTIONS.md       ← Unresolved questions
│
├── implementation/
│   ├── AGENT.md
│   ├── CODING_STANDARDS.md     ← How code is written
│   ├── PATTERNS.md             ← Approved patterns with examples
│   └── GATEWAY_USAGE.md        ← How to use the LLM Gateway correctly
│
├── testing/
│   ├── AGENT.md
│   ├── TEST_STRATEGY.md        ← What to test, how, at which level
│   ├── PATTERNS.md             ← Test patterns with examples
│   └── COVERAGE_GOALS.md       ← Per-module coverage targets
│
├── ui/
│   ├── AGENT.md
│   ├── UX_PRINCIPLES.md        ← The UX vision
│   ├── COMPONENT_GUIDE.md      ← Component library and usage
│   └── DESIGN_TOKENS.md        ← Colors, spacing, typography
│
└── deployment/
    ├── AGENT.md
    ├── CI_CD_SETUP.md          ← Pipelines, stages, environments
    ├── CHECKLIST.md            ← Pre-deploy checklist
    └── RUNBOOKS.md             ← Backup, restore, incident, rollback
```

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

When a file needs to grow beyond its limit, split before adding.

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
| Celery task | `<verb>_<noun>_task` | `embed_chapter_task` |

---

> Last updated: project initialization
> Maintained by: Architecture Agent
> Changes require a DECISIONS.md entry
