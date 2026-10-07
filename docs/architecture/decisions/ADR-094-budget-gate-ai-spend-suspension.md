# ADR-094 — Budget Gate & AI Spend Suspension (STATS-002)

> **Status:** ✅ Implemented (per Gate 12 — implementation complete
> 2026-10-07: branch `feature/stats002-budgets`, commits
> `c276a933..3733871c`; binding spec addendum
> `docs/superpowers/specs/2026-10-07-stats002-budgets-design.md`, plan
> `docs/superpowers/plans/2026-10-07-stats002-budgets.md` — see the
> Implementation Report below)
> **Date:** 2026-10-07
> **Deciders:** Architecture Agent; Project Owner (ratified semantics:
> user-level monthly USD budget · warn badge default · opt-in hard block)
> **Related:** ADR-093 (the seam whose totals this gate arms; the decision-1
> inversion recorded here), ADR-092 (decision 6 — why the guard slot is not a
> registry), ADR-082 (token budgets — distinct axis, see decision 9),
> ADR-080 (in-process execution — no cron), ADR-084 (WS identity),
> `docs/features/analytics/STATS-002-cost-tracking.md` § deferred slices

---

## Context

STATS-002 v1 (ADR-093) delivered *transparency*: per-call usage records,
strict write-time pricing, a monthly costs panel. The deferred slice is
*control*: a monthly USD budget with the ability to warn — and, when the
user opts in, to stop spend.

Two structural facts shape the decision:

1. **The sink cannot enforce.** ADR-093's emission is post-call by
   construction: by the time `SqlUsageEventSink.record()` runs, the tokens
   are spent. True pre-call gating needs a check *before* LLM invocation.
2. **`ModelRegistry.get_model()` is the single upstream choke point for both
   ADR-093 emission populations.** Verified call graph:
   `prepare()` acquires via `get_model()` (`gateway.py:123`),
   `RegistryRunMixin.run()`/`stream()` acquire via `get_model()`
   (`registry_run.py:107`/`:183`), and capability-path services acquire
   models through `prepare()`/`get_model()` (e.g. `_summary_invocation.py`,
   `chat/_tiering.py`). One gate there covers everything that reaches a
   model. Conversely, the capability seam's `before_model_request` hook
   (`observability.py:138`) would structurally miss the registry's bare
   agents — including the dominant WS writing turns (ADR-093 gate F1).

---

## Decision Drivers

- **True pre-call gating** without instrumenting ~30 service call sites.
- **Never silently miss a population** — the mirror of ADR-093 F1: a gate on
  the wrong seam is worse than no gate (false sense of control).
- **The inversion must be controlled.** ADR-093's philosophy is "cost
  capture may never break a product run". A budget *block* deliberately
  stops a run — that inversion of D1 must be recorded, bounded to one seam,
  one exception, one error mapping, and one opt-in mode.
- **Month semantics must match the money math** — UTC calendar months,
  identical to the repository's UTC-pinned bucketing.
- **Honest budget math** (RULE-11): unpriced calls cannot count toward a
  USD budget and must stay visible; untracked spend is never estimated in.
- **ADR-080 boundary** — no scheduler, no new infrastructure.

---

## Options Considered

### Option A — Warn-only (read-side badge, no enforcement)

Costs endpoint joins the budget; FE shows a badge when spend crosses it.

**Pros:** zero Core change, zero risk.
**Cons:** a "budget" that cannot stop spend is weak; the PO deferred this
slice expecting enforcement semantics. Rejected as the whole answer (warn
*is* the default mode of the chosen option).

### Option B — Pre-call gate at `get_model()` + sink-armed in-process state (chosen)

`get_model()` consults a `BudgetGuard` slot before returning a model;
`SqlUsageEventSink` maintains the per-user month total that arms it.

**Pros:** one touch point covers both populations; no service-layer change;
bounded, explicit inversion of ADR-093 D1.
**Cons:** inverts never-raise in a controlled way (accepted, recorded);
in-process state assumes single-app deployment (ADR-029/080 — accepted).

### Option C — Service-layer pre-checks

Each API service checks the budget before its LLM call.

**Pros:** no Core change.
**Cons:** ~30 call sites, every new site can silently forget — drift by
construction. Rejected for exactly the reason ADR-093 rejected its Option A.

### Option D — Capability-seam gate (`before_model_request`)

Gate inside the observability capability.

**Cons:** misses the registry's bare-agent population incl. WS writing
turnes — the dominant token consumer (ADR-093 F1). Structurally wrong;
rejected without further evaluation.

