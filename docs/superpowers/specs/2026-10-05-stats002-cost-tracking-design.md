# STATS-002 v1 — AI Cost Tracking (Transparency) — Design

- **Date:** 2026-10-05
- **Status:** PO-approved in brainstorming session (all four design rulings below);
  amended 2026-10-05 after the architecture gate (findings F1–F7 folded in)
- **Feature file:** `docs/features/analytics/STATS-002-cost-tracking.md` (status stays
  `planned` until the deferred slices land; this spec covers v1)
- **Related:** ADR-015 (capability architecture), ADR-080 (in-process infra pattern),
  ADR-092 (`asyncio.create_task` background pattern — context-inheritance reference),
  `docs/reference/model-data.md` (models.dev pricing cache)

---

## 1. Context & Goal

Every Narrare agent run already passes the auto-injected `NarrareObservability`
capability (`packages/core/narrare_core/agents/capabilities/observability.py`),
which sees intent / model / provider / token usage / cache tokens / duration for
every LLM call — but today it only feeds in-memory metrics (`narrare_core/llm/metrics.py`).
Pricing lookup already exists (`narrare_core/llm/cost_rates.py`, models.dev cache,
`get_rates(provider, model_id)`).

v1 makes AI spending **visible**: persist one usage record per LLM call, compute the
cost at write time, and surface a monthly cost overview in a new Analytics panel.

**Seam reality (gate F1):** the capability seam alone is NOT sufficient —
`ModelRegistry.run()`/`stream()` create bare ephemeral agents **without capabilities**
for nine live production call sites (name generation, KB consistency, inline suggest,
**interactive WS writing turns** — likely the dominant token consumer — interview
drafts, and the legacy `WritingPipeline` paths). v1 therefore emits at **two disjoint
points**: the `NarrareObservability` capability (capability-carrying agents) and
inside `ModelRegistry.run()`/`stream()` at the existing `TokenUsage` construction
sites. The populations are disjoint — no double counting. One direct-Agent exception
path (setup provider validation, RULE-01b exception #13) stays untracked, documented.

**Goal:** a user can answer "what did AI cost me this month, on which features and
models?" — nothing more in v1.

## 2. Scope — PO Rulings (2026-10-05)

| # | Decision | Ruling |
|---|----------|--------|
| D1 | v1 scope | **Transparency only.** Persistent usage records + aggregation API + Analytics panel (month overview, breakdown by feature/model, 6-month trend). No budgets, no suspension, no export, no CLI. |
| D2 | Capture seam | **Core emitter + API sink.** Protocol sink in Core with **two disjoint emission points** (observability capability + registry gateway, gate F1); the API registers a DB-writing sink at startup. Attribution (user/novel) via Core-defined ContextVars set by API middleware (HTTP) and WS session bootstrap. |
| D3 | Cost timing | **Write-time.** `cost_usd` is computed once at capture and stored. Unknown models store `NULL` and are counted as `unpriced`. No read-time re-pricing. |
| D4 | UI home | **New Analytics nav element** (`/analytics`, tabs; "AI Costs" is the first tab). STATS-001 will join the same panel later. |

## 3. Architecture

### 3.1 Core — `narrare_core/llm/usage_events.py` (new, pure, DB-free)

- `UsageEvent` (frozen dataclass): `timestamp: datetime` (UTC), `intent: str`,
  `provider: str`, `model_id: str`, `tokens_in: int`, `tokens_out: int`,
  `cache_read_tokens: int`, `cache_creation_tokens: int`, `duration_seconds: float`,
  `cost_usd: float | None`, `user_id: UUID | None`, `novel_id: UUID | None`.
  (The DB row stores `duration_ms`; the sink converts — see §3.3.)
- `UsageEventSink` **Protocol** (RULE-03): `async def record(self, event: UsageEvent) -> None`.
  Contract: implementations must never raise into the caller; failures are logged
  and swallowed by the emitter side as defense-in-depth.
- Module-level sink slot `set_usage_event_sink(sink) / get_usage_event_sink()`
  (same pattern as `llm/metrics.py` module state). Unset sink ⇒ no-op.
- Attribution ContextVars in the same module: `usage_user_id: ContextVar[UUID | None]`,
  `usage_novel_id: ContextVar[UUID | None]` (+ `set_usage_context(...)` helper).
- `estimate_cost_usd(provider: str, model_id: str, tokens_in: int, tokens_out: int,
  cache_read: int, cache_creation: int) -> float | None` — pure function over the
  pricing layer with **strict pricing** (gate F3): only exact-model rates price a
  call; a provider-default fallback rate must NOT silently price an unknown model
  (→ `None` = unpriced). Requires a small `llm/model_pricing.py` extension:
  (a) distinguish exact-model rates from the `DEFAULT_RATES[provider]` fallback,
  (b) surface models.dev `cost.cache_read` / `cost.cache_write` in rate extraction.
  Do NOT reuse `TokenUsage.cost_estimate_usd`'s blended $3/1M fallback (different
  semantics).

