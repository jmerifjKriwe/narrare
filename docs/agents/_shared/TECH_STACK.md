# Narrare — Tech Stack

> **This document defines what we use, why we use it, and what we explicitly do not use.**
> It is the authoritative reference for all technology decisions.
> Changes require an ADR and Architecture Agent approval.
>
> Location: `docs/agents/_shared/TECH_STACK.md`
> Maintained by: Architecture Agent

---

## Philosophy

We choose boring technology where possible and interesting technology only where
it creates genuine value. Every dependency is a maintenance burden, a security
surface, and a cognitive load for every developer. We add dependencies deliberately
and remove them aggressively.

**Three questions before adding any dependency:**
1. Does it solve a problem we actually have today?
2. Is it actively maintained with a clear upgrade path?
3. Could we implement the needed subset ourselves in < 200 lines?

---

## Backend Runtime

### Python `3.14+`
**Why:** Latest stable release with latest typing improvements and stdlib enhancements.
We use `3.14` as minimum.
**Not:** `3.13` or lower — we depend on 3.14 features.

### FastAPI `>=0.135`
**Why:** Best-in-class async Python web framework. Pydantic-native.
OpenAPI generation is free. SSE support is clean.
**Role:** HTTP transport layer only. No business logic in routers.
**Not:** Django, Flask, Starlette directly — FastAPI gives us everything we need.

### Uvicorn `[standard]`
**Why:** ASGI server. The `[standard]` extra gives us uvloop + httptools.
**Role:** Production runtime. Not imported directly in application code.

---

## Data & Persistence

### PostgreSQL (via SQLAlchemy `2.0` async + asyncpg)
**Why:** Our data is relational (novels → chapters → KB entries → facts).
We need transactions. We need pgvector. Postgres does both well.
**Role:** Primary datastore for all persistent application state.
**Pattern:** Repository pattern only. No raw SQLAlchemy in services.
**Migration:** Alembic. No manual schema changes ever.
**Not:** SQLite (no pgvector, no production-grade async), MongoDB (our data is relational).

### pgvector
**Why:** Embedding similarity search inside Postgres. No separate vector DB to operate.
**Role:** Stores and queries embeddings for KB entries, chapters, style profiles.
**Location:** Only used in `core/embeddings/store.py`.
**Not:** Pinecone, Weaviate, Qdrant — operational complexity not justified at our scale.

### Redis
**Why:** Fast ephemeral state. Session storage, task broker, provider model cache.
**Role:** Three distinct uses:
  - TaskIQ broker for background tasks
  - Writing session state (TTL-based)
  - Provider model list cache (24h TTL)
