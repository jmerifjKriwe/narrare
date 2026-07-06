<!-- Context: narrare-dev/lookup/tech-stack | Priority: critical | Source: docs/_shared/TECH_STACK.md | Updated: 2026-07-06 -->

# Tech Stack Reference

> **This file mirrors `docs/_shared/TECH_STACK.md` (SSOT).** If anything here conflicts with TECH_STACK.md or the manifests, those win. For exact version pins, always read `pyproject.toml` / `package.json` — this file intentionally records only major-version commitments to avoid drift.

> Complete reference: `docs/_shared/TECH_STACK.md`

## Philosophy

Three questions before adding any dependency:
1. Does it solve a problem we actually have **today**?
2. Is it actively maintained with a clear upgrade path?
3. Could we implement the needed subset ourselves in < 200 lines?

## Backend Runtime

| Tech | Version | Role |
|------|---------|------|
| Python | 3.14+ | Minimum runtime |
| FastAPI | >=0.135 | HTTP transport only, no business logic in routers |
| Uvicorn | [standard] | ASGI server with uvloop + httptools |

## Data & Persistence

| Tech | Role | Key Rule |
|------|------|----------|
| PostgreSQL + asyncpg | Primary datastore | Relational: novels→chapters→KB→facts |
| pgvector | Embedding similarity inside Postgres | Only in `core/embeddings/store.py` |
| Redis | 3 uses: TaskIQ broker, session state (TTL), provider cache (24h) | Only via `core/cache/client.py` |
| Alembic | Schema migrations | Every change has a migration. No `create_all()` in prod |

## LLM & AI

| Tech | Role | Constraint |
|------|------|------------|
| pydantic-ai (v2.x, slim variant) | Agent runtime inside `core/llm/` | Not used outside it. Exact pin in `packages/core/pyproject.toml` (`pydantic-ai-slim`) |
| LLM Gateway (`core/llm/gateway.py`) | Policy layer: routing, cost, retry, telemetry | Every LLM call goes through it (RULE-01) |
| mem0 (2.0.x line) | Persistent memory for preferences/style/feedback | Graceful degradation via NullMemoryClient. Exact pin in `packages/core/pyproject.toml` (`mem0ai`) |
| OpenAI embeddings | `text-embedding-3-small` for similarity tasks | Only via `core/llm/embeddings.py` |
| sentence-transformers | Local fallback `all-MiniLM-L6-v2` | Optional, for users without OpenAI |

**Providers:** OpenAI, Anthropic, z.ai (GLM family), OpenAI-compatible (custom). Concrete model ids are registered in `apps/api/narrare/setup/provider_service.py` and `packages/core/narrare_core/llm/_providers/` — read those for the live model list. Intent→Model routing in `core/llm/intents.py`.

**Embedding Cascade** (ADR-017): OpenAI → provider-native (future) → local sentence-transformers → disabled.

## Background Processing

| Tech | Role |
|------|------|
| TaskIQ [redis] >=0.11.0 | Async task queue: batch embedding, summarization, extraction |

## Validation & Config

| Tech | Role |
|------|------|
| Pydantic v2 >=2.12 | All schemas, domain types. v2 API exclusively |
| pydantic-settings >=2.13 | Environment variable loading via Settings classes |

## Auth & Security

| Tech | Role |
|------|------|
| PyJWT >=2.10 | JWT creation/verification |
| argon2-cffi >=23.1.0 | Password hashing (argon2id, PHC winner) |
| pyrate-limiter (4.x) | Async rate limiting for AI-cost-bearing endpoints | Used **directly** via `apps/api/narrare/_app/rate_limiter_dep.py` (thin adapter around `pyrate_limiter`). `fastapi-limiter` is **not** used (unmaintained). Exact pin in `apps/api/pyproject.toml` |

## Observability

| Tech | Role |
|------|------|
| structlog >=25.5 | All logging. Never print(), never stdlib logging directly |
| OpenTelemetry | Sole trace standard for API, DB, HTTP, and Pydantic-AI agent/model/tool spans |
| Prometheus-compatible metrics | Runtime counters/metrics; exported through approved OTel/metrics paths |

## Frontend

| Tech | Role |
|------|------|
| Next.js 16 (App Router) | WebUI primary client. SSR + SSE |
| Zustand | Client state only (sidebar, focus mode) |
| TanStack Query v5 | Server state (chapters, novels, KB). Never in Zustand |
| Tailwind CSS v4 | Sole styling via CSS variables. No CSS-in-JS |
| motion | Declarative animations, AnimatePresence |
| shadcn/ui | Copy-paste Radix primitives, styled with Tailwind |
| react-hook-form + zod | Form handling with schema validation |
| jose | Edge-compatible JWT for middleware |
| fetch + ReadableStream | All HTTP + SSE. No axios |
| Recharts ~3.8 | Analysis visualization (radar, line, bar charts) |

## Dev Tooling

| Tool | Role |
|------|------|
| just | Task runner (`just dev`, `just test`, `just check`) |
| Ruff | Linter + formatter (replaces flake8 + isort + black) |
| pyright | Strict type checking, CI gate |
| Bandit | Security linting |
| pre-commit | Architecture/lint/type/security + frontend checks. See `.pre-commit-config.yaml` for the authoritative hook list. Run `pre-commit run --all-files` for the current set |
| pytest + pytest-asyncio | Unit + integration + e2e tests |

## Explicitly NOT Used

| Technology | Reason |
|-----------|--------|
| LangChain | Too heavy, too much magic, version churn |
| SQLModel | Conflates ORM + Pydantic schemas |
| Direct SDK imports outside gateway | Bypasses policy layer |
| `requests` (sync) | Async-first |
| `print()` | Use structlog |
| `Any` | Defeats type safety |
| In-memory SQLite tests | Use real Postgres via Docker |
| Separate vector DB (Pinecone etc.) | pgvector sufficient |
| axios | Native fetch handles all HTTP + SSE |
| styled-jsx | Tailwind v4 is sole styling |
| slowapi | Replaced by pyrate-limiter (used directly) |
| fastapi-limiter | Not used (unmaintained, breaks on FastAPI ≥0.116); pyrate-limiter is used directly via `_app/rate_limiter_dep.py` |
| bcrypt | Replaced by argon2-cffi |
| prometheus-client | Replaced by OpenTelemetry SDK |

**Related**: `narrare-dev/lookup/justfile-commands`, `narrare-dev/guides/deployment`