### 3.2 Core — `NarrareObservability` extension

`after_model_request` builds a `UsageEvent` (tokens from `ctx.usage` incl. cache
details — same extraction as today; provider/model/intent from run state;
attribution from the ContextVars; cost via `estimate_cost_usd`) and awaits
`get_usage_event_sink().record(event)` inside a catch-all guard
(`asyncio.BlockingIOError`-style: **any** exception ⇒ `logger.warning`, run continues).
The hook fires **per model request**: an agent run with multiple model round-trips
(streaming, tool loops) emits one event per request — that is the correct
per-call accounting granularity.
Failures (`on_model_request_error`) are **not** recorded — they have no usage payload;
existing metrics already cover them.

**Intent & attribution source (amended 2026-10-05 after the Task 3 review):** the
capability learns its intent from **agent-class identity** (snake_case slug of the
class name, `ClassVar`-overridable on `NarrareAgent`) carried on the capability
template — not from run state; the existing metrics `record_*` labels switch to the
same source by construction. Capability-path intent vocabulary is agent-class slugs
(`chapter_summary`), registry-path vocabulary is `LLMIntent` values — disjoint
populations, both stable keys; the FE intent→label map covers both. Provider/model
attribution on the capability path rides the `model` object passed to
`NarrareAgent.__init__` (deps-based `model_config` extraction stays preferred where
present). Plan tasks 3b/3c implement both.

### 3.2b Core — `ModelRegistry` emission (gate F1)

`ModelRegistry.run()` and `ModelRegistry.stream()` emit the same `UsageEvent` at
their existing `TokenUsage` construction sites (`gateway.py` ~211–217 / ~284–290),
inside the same catch-all guard. The capability population (capability-carrying
agents) and the registry population (bare ephemeral agents) are disjoint, so every
LLM call is counted exactly once. The `llm/usage_events.py` placement is required
by this: `gateway.py` (in `core/llm/`) imports the sink — `llm/` must never import
from `agents/`.

### 3.3 API — `apps/api/narrare/analytics/` (new module family)

Files (RULE-06 one-responsibility split):
`contracts.py` (`CostQueryServiceProtocol`) · `models.py` (`UsageRecordRow`) ·
`repository.py` · `service.py` · `router.py` · `dependencies.py` · `usage_sink.py` ·
`middleware.py` (attribution middleware — domain-owned, registered in `main.py`;
note `add_middleware` ordering: last added runs outermost, so attribution must be
added late enough to wrap everything downstream).

- `usage_sink.py` — `SqlUsageEventSink`: builds/validates the row (converting
  `duration_seconds` → `duration_ms`) and **delegates the insert to
  `UsageRecordRepository`** (RULE-08 — no direct SQLAlchemy outside `repository.py`),
  running in its **own** short-lived session per record (the app sessionmaker, not
  the request session). Events with `user_id is None` are **skipped with a debug
  log** (gate F2 — unattributed rows have no query surface; every read is
  user-scoped). Best-effort: catches everything, logs. No queue/worker infra in v1
  (volume is one row per multi-second LLM call; local PG insert ≈ 1 ms).
