<!-- Context: narrare-dev/domain/architecture-concepts | Priority: high | Source: docs/_shared/CONSTRAINTS.md + docs/_shared/TECH_STACK.md | Updated: 2026-06-12 -->

# Architecture Concepts

Core architectural concepts every specialist must understand. Detailed RULE-XX text is in `constraints/rules.md`.

---

## Layer Architecture

```
packages/core/narrare_core/    ← Domain logic, NO HTTP/auth/users/DB-session
         ↓
apps/api/narrare/              ← Service Layer: FastAPI, auth, DB sessions
         ↓
packages/web/                  ← Frontend: Next.js, user-facing UI
```

**Dependency direction**: core ← apps/api ← packages/web. Core never imports from apps/ or packages/web/.

---

## The 4-Client Model (RULE-12)

Service Layer is the **only public API**. All clients call it — never each other.

```
WebUI  ──┐
MCP    ──┤──→  Service Layer  ──→  core/  ──→  LLM / DB / Cache
A2A    ──┤
CLI    ──┘
```

New client = new adapter. Never modify services to accommodate a specific client.

---

## Key Patterns

### LLM Gateway (RULE-01)

All LLM calls go through `core/llm/gateway.py`. pydantic-ai `Agent` only in `core/agents/`. Model/provider classes only in `core/llm/`. No direct `openai`/`anthropic` imports.

### Prompt System (RULE-02)

Prompts built only in `core/prompts/`. Uses `PromptComposer.build(intent=..., context=...)`. No f-string prompt assembly elsewhere.

### Contract-First (RULE-03)

Every service needs a `Protocol` in `contracts.py` **before** implementation. Enables mocking, testing, client-switching.

### Agent Architecture

- **Runtime**: pydantic-ai Agents in `core/agents/`
- **Model resolution**: `ModelRegistry` in `core/llm/` provides model instances
- **Singletons**: Agents created once, reused across requests (ADR-016)
- **Testing**: `TestModel` / `FunctionModel` for deterministic LLM responses
- **Caching**: Prompt caching via agent singletons + `ModelSettings`

### Prompt Injection Architecture (ADR-026)

Three-mechanism model for prompt content:

| Content Type | Mechanism | Guaranteed? |
|---|---|---|
| Universal rules (fiction guidelines, conflict resolution, injection defense) | `NarrareUniversalRules` Capability | ✅ Always |
| Meta-prompt (identity, role flexibility, guardrails) | `NarrareMeta` Capability | ✅ Always |
| Feature-specific (task, output format, mode) | `PromptComposer` cascade | Per intent |
| Dynamic (KB data, style profiles) | Future: `@agent.instructions` | Per run |

All three default Capabilities (`NarrareObservability`, `NarrareUniversalRules`, `NarrareMeta`)
are injected by `NarrareAgent.__init__` and cannot be forgotten. `with_meta()` has been removed.

---

## Event-Driven Architecture

- **Event bus**: Redis Pub/Sub (ADR-012)
- **Location**: `apps/api/narrare/_app/events.py`
- **Flow**: Domain events → Redis Pub/Sub → TaskIQ workers → background tasks
- **Use cases**: Embedding generation, consistency checks, chapter summarization

---

## Streaming Pattern

| Transport | Use For | Protocol |
|-----------|---------|----------|
| **SSE** | AI responses (generation, sessions) | `text/event-stream` |
| **REST** | CRUD operations | Standard JSON |
| **WebSocket** | Interactive writing sessions | `ws://` |

Streaming and non-streaming share one interface (RULE-13): `stream: bool = False`.

---

## Observability Stack

| Layer | Tool | Location |
|-------|------|----------|
| Structured logging | `structlog` | All modules |
| Distributed tracing | OpenTelemetry | `apps/api/narrare/_app/telemetry.py` |
| Agent/model/tool spans | OpenTelemetry via Pydantic-AI instrumentation | Agent runtime bootstrap (ADR-031) |
| Metrics | Prometheus-compatible export | `/metrics` + OTel metrics where applicable |

---

## Data Layer

| Store | Purpose | Access |
|-------|---------|--------|
| PostgreSQL + pgvector | Primary data + embeddings | `*/repository.py` only |
| Redis | Cache, sessions, task broker, event bus | `core/cache/client.py` only |
| Alembic | Schema migrations | Required for every model change (RULE-14) |

---

## Dependency Injection Flow

```
Router (FastAPI Depends)
  → dependencies.py (get_*_service factory)
    → Service (constructor injection)
      → Repository (constructor injection)
        → AsyncSession (via SessionDep — RULE-19)
      → ModelRegistry (for LLM calls)
      → PromptComposer (for prompt building)
```

Tests inject Fakes through constructors. Never `__new__()` to bypass `__init__`.

---

**Reference**: `docs/_shared/CONSTRAINTS.md`, `docs/_shared/TECH_STACK.md`
**Related**: narrare-dev/constraints/rules · narrare-dev/domain/module-map · narrare-dev/standards/architectural-discipline