Also rejected inline: **per-feature budget caps** (no request surface
exists, YAGNI) and a **`cost_budgets` table** (two scalars; see decision 7).

---

## Decision

**We choose Option B**, in ten decisions:

1. **Gate location: `ModelRegistry.get_model()`.** The check runs inside
   `get_model()` (`gateway.py:77`), before the provider factory call — the
   single point through which both ADR-093 v1 populations acquire models.
   Documented ungated-and-untracked pair unchanged: mem0-internal LLM calls
   (RULE-01b exception #2) and setup provider validation (#13) never reach
   `get_model()`. **Documented v1 limitation:** embedding calls (ADR-093's
   third emission surface) count toward the month total but are **not
   pre-call gated** — `get_model()` is not on their path (review trigger).

2. **`BudgetGuard` Protocol slot — module state, not a registry.** A pure
   Core module `narrare_core/llm/budget.py` owns the `BudgetGuard` Protocol
   (RULE-03), a single-slot `set_budget_guard()`/`get_budget_guard()` — the
   exact ADR-093 decision-2 service-locator pattern, therefore explicitly
   **not** a registry and outside ADR-092 decision 6's fourth-registry
   trigger. Unset guard ⇒ no-op (tests, CLI, Core-only usage pay zero
   overhead). The API registers its guard once at app startup (lifespan),
   next to the sink registration.

3. **Attribution from `usage_user_id`; `None` ⇒ no check.** The guard reads
   the ADR-093 ContextVar — proven reliable by v1 attribution (HTTP
   middleware + WS bootstrap per ADR-084). No signature change anywhere;
   missing attribution (tests, CLI) can never false-positive a block.

4. **`BudgetExceededError` → one registered handler → 429.** The exception
   is a Core type (`narrare_core/shared/errors.py`, `NarrareError`
   subclass — the error catalog is the SSOT home for Core exceptions; the
   guard machinery in `llm/budget.py` raises it). The API registers exactly
   one exception handler (`_app/main.py`, precedent: `ExportError` /
   `ScopeError` / `InvalidMonthError` handlers) mapping it to **HTTP 429**
   with a machine-readable code the FE turns into a banner via existing
   query-error paths. 429 because the semantics are quota exhaustion
   ("too many requests for this user this month") — 402 implies payment
   processing (wrong for a local-first BYO-key app), 403 implies
   authorization (misleading). **The sink's never-raise contract (ADR-093
   D1) is untouched** — the inversion is confined to the gate seam, which
   raises before any spend occurs.

5. **Arming without cron.** `SqlUsageEventSink` maintains an in-process
   per-user UTC-month running total: hydrated once at startup (single
   aggregate query over `usage_records`), incremented after each successful
   write. Month rollover = month-key comparison on write/read (state lazily
   re-hydrates when the key changes) — no scheduler, ADR-080-consistent.
   Restart-safe (hydration). Unattributed events do not count (the sink
   drops them pre-count — consistent with their having no budget surface).
   Money stays `Decimal` end-to-end (no float).

6. **Semantics (PO-ratified 2026-10-07):** user-level **monthly USD budget**
   (the wallet spans novels — same scope as every cost read); **warn badge
   by default** (read-side: costs endpoint returns spent/budget so the FE
   can badge); **hard block opt-in** via `budget_mode` — hard-blocking
   mid-scene is hostile to a creative tool, so blocking is never the
   default. Month = UTC calendar month, identical to the repository's
   UTC-pinned `date_trunc` bucketing.

7. **Storage: two typed columns on `user_ai_settings`.**
   `monthly_budget_usd NUMERIC(10,2) NULL` (NULL = no budget; `0` in block
   mode is a valid full stop) and `budget_mode` String(10) NOT NULL
   `server_default='warn'` (`'warn' | 'block'`). This matches the table's
   own scalar-column pattern (`embedding_provider`, `embedding_model`) —
   Alembic migration per RULE-14. Rejected: a `cost_budgets` table (two
   scalars with no query surface of their own — table + repository +
   service for nothing) and `ProjectSettings` (wrong scope: the wallet is
   per-user cross-novel).

8. **Gate behavior.** The guard no-ops unless *all* hold: mode `block`,
   budget set, `usage_user_id` present, month total ≥ budget. In `warn`
   mode the gate never raises — the badge is purely read-side. Budget
   config is cached in-process with write-through invalidation on settings
   update — **no DB read on the LLM-call hot path**.

