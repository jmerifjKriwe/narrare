---
id: STATS-002
title: "AI Cost Tracking"
status: stable
area: analytics
mvp: false

ui_tooltip: "See what your AI usage costs each month, broken down by feature and model."
ui_help_short: |
  See your monthly AI spending: calls, tokens, and estimated cost by feature
  and model, with an optional monthly budget.
ui_help_long: |
  ## AI Cost Tracking

  Every AI call Narrare makes is recorded with its token usage and an
  estimated cost, so you can answer "what did AI cost me this month, and on
  what?" Open **Analytics** in the studio sidebar and check the **AI Costs**
  tab: pick a month, see totals (calls, tokens in/out, estimated cost), a
  breakdown by feature and by provider/model, and a 6-month trend; a button
  downloads the selected month as a CSV file.

  Set an optional monthly budget in **Settings → AI**: by default Narrare
  shows a warning badge on the costs panel once your spend crosses the
  budget; if you opt in to **Block** mode, further AI calls are stopped with
  a clear banner until you raise or remove the budget.

  **Honest boundaries:** cost figures are estimates from per-model pricing
  data (models.dev). Models without a known price are counted separately as
  "unpriced" instead of being silently guessed. A few internal paths are not
  counted yet (memory-layer calls, setup provider validation), and a stream
  you abandon mid-generation is only counted up to its last completed
  request.
ui_available_in: [analytics, settings]

service: analytics/service.py
contract: analytics/contracts.py#CostQueryServiceProtocol
router: analytics/router.py
prompt: ~
requires: [INFRA-001]
---

# STATS-002 — AI Cost Tracking

> **Status:** ✅ Stable — v1 (transparency) implemented 2026-10-06
> (commits `b2aeb9af..a4f2c2ba`) per
> [ADR-093](../../architecture/decisions/ADR-093-usage-event-sink-cost-persistence.md);
> budgets slice implemented 2026-10-07 (commits `c276a933..3733871c`) per
> [ADR-094](../../architecture/decisions/ADR-094-budget-gate-ai-spend-suspension.md)
> — the last major deferred code slice; status → stable 2026-10-07.
> Design: [cost-tracking spec](../../superpowers/specs/2026-10-05-stats002-cost-tracking-design.md)
> + [budgets addendum](../../superpowers/specs/2026-10-07-stats002-budgets-design.md).

## What it does

A monthly AI cost overview: one persisted usage record per billable LLM call
(tokens, duration, estimated cost), an aggregation endpoint, a month-scoped
CSV export, and an **Analytics** panel (`/analytics`, **AI Costs** tab) with
month totals, breakdowns by feature and provider/model, a 6-month trend, and
a CSV download button. An optional user-level monthly USD budget warns via a
badge by default; opting in to block mode stops AI calls once the budget is
reached, with a clear banner.

## Why it exists

AI costs add up quietly. Writers using AI assistance need visibility: Which
features cost the most? Which models are cost-effective? Am I trending
higher than last month? v1 answers those questions with honest numbers —
including an explicit count of unpriced calls instead of silent guesses.

## How it works (User perspective)

1. Use Narrare normally — every billable LLM call is recorded automatically.
2. Open **Analytics** (studio sidebar) → **AI Costs** tab.
3. Pick a month (prev/next): you see totals (calls, tokens in/out,
   estimated cost, unpriced badge), a **by feature** table, a **by
   provider/model** table, and a 6-month trend chart.
4. Feature names come from i18n labels; a few internal intents without a
   label yet (e.g. `wiki_generation`, `wiki_chapter`, `interview_question`)
   show their raw slug by design until labeled.
5. Budget (optional): set a monthly USD budget in **Settings → AI**. In the
   default **Warn** mode a badge on the totals card flags when spend crosses
   it; in **Block** mode further AI calls stop with a dismissible banner on
   the costs panel (it re-arms if the budget is hit again after being
   raised or removed).

## How it works (Technical)

**Entry point:** `analytics/router.py` → `GET /api/v1/analytics/costs?month=YYYY-MM`
(auth required; `month` optional, default = server-local current month;
invalid ⇒ 422 via app-registered `InvalidMonthError` handler). Router
delegates immediately (RULE-06).

**Service:** `analytics/service.py` (`CostQueryService`), contract
`CostQueryServiceProtocol` in `analytics/contracts.py`. Response
(`CostMonthReport`): `totals` (calls, tokens, `cost_usd`, `unpriced_calls`),
`by_intent`, `by_model`, and `trend` (the 6 months ending with the requested
month). All figures user-scoped; month bucketing uses UTC calendar months
(session-tz independent).