- **Attribution — HTTP** (`analytics/middleware.py`, pure ASGI middleware for the
  `http` scope): `user_id` from the authenticated request; `novel_id` from the path
  parameter on routes matching `/novels/{novel_id}/...`; absent for non-novel
  routes ⇒ `NULL`.
- **Attribution — WS** (gate F4): user identity arrives via ticket validation
  *inside* the endpoint (ADR-084), not the ASGI scope — so the WS session bootstrap
  (`WritingSessionContext` construction, `ws_handler.py` ~113–119) makes one helper
  call setting the same Core ContextVars (the one deliberate per-service touch
  point). Background jobs (ADR-092 pattern) inherit the caller's context via
  `asyncio.create_task` context copy — attribution carries over correctly.
  Race-safety: the middleware sets vars before `await self.app(...)`; per-request
  isolation is guaranteed by context-copy-at-task-creation (structlog-contextvars
  middleware precedent at `_app/middleware.py` ~164).
- Wiring: `set_usage_event_sink(SqlUsageEventSink(...))` once at app startup
  (lifespan), after DB engine/sessionmaker construction.

### 3.4 Database — Alembic migration (RULE-14)

Table `usage_records`:

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `user_id` | UUID FK → users `ON DELETE RESTRICT`, NOT NULL | owning user |
| `novel_id` | UUID FK → novels, NULL | `ON DELETE SET NULL` (cost history outlives novel deletion) |
| `intent` | TEXT NOT NULL | LLM intent / feature key |
| `provider` | TEXT NOT NULL | |
| `model_id` | TEXT NOT NULL | |
| `tokens_in` / `tokens_out` | INTEGER NOT NULL | |
| `cache_read_tokens` / `cache_creation_tokens` | INTEGER NOT NULL DEFAULT 0 | |
| `duration_ms` | INTEGER NOT NULL | |
| `cost_usd` | NUMERIC(12, 6) NULL | `NULL` = unpriced |
| `created_at` | TIMESTAMPTZ NOT NULL | UTC; set from `event.timestamp` (not DB `now()`) so late sink writes cannot drift months |

Indices: `(user_id, created_at)`, `(novel_id)`.

## 4. API Surface

Single endpoint, one round trip:

```
GET /api/v1/analytics/costs?month=YYYY-MM        (auth required)
```

- `month` optional, default = current calendar month (server local timezone —
  documented simplification); invalid format ⇒ 422.
- Response:
```json
{
  "month": "2026-10",
  "totals": { "calls": 42, "tokens_in": 123456, "tokens_out": 7890,
              "cost_usd": 1.2345, "unpriced_calls": 3 },
  "by_intent":  [ { "intent": "draft", "calls": 10, "cost_usd": 0.61, "unpriced_calls": 0 }, ... ],
  "by_model":   [ { "provider": "zai", "model_id": "glm-5.3", "calls": 30, "cost_usd": 1.10, "unpriced_calls": 0 }, ... ],
  "trend": [ { "month": "2026-05", "cost_usd": 0.9 }, ... ]
}
```
  `trend` = the 6 months ending with the requested month (inclusive). All figures
  are scoped to the authenticated user. Router delegates immediately (RULE-06).

## 5. Frontend — `/analytics` (new)

- New sidebar nav entry "Analytics" → `/analytics` page with a tab bar; v1 ships
  one tab **"AI Costs"** (`AnalyticsCostsPanel`).
- Panel: month selector (prev/next + label), totals card (calls, tokens in/out,
  estimated cost, unpriced-calls badge when > 0), two breakdown tables
  (by feature — intent keys mapped to i18n labels — and by provider/model),
  6-month trend rendered with **Recharts** (`recharts` ^3.10.1 is already a
  dependency; in-repo bar-chart precedent:
  `components/studio/analysis/SentimentChart.tsx` —
  `BarChart`/`Bar`/`ResponsiveContainer`/`Tooltip`). No new dependency.
- TanStack Query hook (`useAnalyticsCosts`), `analytics.*` i18n namespace
  (en/de/fr), follows existing panel/page conventions.