9. **Distinct axis from per-run limits.** `UsageLimits` /
   `token_limit_profile` (ADR-082) cap a *single run's tokens*; the budget
   caps a *month's USD across all calls*. Different axes, never conflated
   in UI or docs (both live in settings — the docs must keep them apart).

10. **WS blocks on the next turn.** Each WS writing turn re-enters
    `get_model()` (`registry_run.py:183`), so a crossed threshold takes
    effect on the next turn; a turn already in flight completes (~1-call
    boundary latency, inherent to post-write arming). Documented, accepted.

---

## Rationale

Root-cause chain (2× why):

1. **Symptom:** users can see spend but cannot cap it.
2. **Why?** v1 deliberately shipped transparency only; enforcement needs a
   pre-call check, and no such check point existed.
3. **Why?** Capture could be centralized post-call (ADR-093) because two
   emission surfaces already existed; prevention needs a *pre-call* choke,
   and the only one shared by both populations is `get_model()` — verified
   against the call graph, not assumed.
4. **Design:** arm the existing sink with a running total, gate the one
   shared acquisition point, raise one dedicated exception through one
   handler. Option A cannot stop spend; Option C drifts; Option D misses
   the dominant population. B is the simplest *correct* enforcement.

---

## Consequences

**Positive:**

- One gate covers both emission populations; zero service-layer changes.
- Default (`warn`) adds zero behavioral risk — only the opt-in mode blocks.
- Month totals and the costs panel can never disagree (same table, same
  UTC bucketing, same strict pricing).

**Negative / Trade-offs:**

- Controlled inversion of ADR-093 D1's philosophy — confined to the gate
  seam, one exception, one handler, opt-in mode (recorded here).
- In-process arming assumes single-app deployment (ADR-029/080); a restart
  re-hydrates from `usage_records` (bounded, correct).
- ~1-call boundary latency: the call that crosses the threshold completes;
  blocking starts with the next acquisition.
- Embedding calls are counted but not gated (decision 1) — a blocked user's
  KB-ingest embeddings would still run until the review trigger fires.
- Unpriced calls cannot count toward a USD budget (decision 8 honesty):
  a month with a high unpriced share under-blocks; it stays *visible* as
  `unpriced_calls` instead of being silently guessed.

**Constraints touched:** RULE-03 (Protocol first), RULE-04 (task sizing),
RULE-06/07 (handler home in `_app/`; Core guard pure — no HTTP, no DB in
`llm/budget.py`), RULE-08 (guard impl delegates reads to repositories),
RULE-10 (tests per slice), RULE-11 (unpriced visible; block surfaces
loudly as 429 + banner), RULE-14 (Alembic for the two columns), RULE-17
(i18n for badge/banner/settings, en/de/fr), RULE-18b (this *is* the
governed settings-surface decision for budgets), RULE-20.

---

## Sustainability Check

1. **Correct in 3 months?** Yes — under the same single-user in-process
   deployment contract as ADR-093 (shared review trigger below).
2. **Hard-to-undo coupling?** None: dropping the guard registration
   restores ADR-093 behavior exactly; both columns are nullable/defaulted.
3. **Simplest correct solution?** Yes — one check at one verified choke
   point, arming reuses the sink that must exist anyway.
4. **Intent clear?** This ADR (architecture) + the binding implementation
   spec (wire shapes, cache invalidation, FE) — same split as ADR-093.

---

## Implementation Notes

- Module homes: Core `narrare_core/llm/budget.py` (guard Protocol + slot +
  `enforce_budget()` helper) + `BudgetExceededError` in
  `narrare_core/shared/errors.py`; `gateway.py` `get_model()` +~10 LOC
  (slot check after profile conversion, before provider factory).
- API: `analytics/usage_sink.py` (running-total state + startup hydration
  in lifespan); `settings/models.py` columns + Alembic migration; settings
  service/router get-set budget; `_app/main.py` 429 handler; costs endpoint
  response gains budget fields for the warn badge.
- FE: badge in the analytics costs panel + block banner via existing
  query-error handling + one settings field; i18n en/de/fr.
- Tests (RULE-10): unset-guard no-op; `None` attribution fast-path; block
  raise → 429 mapping; month rollover; unpriced exclusion; WS next-turn
  semantics; settings-write invalidation.

**ADR Implementation Completeness Gate (Gate 12):** flip INDEX to
"✅ Implemented" only when Core guard + gate, arming, storage + migration,
handler, costs-endpoint badge fields, FE badge/banner/settings, i18n, and
tests are all complete.

---

## Implementation Report (2026-10-07)