```json
{
  "month": "2026-10",
  "totals": { "calls": 42, "tokens_in": 123456, "tokens_out": 7890,
              "cost_usd": 1.2345, "unpriced_calls": 3 },
  "budget": { "monthly_budget_usd": 5.0, "budget_mode": "warn",
              "over_budget": false },
  "by_intent": [ { "intent": "draft", "calls": 10, "cost_usd": 0.61,
                   "unpriced_calls": 0 } ],
  "by_model": [ { "provider": "zai", "model_id": "glm-5.3", "calls": 30,
                  "cost_usd": 1.1, "unpriced_calls": 0 } ],
  "trend": [ { "month": "2026-05", "cost_usd": 0.9 },
             { "month": "2026-06", "cost_usd": 0.75 },
             { "month": "2026-07", "cost_usd": 1.1 },
             { "month": "2026-08", "cost_usd": 0.95 },
             { "month": "2026-09", "cost_usd": 1.05 },
             { "month": "2026-10", "cost_usd": 1.2345 } ]
}
```

**CSV export:** `GET /api/v1/analytics/costs/export?month=YYYY-MM` (auth
required; same month validation ⇒ 422) streams `text/csv; charset=utf-8` as
an attachment (`narrare-costs-<month>.csv`) — a UTF-8 BOM + header row, then
one line per usage record in chronological order. Unpriced calls and deleted
novels (NULL `novel_id`) export as empty cells, never guessed values. The
panel button downloads the selected month (`analytics.costs.exportCsv`,
en/de/fr). PDF export was formally rejected — see Status & History.

**Capture seam (ADR-093):** Core `llm/usage_events.py` defines the DB-free
`UsageEvent`, the never-raise `UsageEventSink` Protocol, a single process-local
sink slot (`set_usage_event_sink`/`get_usage_event_sink` — unset ⇒ no-op), and
the attribution ContextVars. Emission happens at three disjoint points — the
`NarrareObservability` capability (intent = agent-class slug; per model
request), the registry run/stream layer (`llm/registry_run.py`, `LLMIntent`
vocabulary), and the embedding provider (`llm/embedding_providers.py`,
`OpenAIEmbeddingProvider.embed_texts` — one event per API batch,
`intent="embeddings"`) — so capability-carrying and bare-ephemeral agents are
each counted exactly once and embedding batches land per API call. Emission is wrapped in a catch-all guard: a sink failure is
logged and swallowed; the product run is never affected.

**Persistence:** `SqlUsageEventSink` (`analytics/usage_sink.py`) validates and
writes via `UsageRecordRepository` into `usage_records` (Alembic `0043`),
one short-lived session per record, registered once at app startup
(`_app/lifespan.py`) and unset at shutdown. Rows without a resolved user are
skipped. Attribution: `usage_user_id` from the auth dependency,
`usage_novel_id` from the novel path (`analytics/middleware.py`; WS session
bootstrap sets the same vars — `asyncio.create_task` context copy carries
attribution into background jobs).

**Pricing:** write-time, strict (`estimate_cost_usd` over the models.dev
cache — see [Model Data Reference](../../reference/model-data.md)): only
exact-model rates price a call; unknown models store `cost_usd = NULL` and are
counted as `unpriced_calls` — never re-priced at read time.

**Budget gate (ADR-094):** user-level `monthly_budget_usd` + `budget_mode`
(`warn` | `block`, default `warn`) stored on `user_ai_settings` (Alembic
`0044`; get-set settings endpoints). In block mode a pre-call gate in
`ModelRegistry.get_model()` — the single point both ADR-093 LLM emission
populations acquire models through — raises `BudgetExceededError`, mapped by
one registered handler to **HTTP 429 `BUDGET_EXCEEDED`** (embeddings count
toward the month total but are not gated — documented v1 limitation).
`SqlUsageEventSink` arms the gate with an in-process per-user UTC-month
running total (startup hydration + per-write increment, no scheduler);
budget-config changes invalidate in-process (no DB read on the LLM hot
path). The costs endpoint returns the `budget` block above (`null` when no
budget is set; `over_budget` uses the same `>=` boundary as the gate),
which drives the warn badge and the block banner; the FE maps
`429 BUDGET_EXCEEDED` distinctly from provider rate limits.

**Frontend:** `/analytics` page (`app/(studio)/analytics/`) with the
`AnalyticsCostsPanel` (totals card, breakdown tables, `CostTrendChart` via
Recharts), TanStack Query hook, `analytics.*` i18n (en/de/fr).

## Constraints & Edge Cases

