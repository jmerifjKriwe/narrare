# ADR-093 — Core Usage-Event Sink Seam & AI Cost Persistence (STATS-002)

> **Status:** ✅ Implemented (per Gate 12 — implementation complete
> 2026-10-05..06: 18-task SDD on branch `disco-badger`, commits
> `b2aeb9af..c6c6856c` + the docs-closure commit; binding spec
> `docs/superpowers/specs/2026-10-05-stats002-cost-tracking-design.md`, plan
> `docs/superpowers/plans/2026-10-05-stats002-cost-tracking.md`)
> **Amended:** 2026-10-07 — Post-Implementation Amendment: decision 4's dual
> disjoint emission becomes **three disjoint emission surfaces** (embeddings
> provider added — STATS-002 deferred slice D, PO-ratified); see the final
> section
> **Date:** 2026-10-05
> **Deciders:** Architecture Agent (architecture-gate ruling 2026-10-05, findings
> F1–F7); Project Owner (product rulings D1–D4 — those stay recorded in the
> binding spec, not here)
> **Related:** `docs/superpowers/specs/2026-10-05-stats002-cost-tracking-design.md`
> (**binding implementation doc** — schemas, wire shapes, migration, tests),
> ADR-015 (capability architecture), ADR-080 (in-process execution boundary —
> applied), ADR-084 (WS ticket identity), ADR-092 (`create_task` context
> inheritance; decision 6 registry rule), ADR-094 (budget gate — consumes the
> totals this seam produces), `docs/features/analytics/STATS-002-cost-tracking.md`

---

## Context

Every capability-carrying agent run already reports intent, model, provider,
token usage (incl. cache tokens), and duration through the auto-injected
`NarrareObservability` capability
(`packages/core/narrare_core/agents/capabilities/observability.py`) — but that
data terminates in in-memory Prometheus counters
(`narrare_core/llm/metrics.py`). No persisted, user-attributed, priced record
of AI spend exists. STATS-002 v1 adds one: persist a usage record per LLM call
and surface a monthly cost overview.

Three architecture facts shape the decision:

1. **The capability seam alone is insufficient (gate F1).**
   `ModelRegistry.run()`/`stream()` create bare ephemeral agents **without
   capabilities** for nine live production call sites (name generation, KB
   consistency, inline suggest, **interactive WS writing turns** — likely the
   dominant token consumer — interview drafts, legacy `WritingPipeline`
   paths). Capability-only capture would silently miss that population.
2. **Attribution data lives only in the API layer.** Core is HTTP/DB-free
   (RULE-07); user identity arrives via HTTP auth middleware or — on
   WebSocket — via ticket validation *inside* the endpoint (ADR-084), not the
   ASGI scope.
3. **Pricing data drifts.** Rates come from the models.dev cache
   (`llm/cost_rates.py`), so *when* cost is computed determines whether
   history stays truthful.

Product scope (transparency-only, Analytics UI home, etc.) is ruled D1–D4 in
the spec and is not re-decided here.

---

## Decision Drivers

- **Cost capture may never break a product run** — writing/analysis
  correctness never depends on cost telemetry.
- **Exactly-once counting** across *both* agent populations (capability and
  registry-routed); neither double counting nor silent gaps.
- **Core purity** (RULE-07) and one-way module dependencies — `core/llm/` may
   not import from `core/agents/`.
- **ADR-080 boundary** — in-process execution; no queue, no worker, no new
  datastore for telemetry.
- **Attribution must survive** per-request isolation *and* background-job
  inheritance (ADR-092 `create_task` pattern).
- **Registry-count discipline** — ADR-092 decision 6: the fourth
  module-local registry triggers a generalization review.

---

## Options Considered

### Option A — Service-call-site capture (each API service records usage)

Every backend service records a usage row after its agent/registry call.

**Pros:** no Core change.
**Cons:** ~30 call sites to instrument; every new call site can silently
forget; the registry's bare-agent sites have no service-level usage payload
anyway. Rejected — drift by construction.

### Option B — Telemetry-pipeline piggyback (OTel processor / Prometheus-derived records)

Derive persisted cost records from the existing operational telemetry stream.

**Pros:** one pipeline.
**Cons:** couples user-facing persisted data to operational telemetry with a
different consumer, data shape (aggregated counters, no per-call record, no
attribution), and lifecycle (process lifetime vs. DB lifetime — see decision
6). Rejected — wrong lifecycle coupling.