Implemented on branch `feature/stats002-budgets`, commits
`c276a933..3733871c`, per the binding spec addendum
`docs/superpowers/specs/2026-10-07-stats002-budgets-design.md` and plan
`docs/superpowers/plans/2026-10-07-stats002-budgets.md`. Mapping to the
decisions above:

- **D1/D2/D3 (gate location, slot, attribution):** `narrare_core/llm/budget.py`
  owns the `BudgetGuard` Protocol, the single-slot
  `set_budget_guard()`/`get_budget_guard()`, and `check_budget()`;
  `gateway.py` `get_model()` calls it after profile conversion, before the
  provider factory; `BudgetExceededError` lives in `shared/errors.py`.
  Unset guard ⇒ no-op; `usage_user_id=None` ⇒ no check. Embeddings stay
  counted-not-gated (documented v1 limitation, review trigger unchanged).
- **D4 (one handler → 429):** `_app/main.py` registers the handler —
  HTTP 429 with `code: "BUDGET_EXCEEDED"`; the sink's never-raise contract
  untouched.
- **D5/D8 (arming without cron, no hot-path reads):** `analytics/budget_guard.py`
  (`arm_budget_guard` — startup hydration in lifespan, per-write increment
  in the sink) + `analytics/budget_invalidation.py` (write-through budget
  config invalidation); unattributed events don't count; `Decimal`
  end-to-end.
- **D6/D7 (semantics + storage):** `monthly_budget_usd NUMERIC(10,2) NULL`
  + `budget_mode` (`warn`/`block`, server default `warn`) on
  `user_ai_settings` (Alembic `0044`); settings get-set endpoints; an
  explicit-null `budget_mode` is rejected at the schema level (PATCH
  semantics pinned by test).
- **Costs endpoint (warn-badge read side):** `CostMonthReport.budget`
  (`CostBudgetBlock`: `monthly_budget_usd`, `budget_mode`, `over_budget`) —
  `over_budget` uses the same `>=` boundary as the gate; `null` when no
  budget is set.
- **FE (RULE-17):** totals-card warn badge, dismissible
  `BudgetExceededBanner`, budget section in Settings → AI
  (`useBudgetSettingsSave`, RULE-04 split; FE-level amount cap with surfaced
  save failures); i18n en/de/fr.
- **Tests (RULE-10):** guard slot no-op, `None`-attribution fast path, gate
  raise → 429 mapping, arming/month rollover, unpriced exclusion, settings
  write invalidation, costs budget block, lifespan registration, FE suites.

**Where the implementation refined the decision text (factual, per the
sections above):**

1. **Banner arming is data-derived.** Decision 4 anticipated the banner
   surfacing "via existing query-error paths" from the 429. As implemented,
   the banner arms from the costs-report **data** (`budget.over_budget &&
   budget_mode === "block"` — the production-reachable signal, since warn
   mode never raises) with dismiss/re-arm semantics (a dismissal holds until
   the budget is raised/removed and hit again). The 429 remains the
   enforcement backstop for call paths outside the panel.
2. **The 429 mapping needed explicit FE code handling.** `ApiError` carries
   the machine-readable `code`; both the fetch and the SSE (`connectSSE`)
   paths parse it, so `429 BUDGET_EXCEEDED` maps to the budget message, a
   plain 429 stays a rate-limit signal, and a budget 429 after a token
   refresh is never misrouted to the login redirect. This addresses Review
   Trigger 5's confusion risk at the mapping layer.

Gate 12 satisfied — Core guard + gate, arming, storage + migration, handler,
costs-endpoint budget block, FE badge/banner/settings, i18n, and tests all
complete; INDEX flipped to ✅ Implemented in the same docs pass.

---

## Review Triggers

- [ ] Narrare moves to multi-user/multi-worker deployment → in-process
      arming and the module-state slot break (shared ADR-093 trigger);
      re-decide the guard substrate.
- [ ] Embedding spend grows material → extend the gate to the embedding
      provider seam (the guard slot is importable from `llm/` by
      construction); do not leave the gap undocumented.
- [ ] mem0 ever exposes hooks for its internal LLM calls → close the bypass
      (tracking and gating must land together).
- [ ] Per-feature caps or per-novel wallets are requested → new decision
      (explicitly rejected here as YAGNI).
- [ ] 429 becomes confusing next to provider-side rate limits in FE error
      handling → revisit the status-code mapping.
- [ ] A new model-acquisition path bypasses `get_model()` → an ungated
      population exists; audit the choke point.
