# Narrare — Tech Stack

> **This document defines what we use, why we use it, and what we explicitly do not use.**
> It is the authoritative reference for all technology decisions.
> Changes require an ADR and Architecture Agent approval.
>
> Location: `docs/_shared/TECH_STACK.md`
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

### FastAPI (App Router) — `>=0.135`, see `apps/api/pyproject.toml` for exact pin
**Why:** Best-in-class async Python web framework. Pydantic-native.
OpenAPI generation is free. SSE support is clean.
**Role:** HTTP transport layer only. No business logic in routers.
**Not:** Django, Flask, Starlette directly — FastAPI gives us everything we need.
**Canonical source:** `apps/api/pyproject.toml` (`fastapi` pin). This document
intentionally records only the major-version commitment so the prose does not
drift between releases; check the manifest for the installed version.

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

### Redis — ⛔ Removed (ADR-080)

> **⛔ Removed in ADR-080 (2026-08-07):** Redis is **no longer a dependency** and is
> absent from the runtime path. The former uses — TaskIQ broker, writing-session
> cache (`RedisSessionCache`), and provider model-list cache — were replaced by the
> in-process execution boundary (ADR-080) and a TTL-capable `InMemorySessionCache`
> in `core/cache/` (`packages/core/narrare_core/cache/in_memory.py`). The
> `core/cache/redis_client.py` adapter and the `apps/api/narrare/_app/events.py`
> event bus are deleted. ADR-080 supersedes ADR-007 / ADR-012 and amends ADR-036.
>
> **Re-introduction guard (RULE-08):** if Redis returns for multi-user /
> multi-worker deployment, it must go through `core/cache/` only, via a new ADR
> superseding ADR-080.