### Option C — Core sink seam with dual disjoint emission (chosen)

A pure-Core `UsageEventSink` Protocol + single-slot module registration +
attribution ContextVars; two disjoint emitters (capability, registry); an
API-registered DB-writing sink. Related alternatives rejected inline in
decisions 5 and 7: read-time pricing, read-side re-pricing, and a queue-based
sink (premature infrastructure against the ADR-080 boundary).

---

## Decision

**We choose Option C**, in seven decisions:

1. **Never-raise sink contract.** `UsageEventSink` (Protocol, RULE-03):
   `async def record(event: UsageEvent) -> None`. Implementations must never
   raise into the caller. As defense-in-depth, both emitters wrap `record()`
   in a catch-all guard — **any** exception ⇒ `logger.warning`, the product
   run continues untouched. Failed model requests are not recorded at all
   (no usage payload; existing metrics cover them).

2. **Single-slot process-local registration — a service locator, not a
   registry.** `set_usage_event_sink(sink)` / `get_usage_event_sink()` as
   module state in `narrare_core/llm/usage_events.py` (the `llm/metrics.py`
   module-state pattern). One unnamed slot — no keying, no owner pinning, no
   TTL sweep, no enumeration — therefore **not** a registry and **explicitly
   outside** ADR-092 decision 6's fourth-registry generalization trigger.
   Unset sink ⇒ no-op (a `None` check; tests, CLI, and Core-only usage pay
   zero overhead). The API registers its sink once at app startup (lifespan).

3. **ContextVar attribution contract — Core defines, API writes.** Core owns
   `usage_user_id` / `usage_novel_id` ContextVars (+ `set_usage_context()`
   helper) in the same module. The API is the only writer: HTTP attribution
   middleware (authenticated `user_id`; `novel_id` from the
   `/novels/{novel_id}/…` path parameter, else `NULL`) and one helper call
   in the WS session bootstrap — identity there arrives via ADR-084 ticket
   validation inside the endpoint, not the ASGI scope. Isolation and
   inheritance both fall out of context-copy-at-task-creation: each request
   gets its own context, and background jobs (ADR-092 `create_task` pattern:
   bulk extraction, band summaries, embedding hooks) inherit the caller's
   attribution for free.