- **Known-untracked spend:** mem0-internal LLM calls (RULE-01b exception #2),
  setup provider validation (exception #13), and abandoned streams
  (a `GeneratorExit` mid-stream emits nothing — partial-turn tokens of the
  final request are uncounted). Documented limitation, not a bug.
- Costs are estimates; unpriced models appear as counts, never guessed costs.
- Month bucketing is UTC; the default month is server-local — the displayed
  month can differ from a session timezone around month boundaries.
- Sink DB failures are logged and swallowed (cost data is best-effort; a
  crash mid-insert loses that record).
- Deleted novels keep their cost rows (`novel_id` `ON DELETE SET NULL`).
- Records are user-scoped; there is no project/admin aggregation surface.
- Budget math counts only priced calls toward the USD total (unpriced stay
  visible as counts, never guessed in); embeddings count toward the total
  but are not pre-call gated (documented v1 limitation). The call that
  crosses the budget completes — blocking starts with the next call.

## Related Features

- [INFRA-001](../infra/INFRA-001-llm-gateway.md) — LLM usage source
- [STATS-001](STATS-001-writing-stats.md) — Writing Statistics (joins the
  same Analytics panel in a later cycle)
- [SETUP-004](../setup/SETUP-004-provider-config.md) — Provider configuration
  (its validation calls are not tracked)

## Status & History

- `project-init` — Added to registry as planned feature (old spec: budgets,
  Settings home, CLI — superseded).
- 2026-10-05 — PO rulings D1–D4 (transparency only; dual emission seam;
  write-time strict costs; `/analytics` panel home); architecture gate
  findings F1–F7 folded in; ADR-093 authored.
- 2026-10-06 — v1 implemented (commits `b2aeb9af..a4f2c2ba`): Core seam +
  emission, `analytics` API module + endpoint + lifespan wiring, `/analytics`
  FE panel + `analytics.*` i18n. Status → `in-progress`.
- 2026-10-07 — CLI formally retired (PO decision): no CLI substrate exists, a
  CLI would have to bypass the service layer/user scoping or duplicate HTTP+auth
  plumbing, and the `/analytics` panel + CSV export cover the value. Removed
  from the deferred slices.
- 2026-10-07 — Embeddings cost implemented (commits `a1d12c4d..efa8a060`) as
  [ADR-093](../../architecture/decisions/ADR-093-usage-event-sink-cost-persistence.md)
  surface (c) (post-implementation amendment: decision 4 is now **three
  disjoint emission surfaces**). Emission at `OpenAIEmbeddingProvider.embed_texts`
  (`packages/core/narrare_core/llm/embedding_providers.py`): one `UsageEvent`
  per API batch, `intent="embeddings"`, strict write-time cost (unknown
  embedding models stay unpriced). Budget interplay per
  [ADR-094](../../architecture/decisions/ADR-094-budget-gate-ai-spend-suspension.md)
  D1: embeddings count toward totals but are not pre-call gated — v1
  limitation. Binding spec:
  [embeddings-cost addendum](../../superpowers/specs/2026-10-07-stats002-embeddings-cost-design.md).
- 2026-10-07 — CSV export implemented (commits `9ea8d9e3..b657d81c`) per
  [csv-export addendum](../../superpowers/specs/2026-10-07-stats002-csv-export-design.md):
  streaming, month-scoped `GET /api/v1/analytics/costs/export` (repository
  row stream → service CSV lines → `StreamingResponse`), UTF-8 BOM + header
  row, empty cells for unpriced/NULL values, panel download button
  (`analytics.costs.exportCsv`, en/de/fr). **PDF export formally REJECTED**
  (design-sheet ruling): CSV covers data egress, the panel is the
  presentation view, and a cost PDF would widen the RULE-08-guarded renderer
  surface for near-zero value. Removed from the deferred slices.
- 2026-10-07 — Budgets implemented (commits `c276a933..3733871c`) per
  [ADR-094](../../architecture/decisions/ADR-094-budget-gate-ai-spend-suspension.md)
  (✅ Implemented) + spec addendum
  [budgets design](../../superpowers/specs/2026-10-07-stats002-budgets-design.md):
  user-level monthly USD budget on `user_ai_settings` (`monthly_budget_usd`
  + `budget_mode`, Alembic `0044`) with **warn badge default / opt-in hard
  block** (429 `BUDGET_EXCEEDED`); pre-call gate at
  `ModelRegistry.get_model()` (both ADR-093 LLM populations; embeddings
  counted-not-gated — v1 limitation); `SqlUsageEventSink`-armed in-process
  per-user UTC-month running total (startup hydration + per-write
  increment); costs endpoint returns the `budget` block; FE badge/banner/
  settings (`Settings → AI`), i18n en/de/fr. **Status → `stable`** —
  budgets was the last major deferred code slice.

**Deferred slices (registered scope):** read-time re-pricing ·
per-series attribution · tracking of mem0-internal and setup-validation
LLM calls · STATS-001 (second cycle in the same panel).