**Historical record (pre-ADR-080):** Redis was chosen for fast ephemeral state —
session storage, TaskIQ task broker, and provider model-list cache (24h TTL) — used
only via `core/cache/redis_client.py`. It was preferred over Memcached (no pub/sub, no
sorted sets) and over in-process caching (doesn't survive restarts). The
single-user deployment model (ADR-029) made that operational overhead unjustified;
the in-process trade-off is now accepted (see ADR-080 Durability Trade-off).

### Alembic
**Why:** The only safe way to manage schema migrations. No alternatives considered.
**Rule:** Every schema change has a migration. No `Base.metadata.create_all()` in production.

---

## LLM & AI

### pydantic-ai (v2.x, slim variant)
**Why:** Type-safe LLM agent framework. Native Pydantic integration.
Supports OpenAI, Anthropic, and other providers via a unified interface.
**Role:** The underlying agent runtime inside `core/llm/`. Not used outside it.
**Canonical source:** `packages/core/pyproject.toml` pins
`pydantic-ai-slim[openai,anthropic,google,groq]`. This document records only the
major-version commitment (v2.x) — the slim variant is intentional (we vendor only
the providers we use); check the manifest for the installed patch version.
**Not:** LangChain (too heavy, too much magic), raw SDK calls (no type safety, no retry).
**v2 migration notes:** pydantic-ai v2 changed `result_type` → `output_type` on
`Agent` construction and requires `OpenAIProvider(...)` around `base_url`/`api_key`.
The v1.x `result_type` field is no longer accepted. See the pydantic-ai v2
changelog when upgrading the pin.

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
| z.ai (GLM family) | Cost-efficient primary workhorse | General API and Coding API endpoints supported via wizard endpoint selector. Concrete model ids (e.g. `glm-4-plus`, `glm-4-flash`, `glm-z1-32b`) are registered in `apps/api/narrare/setup/provider_service.py` and `packages/core/narrare_core/llm/_providers/zai.py` — read those for the live model list rather than relying on a version string here. |
| OpenAI-compatible (custom) | Future: self-hosted models | Via provider registry |

**Intent → Model routing** is defined in `core/llm/intents.py`, not hardcoded in services.
Changing the model for an intent requires only one file change.

### mem0 OSS (2.0.x, compatibility-verified)
**Why:** Persistent memory layer for writing preferences, style patterns,
rejection feedback, and session history across conversations.
**Role:** Powers the learning system — user and project-level preference accumulation.
**Canonical source:** `packages/core/pyproject.toml` pins `mem0ai` (2.0.x line).
This document records only the major-version commitment (2.0.x); check the manifest
for the installed patch version.
**Architecture:**
  - Uses `AsyncMemory` with pgvector backend for semantic search over memories
  - LLM provider is configurable — reuses user's settings (stored in `user_ai_settings`)
  - Cost-efficient default model per provider:
    - Anthropic → Claude Haiku (lightweight extraction)
    - OpenAI → GPT-4.1-nano
    - Ollama → Llama3.2
  - Graceful degradation via `NullMemoryClient` — system works without memory
  - **mem0 2.0.x** (ADR-033, verified): hybrid search, entity matching/linking,
    filters-in-search, metadata filtering, and local embedding fallback.
  - Platform-only features (Memory Decay, structured Memory Export) are not core
    product dependencies.
  - Users can override embedding behavior via the approved settings cascade.
**Flow:** Feedback collection (`FeedbackService`) → preference extraction (mem0 AsyncMemory) → prompt injection (`PreferenceService` → `PromptComposer`)
**Location:** Only used via `core/memory/mem0_client.py` (singleton factory, approved RULE-01b exception).
**Not:** mem0 Platform as a core dependency; custom memory service. ADR-033
compatibility gates passed with 2.0.x.
**Note:** Graceful degradation is mandatory. If mem0 is unavailable, the system
continues without memory features. Never a hard dependency at request time.

### Embeddings (OpenAI `text-embedding-3-small`)
**Why:** Fast, cheap, good quality for semantic similarity tasks.
**Role:** KB entry embeddings, chapter summary embeddings, style profile embeddings.
**Location:** Only via `core/llm/embeddings.py` (approved RULE-01b exception).
**Future:** Provider-agnostic embedding interface planned — model swappable via config.

### sentence-transformers `all-MiniLM-L6-v2` (optional)
**Why:** Local embedding fallback for users without OpenAI access (z.ai, Anthropic, Ollama).
**Role:** Powers the embedding cascade for mem0 memory search when no API-based embeddings are available.
**Architecture:** Local fallback remains required under ADR-033; exact tiers are
defined by the compatibility-verified mem0 2.0.x implementation.
See ADR-033 for full rationale.
**Location:** Only via `core/memory/embedding_cascade.py`.
**Not:** A required dependency — optional via `pip install narrare-core[memory]`.

---

## Background Processing

### In-Process Async Tasks (asyncio)
**Why:** Single-user, self-hosted deployment (ADR-029) needs no distributed
queue, no cross-process durability, and no second always-on process. See ADR-080
for the full rationale and the explicit durability trade-off.
**Role:** Slow, idempotent or best-effort operations that must not block writing:
embedding generation (`embed_source`) and band-summary generation
(`generate_band_summary`) for a completed series.
**Dispatch:** Tasks run as `asyncio.create_task` coroutines inside the API
process. Each wrapper builds its own DB session (`get_session_factory()`, never
the request session) and the caller holds a strong reference (GC guard). Retry
schedules are transport-independent (`run_embed_source`: `[30, 120, 300]s`).
**Architecture (INFRA-007, stable):**
- `embed_source` — defined in `embeddings/tasks.py`, dispatched by
  `kb/embedding_hooks.py` on KB source content changes.
- `generate_band_summary` — defined in `series/tasks.py`, dispatched by the
  series auto-trigger when a Series flips to `completed`.
- Wiki summaries (`wiki/tasks.py`) are invoked **directly** (awaited) by
  `wiki/listeners.py`, not as background tasks.
**Location:** Task definitions live in feature-package `*/tasks.py` files
(`embeddings/tasks.py`, `series/tasks.py`); the former shared
`apps/api/narrare/tasks/` package was **deleted** in the ADR-080 cleanup —
nothing imported it, so no stub is retained.
**Trade-off:** In-flight tasks are lost on API restart (idempotent embeddings
regenerate on the next dirty save; band summaries re-trigger manually). No
queue-depth / coverage metrics or dedicated monitoring UI.

> **⛔ Removed in ADR-080 (2026-08-07):** TaskIQ (`taskiq`, `taskiq-redis`,
> `taskiq-fastapi`) and the `redis` datastore are no longer dependencies. The
> `ListQueueBroker` + `RedisAsyncResultBackend` (`tasks/broker.py`), the worker
> process, the `GET /tasks/status` monitoring API, the Redis Pub/Sub event bus
> (ADR-012), and the frontend `BackgroundTasksPanel` were deleted. ADR-080
> supersedes ADR-007 / ADR-012 and amends ADR-036. If multi-user / multi-worker
> deployment returns, re-introduce a broker via a new ADR superseding ADR-080
> (the dispatch site is the single swap seam).

---

## Export Toolchain

> Added by ADR-081 (2026-08-10). Manuscript export is a deterministic, non-LLM
> render pipeline (no ModelRegistry, no PromptComposer, no agent — see the
> non-LLM call-out in ADR-081).

### Typst (pre-1.0, exact-pinned)
**Why:** Chosen PDF engine for manuscript export (ADR-081). Single ~15 MB static
binary; **byte-reproducible** output (decisive for the Golden-Pages CI
acceptance test); correct PDF text layer (ToUnicode). Knuth-Plass-class line
breaking; no glyph expansion (the accepted ~5–10% gap vs LaTeX on compound-heavy
German — user bar = ~95%, "sehr hochwertig"). Pre-1.0 (v0.15.x) → exact version
pin mandatory; Golden-Pages test is the regression net across bumps.
**Role:** PDF rendering via a bespoke `narrare-roman` Typst package (vendored at
`apps/api/narrare/export/typst/`, owned — not a community template fork).
**Location:** Invoked ONLY inside `apps/api/narrare/export/renderers/typst.py`
(RULE-08).
**Canonical source:** `scripts/install_export_toolchain.sh` pins the exact tag
(bake-off-verified floor: v0.15.1; Platform locks the latest stable at IO-001
Slice 0). This document records only the major-version commitment (pre-1.0
v0.15.x); check the script for the installed tag.
**Not:** LaTeX (footprint + non-reproducible), SILE (f-ligature ToUnicode
defect), WeasyPrint / `python-docx` / `ebooklib` (superseded by ADR-081).

### pandoc (exact-pinned)
**Why:** Intermediate converter for all three export formats: HTML → Typst AST
(PDF, with `--to=typst --shift-heading-level-by=-1`), HTML → EPUB3, HTML →
Markdown. Robust fire&forget for the simpler formats.
**Role:** HTML → target AST.
**Location:** Invoked ONLY inside
`apps/api/narrare/export/renderers/pandoc_*.py` (RULE-08).
**Canonical source:** `scripts/install_export_toolchain.sh`.

### EPUBCheck (CI gate, not in release image)
**Why:** The EPUB validation standard. CI gate for the EPUB renderer
(no half-implementations — RULE-20).
**Role:** CI-only validation of rendered EPUBs. Not a runtime dependency.
**Canonical source:** `scripts/install_export_toolchain.sh` (installed only when
`INSTALL_EPUBCHECK=1`, i.e. CI).

### `@preview/droplet` (optional, pinned)
**Why:** Drop-cap support in `narrare-roman`, OFF by default ("die mag nicht jeder").
**Role:** Optional Typst preview package imported by `narrare-roman` only when
`drop_caps: true`.
**Canonical source:** pinned in `apps/api/narrare/export/typst/` (vendored or
version-locked in the wrapper).

### Libertinus Serif (bundled, OFL)
**Why:** Production body font for PDF **and EPUB** export. Bundled for
reproducible output with **NO silent font fallback** in either binary format
(the bake-off's headline fire&forget failure was templates silently falling back
to the wrong font — D7 extends the no-silent-fallback principle to EPUB).
Markdown is plain text and carries no font. EB Garamond was the bake-off
comparison font only.
**Role:** Body font in `narrare-roman` (PDF — compiled in by Typst) **and**
embedded in EPUB via pandoc `--epub-embed-font` (regular/italic/bold/bolditalic
variants) — one bundled font, two embedding mechanisms, one font policy.
**Location:** `apps/api/narrare/export/typst/fonts/` + `LICENSE-OFL.txt`
(recorded at vendoring). Both renderers read from this single directory (D3).
**Not:** EB Garamond (comparison font only); system fonts (silent fallback risk).

---

## Validation & Configuration

### Pydantic `v2`
**Why:** Runtime type validation. Native FastAPI integration. v2 is 5-10x faster than v1.
**Role:** All request/response schemas, internal domain types, configuration.
**Rule:** We use Pydantic v2 API exclusively. No v1 compatibility shims.
**Canonical source:** `packages/core/pyproject.toml` pins `pydantic` (2.x line).
This document records only the major-version commitment (v2); check the manifest
for the installed patch version.
**Not:** attrs, dataclasses alone — we need runtime validation, not just type hints.

### pydantic-settings (2.x)
**Why:** Environment variable loading with Pydantic validation.
**Role:** All application configuration via `Settings` classes.
**Canonical source:** `packages/core/pyproject.toml` pins `pydantic-settings`
(2.x line). This document records only the major-version commitment.
**Not:** dynaconf, python-decouple — pydantic-settings is already in our stack.

---

## Auth & Security

### PyJWT (2.x)
**Why:** Lightweight, well-maintained JWT library.
**Role:** JWT creation and verification in `auth/security.py`.
**Canonical source:** `apps/api/pyproject.toml` pins `PyJWT` (2.x line).

### argon2-cffi (25.x)
**Why:** Password hashing with argon2id — the Password Hashing Competition (PHC) winner.
Stronger against GPU/ASIC attacks than bcrypt. Backward-compatible bcrypt verification
for existing hashes during migration.
**Role:** Password hashing and verification in `auth/security.py`.
**Canonical source:** `apps/api/pyproject.toml` declares `argon2-cffi>=25.1.0`
(25.x line). This document records only the major-version commitment.

### pyrate-limiter (4.x) — async rate limiting, used directly
**Why:** Per-endpoint rate limits for AI-cost-bearing endpoints. We use
`pyrate-limiter` **directly** (not via the abandoned `fastapi-limiter`
wrapper, which is incompatible with current FastAPI versions).
**Role:** Rate-limit dependency for the AI cost surface. Currently in-memory only
(no Redis backend init) — accepted risk AR-05-02 for local-first single-user
deployment. A Redis backend can be enabled when multi-user deployment requires
distributed rate tracking.
**Location:** `apps/api/narrare/_app/rate_limiter_dep.py` (thin async adapter
around `pyrate_limiter`), consumed via `apps/api/narrare/_app/rate_limits.py`.
**Canonical source:** `apps/api/pyproject.toml` declares `pyrate-limiter>=4.0,<5`.
**Not:** `fastapi-limiter` (unmaintained, breaks on FastAPI ≥0.116), `slowapi`
(replaced — async-incompatible).

---

## Observability

### structlog (26.x)
**Why:** Structured logging with consistent context propagation.
**Role:** All logging throughout the codebase. Never `print()`, never stdlib `logging` directly.
**Pattern:** Every log event is a dictionary, not a string.
**Canonical source:** `apps/api/pyproject.toml` and `packages/core/pyproject.toml`
pin `structlog` (26.x line).

### OpenTelemetry (`opentelemetry-*`, 1.39.x SDK line)
**Why:** Vendor-neutral distributed tracing and metrics. Standard instrumentation
for FastAPI, HTTP, and database calls. Exports to any OTLP-compatible backend.
**Role:** Sole trace standard for API requests, DB queries, external calls, and
Pydantic-AI agent/model/tool spans (ADR-031). Optional local backends are OTel
Collector + Grafana/Tempo/Loki/Prometheus.
**Canonical source:** `apps/api/pyproject.toml` pins the four
`opentelemetry-*` artifacts (`api`, `sdk`, `instrumentation-fastapi`,
`exporter-otlp`) on the 1.39.x SDK line with `<1.44.0` upper bounds. This document
records only the major line; check the manifest for the installed patch versions.
**Location:** Setup in `apps/api/narrare/_app/telemetry.py`; shared tracer helpers
in `apps/api/narrare/_app/observability.py`; Pydantic-AI instrumentation helper in
`packages/core/narrare_core/agents/instrumentation.py`. Prompt/completion capture
is controlled by `NARRARE_OTEL_INCLUDE_CONTENT` and defaults to off in production.
No Langfuse/Logfire dependency for core runtime observability.

---

## HTTP & External Services

### httpx (0.28.x)
**Why:** Async HTTP client. Used for external provider calls (research, web search).
**Role:** External HTTP only. Never to LLM provider endpoints (gateway handles that).
**Canonical source:** `packages/core/pyproject.toml` pins `httpx` (0.28.x line).
**Not:** aiohttp — httpx has better typing and a cleaner API.

### aiosmtplib (5.x)
**Why:** Async SMTP. Fits our async-first architecture.
**Role:** Email delivery (auth flows, notifications).
**Location:** Only via `core/notifications/email.py`.
**Canonical source:** `apps/api/pyproject.toml` pins `aiosmtplib` (5.x line).

---

## Frontend

### Node.js `24+`
**Why:** Required runtime for Next.js frontend and all frontend tooling (pnpm, biome, TypeScript).
**Not:** Node 22 or lower — CI tests against 24 only. Older versions are unsupported.
**Canonical source:** This document. All other docs (README, deployment-guide, DevContainer) reference this version.

### pnpm `11.5.2`
**Why:** Deterministic frontend installs across VM-first development, optional
DevContainer bootstrap, and CI.
**Role:** JavaScript package manager for the root workspace and `packages/web/`.
**Canonical source:** `package.json` (`packageManager`). Setup docs should
reference the package metadata instead of repeating the pinned version unless a
version check is the topic.
**Not:** `latest` bootstrap commands — ADR-029 requires pinned package-manager
behavior.

### Next.js `16` (App Router) + TypeScript
**Why:** SSR + SSE support. Strong TypeScript ecosystem. App Router for layouts and streaming.
**Role:** WebUI — the primary client interface.
**Not:** Pages Router — App Router exclusively.

### Zustand
**Why:** Lightweight client state management. No boilerplate.
**Role:** UI state only — sidebar toggles, focus mode, save status. Server state is managed by TanStack Query.
**Not:** Redux (too much ceremony), Jotai (Zustand is sufficient), server data storage.

### TanStack Query `v5`
**Why:** Server state management — fetching, caching, background refetching, invalidation.
**Role:** All server data (chapters, novels, user, settings, KB entries). Server data is NEVER stored in Zustand.
**Pattern:** Components receive server data via props from parent `useQuery` calls or direct `useQuery`.

### Tailwind CSS `v4`
**Why:** Utility-first. Consistent design tokens via CSS variables.
**Role:** **Sole** styling system. All styles use CSS variables from `globals.css` via Tailwind arbitrary values.
**Not:** `styled-jsx` (removed), CSS modules, Emotion, styled-components.

### `motion` (formerly Framer Motion)
**Why:** Declarative animations and transitions with minimal code.
**Role:** Component enter/exit animations, layout transitions, gesture-driven interactions.
**Not:** CSS-only animations for complex sequences — `motion` provides layout animations and `AnimatePresence` that CSS cannot.

### shadcn/ui
**Why:** Copy-paste component primitives built on Radix UI, styled with Tailwind.
**Role:** Base components (Button, Dialog, Dropdown, etc.). Not a runtime dependency — we own the code.
**Not:** Material UI, Chakra (too opinionated, bundle size). Not a package — components live in `components/ui/`.

### react-hook-form + zod
**Why:** Performant form handling with schema-based validation.
**Role:** All form inputs (settings, login, chapter metadata). Zod schemas shared with API validation.
**Pattern:** `zod` schemas define types; `react-hook-form`'s `zodResolver` connects them.

### `jose`
**Why:** Edge-compatible JWT library. Works in Next.js middleware (Web Crypto API only).
**Role:** JWT session validation in middleware. Token refresh logic.
**Not:** `jsonwebtoken` (Node-only, not Edge-compatible).

### HTTP Client
**Why:** Native `fetch` for all HTTP requests and SSE streaming.
**Role:** All API communication via `fetch` + `ReadableStream`. SSE via `connectSSE` utility in `lib/api/streaming.ts`.
**Not:** `axios` (removed — native `fetch` is sufficient and lighter).

### Recharts `~3.8`
**Why:** Composable React charting library built on D3. Declarative, responsive, and well-typed.
**Role:** Analysis visualization — radar charts for multi-dimensional scores (beta reader), line charts for time-series data, bar charts for categorical comparisons. Reusable `AnalysisChart` wrapper component.
**Location:** `packages/web/components/studio/analysis/` (ScoreRadar, future chart components).
**Not:** D3 directly (too low-level for our needs), Chart.js (imperative API, React integration is awkward), Nivo (smaller ecosystem).

---

## Developer Tooling

### just (justfile)
**Why:** Language-agnostic task runner. Replaces Makefile with readable syntax.
**Role:** All dev commands: `just dev`, `just test`, `just check`, `just db-migrate`.

### Ruff
**Why:** Fast Python linter + formatter. Replaces flake8 + isort + black.
**Role:** Code style enforcement in pre-commit and CI.

### pyright
**Why:** Static type checking. Catches entire classes of bugs before runtime.
**Role:** CI gate. All new code must pass pyright strict.

### Bandit
**Why:** Security linting for Python.
**Role:** Detects common security issues. Config in `pyproject.toml`.

### pre-commit
**Why:** Local enforcement before code reaches CI.
**Role:** Runs the full local gate suite — architecture constraints, prompt
structure, adoption score, AI-interaction compliance, exception baseline, file
sizes, prompt-surface contract, streaming compliance, configuration matrix,
locale sync, OpenAPI regeneration, ruff (lint + format), pyright (+ tests),
bandit, biome, testid, i18n, frontend typecheck, conventional commits, plus the
standard `pre-commit-hooks` hygiene set.
**Canonical source:** `.pre-commit-config.yaml` is the SSOT for the exact, current
hook list. This document intentionally does **not** reproduce the hook count,
because it drifts whenever a hook is added or removed — run
`pre-commit run --all-files` (or read the config) for the live set.

### pytest + pytest-asyncio + pytest-cov
**Why:** Standard Python test stack with async support.
**Role:** Unit, integration, and e2e tests. Coverage reports in CI.

### Pydantic Evals
**Why:** Python-native evaluation stack for Pydantic-AI agents, structured outputs,
datasets, cases, evaluators, LLM judges, and span-based evals.
**Role:** Evaluation SSOT for AI runtime quality (ADR-032): KB Extraction, Rewrite
Selection, Preference Analysis, and future suites that run through Narrare agents,
`PromptComposer`, and `ModelRegistry`.
**Not:** promptfoo; Logfire is optional and not required for eval execution.

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
| `axios` | Native `fetch` handles all HTTP + SSE streaming — no extra library needed |
| `styled-jsx` | Tailwind CSS v4 is the sole styling system — no CSS-in-JS |
| `slowapi` | Replaced by `pyrate-limiter` used directly via `_app/rate_limiter_dep.py` (async-native; the earlier `fastapi-limiter` wrapper is unmaintained and breaks on FastAPI ≥0.116, so it is itself not used) |
| `bcrypt` | Replaced by argon2-cffi (PHC winner, stronger against GPU/ASIC) |
| `prometheus-client` | Replaced by OpenTelemetry SDK (vendor-neutral, distributed tracing) as the *application* observability path. A `prometheus-client` pin remains in `packages/core/pyproject.toml` only because a transitive/optional consumer may export Prometheus metrics; it is not a core application dependency and must not be imported for primary observability. See ADR-031. |
| Langfuse | Superseded by OpenTelemetry-only tracing (ADR-031); no core runtime dependency |
| Logfire | Not local-first for core observability; optional external service only, not a product requirement |
| promptfoo | Superseded by Pydantic Evals as eval SSOT (ADR-032) |

---

## Dependency Audit Schedule

Dependencies are audited quarterly for:
- Security vulnerabilities (`pip-audit`)
- Unused packages (removed immediately)
- Major version upgrades (evaluated, not automatic)

---

> Last updated: 2026-07-05 — Drift fix (review-04 AUFG-04-08): replaced hard version pins with major-version commitments + `pyproject.toml`/`package.json` as canonical source (Strategy: no hard numbers in prose); corrected `fastapi-limiter` → `pyrate-limiter` used directly; clarified `prometheus-client` Do-Not-Use rationale; replaced GLM-5.1 prose with pointer to provider registry; pointed pre-commit section at `.pre-commit-config.yaml` as SSOT for the hook list.
> Maintained by: Architecture Agent
> Changes require ADR