4. **Dual disjoint emission points ⇒ exactly-once.** (a)
   `NarrareObservability.after_model_request` for capability-carrying agents
   — one event **per model request**, the correct per-call granularity for
   streaming/tool loops; (b) `ModelRegistry.run()`/`stream()` at their
   existing `TokenUsage` construction sites (`gateway.py:211`/`:284`) for
   the nine capability-less ephemeral-agent call sites incl. WS writing
   turns. The populations are disjoint, so every LLM call is counted exactly
   once. **Architectural consequence:** the Protocol, event dataclass, and
   ContextVars live in `llm/usage_events.py` — the gateway (in `core/llm/`)
   may not import from `agents/`. One documented untracked exception stays:
   setup provider validation (direct `Agent`, RULE-01b exception #13).

5. **Best-effort durability — an ADR-080 application.** In-process, no
   queue/worker infrastructure in v1: the API sink inserts synchronously
   (guarded, own short-lived session from the app sessionmaker — not the
   request session) at ~1 row per multi-second LLM call. Records lost on a
   crash mid-insert are **accepted** (cost data is non-critical).
   Unattributed events (`user_id is None`) are skipped with a debug log —
   they have no query surface, since every read is user-scoped.

6. **Distinct from the operational `llm/metrics.py` module.** `metrics/` is
   operator-facing Prometheus telemetry (in-memory counters/histograms at
   `/metrics`, process lifetime, intent/model/provider/status labels);
   usage events are end-user-facing persisted cost records (attribution,
   pricing, month aggregation, DB lifetime). Different consumers, data, and
   lifecycle — separate modules, no shared state, never merged.

7. **Write-time strict pricing (gate F3).** `cost_usd` is computed **once at
   capture** via a pure `estimate_cost_usd()`; only exact-model rates price a
   call. Unknown model ⇒ `NULL` — surfaced honestly as `unpriced_calls`,
   never silently priced by a provider-default fallback rate or a blended
   heuristic (`TokenUsage.cost_estimate_usd`'s $3/1M fallback has different
   semantics and must not be reused). Rationale: pricing data drifts with the
   models.dev cache — write-time capture freezes the historically correct
   number; read-time pricing would silently mutate history on every rate
   change; `NULL` keeps the unpriced share visible instead of fabricating
   precision.

---

## Rationale

Root-cause chain (2× why):

1. **Symptom:** AI spending is invisible to the user.
2. **Why?** Usage data already flows through the observability capability but
   terminates in process-local Prometheus counters — no persistence, no
   attribution, no cost.
3. **Why?** No consumer ever needed per-user records; and the capability seam
   structurally misses the registry's bare-agent population (gate F1), so no
   single existing seam can see all calls.
4. **Design:** keep the two existing, proven emission surfaces, add one
   minimal pure-Core seam (Protocol + single slot + ContextVars — no HTTP, no
   DB, no new dependency), and let the API own persistence. Option A is
   simpler but incorrect (drift); Option B couples lifecycles that must stay
   independent; C composes existing seams and is the simplest *correct*
   solution.

---

## Consequences

**Positive:**

- Exactly-once per-call cost accounting, including the WS writing turns that
  dominate token spend.
- Zero risk to product runs (never-raise contract + emitter-side guard).
- Background jobs inherit attribution for free via context copy — no per-job
  plumbing.
- Core stays pure; no new infra; the seam is testable with a stub sink.

**Negative / Trade-offs:**

- Dual emission sites must remain disjoint: a future ephemeral agent that
  gains capabilities would double-count (review trigger below).
- Process-local slot: last-writer-wins; single sink in a single app —
  acceptable by construction.
- Crash loses in-flight records (accepted, decision 5); known-untracked
  spend stays documented: mem0-internal LLM calls (RULE-01b exception #2)
  and setup provider validation (#13).
- Unknown models stay unpriced (visible as `unpriced_calls`, not hidden).

**Constraints touched:** RULE-01b (no LLM client imports — capability and
gateway metadata only), RULE-03 (Protocols first), RULE-04 (plan tasks
≤ 3 files / ≤ 250 new LOC), RULE-05/06/07 (one-way deps; thin router; Core
HTTP/DB-free; `analytics/` module split), RULE-08 (sink delegates inserts to
the repository), RULE-10 (tests per task), RULE-11 (loud degradation —
unpriced badge), RULE-14 (Alembic migration for `usage_records`), RULE-16/17
(TS mirror + i18n at first use), RULE-18b (no new settings surface in v1),
RULE-20/23.

---

## Sustainability Check

1. **Correct in 3 months?** Yes — as long as single-user in-process
   deployment holds (ADR-029/080). Both emission surfaces and the
   module-state pattern are already load-bearing in production.
2. **Hard-to-undo coupling?** None added: the sink slot is a swappable seam;
   if multi-worker deployment ever arrives, a queue-backed sink replaces the
   registration behind the same Protocol.
3. **Simplest correct solution?** Yes (see Rationale) — one new seam, two
   existing emitters, no infrastructure.
4. **Intent clear?** This ADR (architecture decisions) + the binding spec
   (implementation detail, product rulings D1–D4) record the full intent.

---

## Implementation Notes

- **Binding implementation doc:**
  `docs/superpowers/specs/2026-10-05-stats002-cost-tracking-design.md`
  (event/dataclass fields, DB schema + migration, middleware ordering,
  endpoint contract, FE panel, test strategy, deferred slices).
- Module homes: Core `narrare_core/llm/usage_events.py` (new, pure) +
  `model_pricing.py` extension (exact-model vs. default-rate distinction;
  cache-rate extraction); API `apps/api/narrare/analytics/` family
  (`usage_sink.py` delegates inserts to `UsageRecordRepository`, RULE-08).
- `created_at` is set from `event.timestamp`, not DB `now()`, so late sink
  writes cannot drift across month boundaries.
- Middleware ordering: attribution must be added late enough to wrap
  everything downstream (`add_middleware` runs last-added outermost).

**ADR Implementation Completeness Gate (Gate 12):** flip `INDEX.md` to
"✅ Implemented" only when the STATS-002 v1 slices are complete — Core seam,
both emission points, pricing extension, migration, analytics API, FE panel,
docs closure — with no plan task skipped.

---

## Review Triggers

- [ ] A capability-less call site gains capabilities (or a registry-routed
      agent gains `NarrareObservability`) → re-audit emission disjointness;
      double counting means the seam contract changed under us.
- [ ] The sink slot ever needs keyed/multi-sink semantics → it becomes a
      registry and counts toward ADR-092 decision 6's generalization review.
- [ ] Narrare moves to multi-user/multi-worker deployment → revisit the
      in-process slot + synchronous insert (queue-based sink option returns).
- [ ] The unpriced share of calls grows materially (models.dev cache
      staleness) → build a pricing-refresh path; do NOT switch to read-time
      re-pricing (mutates history).
- [ ] Cost data is ever needed at billing-grade accuracy → new ADR for a
      durability upgrade; do not quietly harden this best-effort sink.

---

## Post-Implementation Amendment (2026-10-07) — Third Emission Surface: Embeddings

**Context.** STATS-002 v1 shipped with a named known-untracked call class:
embedding API calls (ADR-080 in-process pipeline on the ADR-020 provider
abstraction). Code inspection closes the design question of *where* capture
must live: the **only** seam that sees token counts is
`OpenAIEmbeddingProvider.embed_texts`
(`narrare_core/llm/embedding_providers.py:176–181`) — the API layer cannot
emit, because the `EmbeddingProvider` Protocol returns only vectors, so
tokens are invisible above the provider. The OpenAI SDK's
`CreateEmbeddingResponse` carries a **required** `usage` object which the
current code discards, and models.dev prices embedding models (input-only
rates; output 0), so the existing pure `estimate_cost_usd` works unmodified
with `tokens_out=0`. Attribution needs no new plumbing: decision 3 already
lists embedding hooks among the `create_task` context-inheritors.

**Decision (amends decision 4).** "Dual disjoint emission points" becomes
**three disjoint emission surfaces**: (c)
`OpenAIEmbeddingProvider.embed_texts` emits one `UsageEvent` **per API batch
response** (the provider batches ≤100 texts per call — per-batch is the
correct per-call granularity), with `intent="embeddings"`, `tokens_out=0`
(embeddings produce no output tokens), cache token counts 0, cost via
`estimate_cost_usd` under decision 7's strict pricing (models.dev embedding
rates; unknown model ⇒ `NULL`/unpriced), duration measured per batch, and
attribution read from the existing `usage_user_id`/`usage_novel_id`
ContextVars. Emission goes through the guarded seam (`emit_usage_event`) —
the never-raise contract (decision 1) is **inherited, not reopened**.
Disjointness holds by construction: the capability and registry surfaces see
agent runs; the provider surface sees raw embedding API calls, which involve
no agent — no overlap is possible.

**Usage-omitted edge.** The OpenAI SDK requires `usage`, but a compatible
gateway may omit it ⇒ **skip emission + debug log**. Skipping silently or
fabricating a zero would be dishonest; raising would violate decision 1.

**Test provider.** `TestEmbeddingProvider` emits nothing — it makes no API
call and incurs no cost (correct by construction).

**Honesty consequence.** A month in which embedding usage went untracked
(usage-omitted edge, or spend that predates this amendment) stays
**excluded from budget math** (ADR-094): untracked spend is never estimated
into budgets — the same principle as decision 7's unpriced-`NULL`. It stays
invisible rather than fabricated.

**Consequences.** `usage_records` gains `intent="embeddings"` rows (the FE
intent map + one i18n label key, en/de/fr; `by_intent` aggregation already
isolates them). The STATS-002 feature file's known-untracked list shrinks in
the same docs slice, which also fixes a path drift: the file names
`narrare_core/embeddings/` as the seam — the actual emitter is
`narrare_core/llm/embedding_providers.py` (`embeddings/` is the store
protocol). Module docstrings claiming "two disjoint points" (e.g.
`usage_events.py`) are updated with the emission change. Remaining
untracked, by decision: mem0-internal LLM calls (RULE-01b exception #2) and
setup provider validation (#13).

**Review trigger added:** a future non-OpenAI embedding provider (local,
Ollama) must decide per implementation whether it emits — a real metered
API ⇒ emit; a deterministic/local provider ⇒ do not (the
`TestEmbeddingProvider` rule).