**Location:** Only used via `core/cache/client.py`.
**Not:** Memcached (no pub/sub, no sorted sets), in-process cache (doesn't survive restarts).

### Alembic
**Why:** The only safe way to manage schema migrations. No alternatives considered.
**Rule:** Every schema change has a migration. No `Base.metadata.create_all()` in production.

---

## LLM & AI

### pydantic-ai `>=1.84`
**Why:** Type-safe LLM agent framework. Native Pydantic integration.
Supports OpenAI, Anthropic, and other providers via a unified interface.
**Role:** The underlying agent runtime inside `core/llm/`. Not used outside it.
**Not:** LangChain (too heavy, too much magic), raw SDK calls (no type safety, no retry).

### LLM Gateway (`core/llm/gateway.py`) — our own abstraction
**Why:** pydantic-ai is the runtime, but the gateway is our policy layer.
It enforces intent-based routing, cost tracking, retry, and telemetry uniformly.
**Rule:** Every LLM call in the entire codebase goes through the gateway.
No exceptions without a documented ADR and inline `# narrare: allow-direct-llm` comment.

### Supported LLM Providers
| Provider | Use case | Notes |
|----------|----------|-------|
| OpenAI (GPT-4o, o3) | High-quality generation, complex analysis | Higher cost |
| Anthropic (Claude Sonnet/Haiku) | Long-context, instruction following | Good cost/quality |
| GLM-5.1 (z.ai) | Cost-efficient primary workhorse | Local/private via z.ai |
| OpenAI-compatible (custom) | Future: self-hosted models | Via provider registry |

**Intent → Model routing** is defined in `core/llm/intents.py`, not hardcoded in services.
Changing the model for an intent requires only one file change.

### mem0 `>=1.0`
**Why:** Persistent memory layer for writing preferences, style patterns,
rejection feedback, and session history across conversations.
**Role:** Powers the learning system — user and project-level preference accumulation.
**Location:** Only used via `core/memory/client.py` (singleton factory).
**Not:** Custom memory service — mem0 with pgvector backend gives us semantic search
over memories for free.
**Note:** Graceful degradation is mandatory. If mem0 is unavailable, the system
continues without memory features. Never a hard dependency at request time.

### Embeddings (OpenAI `text-embedding-3-small`)
**Why:** Fast, cheap, good quality for semantic similarity tasks.
**Role:** KB entry embeddings, chapter summary embeddings, style profile embeddings.
**Location:** Only via `core/llm/embeddings.py` (approved RULE-01 exception).
**Future:** Provider-agnostic embedding interface planned — model swappable via config.

---

## Background Processing

### TaskIQ `[redis]` `>=0.11.0`
**Why:** Async-native task queue with FastAPI DI integration via TaskiqDepends.
Redis broker is already in our stack. See ADR-007 for full rationale.
**Role:** Long-running tasks: batch embedding, consistency checks, chapter summarization,
fact extraction, timeline analysis.
**Location:** Task definitions in `*/tasks.py`. Broker in `core/tasks/broker.py`.
**Not:** Celery (async impedance mismatch, needs asyncio.run wrapper), arq (maintenance-only),
asyncio background tasks (no persistence, no retry, no visibility).

---

## Validation & Configuration

### Pydantic `v2 >=2.12`
**Why:** Runtime type validation. Native FastAPI integration. v2 is 5-10x faster than v1.
**Role:** All request/response schemas, internal domain types, configuration.
**Rule:** We use Pydantic v2 API exclusively. No v1 compatibility shims.
**Not:** attrs, dataclasses alone — we need runtime validation, not just type hints.

### pydantic-settings `>=2.13`
**Why:** Environment variable loading with Pydantic validation.
**Role:** All application configuration via `Settings` classes.
**Not:** dynaconf, python-decouple — pydantic-settings is already in our stack.

---

## Auth & Security

### PyJWT `>=2.10`
**Why:** Lightweight, well-maintained JWT library.
**Role:** JWT creation and verification in `auth/security.py`.

### bcrypt `>=4.0`
**Why:** Secure password hashing. Current recommendation.
**Future consideration:** argon2-cffi for new deployments (stronger against GPU attacks).

### slowapi `>=0.1.9`
**Why:** Rate limiting middleware for FastAPI. Minimal overhead.
**Role:** Per-endpoint and per-user rate limits.

---

## Observability

### structlog `>=25.5`
**Why:** Structured logging with consistent context propagation.
**Role:** All logging throughout the codebase. Never `print()`, never stdlib `logging` directly.
**Pattern:** Every log event is a dictionary, not a string.

### prometheus-client `>=0.21`
**Why:** Standard metrics format. Scraping endpoint at `/metrics`.
**Role:** LLM cost metrics, request latency, task queue depth, error rates.
**Future:** OpenTelemetry migration planned when we need distributed tracing.

---

## HTTP & External Services

### httpx `>=0.28`
**Why:** Async HTTP client. Used for external provider calls (research, web search).
**Role:** External HTTP only. Never to LLM provider endpoints (gateway handles that).
**Not:** aiohttp — httpx has better typing and a cleaner API.

### aiosmtplib `>=4.0`
**Why:** Async SMTP. Fits our async-first architecture.
**Role:** Email delivery (auth flows, notifications).
**Location:** Only via `core/notifications/email.py`.

---

## Frontend

### Next.js (App Router) + TypeScript
**Why:** SSR + SSE support. Strong TypeScript ecosystem.
**Role:** WebUI — the primary client interface.

### Zustand
**Why:** Lightweight client state management. No boilerplate.
**Role:** UI state (settings, session state, editor preferences).

### Tailwind CSS
**Why:** Utility-first. Consistent design tokens via CSS variables.
**Role:** All styling. Design tokens defined in `globals.css`.

---

## Developer Tooling

### just (justfile)
**Why:** Language-agnostic task runner. Replaces Makefile with readable syntax.
**Role:** All dev commands: `just dev`, `just test`, `just check`, `just migrate`.

### Ruff
**Why:** Fast Python linter + formatter. Replaces flake8 + isort + black.
**Role:** Code style enforcement in pre-commit and CI.

### mypy `--strict`
**Why:** Static type checking. Catches entire classes of bugs before runtime.
**Role:** CI gate. All new code must pass mypy strict.

### Bandit
**Why:** Security linting for Python.
**Role:** Detects common security issues. Config in `pyproject.toml`.

### pre-commit
**Why:** Local enforcement before code reaches CI.
**Role:** Runs: `check_architecture.py`, ruff, mypy, bandit, test subset.

### pytest + pytest-asyncio + pytest-cov
**Why:** Standard Python test stack with async support.
**Role:** Unit, integration, and e2e tests. Coverage reports in CI.

---

## What We Explicitly Do Not Use

| Technology | Reason |
|-----------|--------|
| LangChain | Too much magic, too many abstractions we don't need, version churn |
| SQLModel | Conflates ORM models with Pydantic schemas — causes confusion at boundaries |
| Direct `openai` / `anthropic` SDK outside gateway | Bypasses policy layer |
| `requests` (sync HTTP) | We are async-first |
| `print()` for logging | Use structlog |
| `Any` type annotations | Defeats type safety; approved exceptions only |
| In-memory SQLite for integration tests | Use real Postgres via Docker |
| Separate vector database (Pinecone etc.) | pgvector is sufficient and simpler |
| watchdog | Was in dependencies, purpose unclear, removed |
| node_semver | Was in dependencies, purpose unclear, removed |

---

## Dependency Audit Schedule

Dependencies are audited quarterly for:
- Security vulnerabilities (`pip-audit`)
- Unused packages (removed immediately)
- Major version upgrades (evaluated, not automatic)

---

> Last updated: project initialization
> Maintained by: Architecture Agent
> Changes require ADR