## 6. Error Handling & Durability

- Sink unset (tests, CLI, Core-only usage) ⇒ no-op, zero overhead beyond a None check.
- Sink DB failure ⇒ logged, swallowed; the product run (writing/analysis) is never affected.
- Records lost on crash mid-insert ⇒ accepted (cost data is non-critical); documented.
- Unknown model pricing ⇒ `cost_usd = NULL` (strict pricing, gate F3), surfaced
  honestly as `unpriced_calls`.
- **Known-untracked spend** (documented honesty): mem0's internal LLM calls
  (`core/memory/mem0_client.py`, RULE-01b exception #2) and setup provider
  validation (exception #13, direct Agent) are not captured in v1.
- Timezone: month bucketing uses **UTC calendar months** — session-tz
  independent; the repository aggregates with `AT TIME ZONE 'UTC'`, pinned by a
  Berlin regression test (corrected 2026-10-06; supersedes the earlier
  "server-local month boundaries" simplification). The **default** month (no
  `month` param) resolves to the current server-local month.

## 7. Testing Strategy

- **Core:** `estimate_cost_usd` (known model incl. cache rates / unknown ⇒ None /
  partial rates); `UsageEvent` emission via capability with `TestModel` + sink stub
  (assert full field set incl. cache tokens); ContextVar attribution set/unset;
  sink-exception swallow (run still succeeds).
- **API:** repository aggregation (month boundaries, by_intent/by_model, trend span);
  router tests (401 unauthenticated, 422 invalid month, default month);
  middleware attribution (novel route vs non-novel route vs WS);
  `SqlUsageEventSink` failure-swallow + own-session behavior.
- **Frontend:** hook + panel tests (msw), month navigation, unpriced badge,
  i18n key completeness (en/de/fr).
- Migration round-trip per project standard.

## 8. RULE Compliance

- **RULE-01b** — no LLM client imports; capability/metadata only. ✔
- **RULE-03** — `UsageEventSink` + `CostQueryServiceProtocol` contracts first. ✔
- **RULE-06** — router delegates; contracts/models/repository/service/sink split. ✔
- **RULE-14** — Alembic migration for `usage_records`. ✔
- **RULE-18b** — no new settings surface in v1 (month is a query param, validated). ✔
- Core stays HTTP/DB-free (Protocol + dataclass + ContextVars only). ✔
- Package sizing: implementation MUST be sliced into plan tasks of
  ≤ 3 files / ≤ 250 new LOC each (see plan, next step).

## 9. Out of Scope (deferred slices, documented)

Budgets & suspension · CSV/PDF export · CLI · embeddings cost (different seam,
`narrare_core/embeddings/`) · read-time re-pricing · per-series attribution ·
tracking of mem0-internal and setup-validation LLM calls ·
STATS-001 Writing Statistics (second cycle in the same Analytics panel).

## 10. Implementation Notes (gate outcome, 2026-10-05)

1. ~~Legacy gateway check~~ — resolved by gate finding F1: nine live
   capability-less call sites confirmed; registry emission is v1 scope (§3.2b),
   not a conditional rider.
2. ~~Chart component check~~ — resolved: Recharts is already a dependency
   (`packages/web/package.json` ~65); the trend uses it (§5).
3. **ADR-093 required** (gate ruling): a dedicated compact ADR — "Core Usage-Event
   Sink Seam & AI Cost Persistence", ADR-092-sized, referencing this spec as the
   binding implementation doc. Authored by the Architecture specialist before
   implementation starts. It records: the never-raise sink contract; single-slot
   process-local registration (a service locator, not a registry — outside
   ADR-092 decision 6's fourth-registry trigger); the ContextVar attribution
   contract; the dual disjoint emission points; best-effort durability as an
   ADR-080 application; and the distinction from the operational `metrics/` module
   (Prometheus telemetry — different consumers, data, lifecycle).
4. Docs follow-up (not a blocker): update the STATS-002 feature file frontmatter
   paths and its Settings-home/budget/CLI promises to match this design.
