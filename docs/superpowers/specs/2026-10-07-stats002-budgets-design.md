# STATS-002 — Budget Gate & AI Spend Suspension — Design Addendum

- **Date:** 2026-10-07
- **Status:** PO-ratified (decision sheet item A: warn-default + opt-in block; sequencing C→D→B→A→E)
- **Amends:** `2026-10-05-stats002-cost-tracking-design.md` §9 — implements the "budgets & suspension" deferred slice
- **ADR:** ADR-094 (Proposed → flips to Implemented with this slice) — records the CONTROLLED inversion
  of ADR-093 D1 (a seam that may raise) and all semantics below

---

## 1. Decisions (binding; mirrors ADR-094)

| # | Decision | Ruling |
|---|----------|--------|
| A-1 | Enforcement point | Pre-call gate inside `ModelRegistry.get_model()` (`gateway.py:77`) — the single upstream choke point covering BOTH ADR-093 LLM populations (`prepare()` gateway.py:123; `run()`/`stream()` registry_run.py:107/183). The gate consults a `BudgetGuard` Protocol slot (module-state pattern per ADR-093 D2) BEFORE returning a model. |
| A-2 | Error | `BudgetExceededError` in `narrare_core/shared/errors.py` (Core error-catalog SSOT); raised by the gate when the user's month spend ≥ budget AND mode is `block`. One registered API handler → **429** with `{"detail", "code": "BUDGET_EXCEEDED"}` (i18n on the FE). Embeddings are NOT gated (no `get_model()` on their path — ADR-094 D1 v1 limitation) but COUNT toward totals. |
| A-3 | Guard contract | `llm/budget.py` (Core-pure): `BudgetGuard` Protocol `def check(user_id: UUID) -> None` (raises `BudgetExceededError`); slot `set_budget_guard(guard: BudgetGuard | None) -> None`; unset ⇒ no check (tests/CLI); `usage_user_id.get()` is `None` ⇒ no check. |
| A-4 | Arming | `SqlUsageEventSink` maintains an in-process per-user UTC-month running total: startup-hydrated (`SELECT user_id, SUM(cost_usd) … GROUP BY` over the current UTC month), incremented on each priced write; month-key comparison rolls the state over lazily (no cron). The API-side guard impl reads budget config (cached, write-through invalidation on settings change — no DB on the hot path) + the running total. |
| A-5 | Semantics | User-level monthly USD budget (a wallet spans novels — NOT ProjectSettings). `monthly_budget_usd NUMERIC(10,2) NULL` (NULL = no budget) + `budget_mode TEXT DEFAULT 'warn' CHECK (budget_mode IN ('warn','block'))` on `user_ai_settings`. Warn badge always-on when budget set (FE reads spend vs budget on the costs endpoint); hard block OPT-IN (`block`). `budget = 0` in block mode = valid full stop. Unpriced calls excluded from budget math (stay visible as `unpriced_calls`). Distinct axis from per-run `UsageLimits`/token-limit profiles. |
| A-6 | Costs endpoint enrichment | `GET /analytics/costs` response gains `budget: {monthly_budget_usd: float | None, budget_mode: "warn"|"block", month_spend_usd: float, over_budget: bool} | None` (None when no budget set) — one round trip for the badge. |
| A-7 | Settings surface | Get/set via the existing user-AI-settings surface (mirror sibling settings fields' endpoint conventions): `monthly_budget_usd` (nullable decimal, ≥ 0, validation 422) and `budget_mode` (enum). Write-through cache invalidation. |
| A-8 | FE | Costs panel: budget badge next to totals (OK / over-budget warn; in block mode: hard-stop banner explaining the 429). Settings: budget field + mode toggle (where sibling AI settings live). Query-error path maps 429 `BUDGET_EXCEEDED` → banner. i18n en/de/fr (`analytics.budget.*` + settings namespace). |
| A-9 | Bypasses (documented) | mem0-internal + setup-validation calls remain ungated (not routed via get_model in-process); tests/CLI (no guard set / no user). |

## 2. Testing Strategy

- **Core:** guard slot semantics (unset ⇒ no-op; set + user ⇒ check called; `BudgetExceededError` propagation); `get_model()` gate raises only in block mode at/above budget; capability-path AND registry-path both gated (one gate, two path tests); cancellation semantics untouched.
- **API:** migration round-trip (0044); settings get/set + validation; sink arming (hydration SQL shape, increment, month rollover lazy); guard config cache (write-through); 429 handler on the real app (happy 200 under budget, 429 at/above in block mode, warn mode never blocks); costs endpoint `budget` block correctness.
- **FE:** badge states, banner on 429 mapping, settings field + mode toggle, i18n parity.

## 3. Out of Scope

Per-feature caps (rejected YAGNI) · embeddings pre-call gating (ADR-094 D1 review trigger) · budget alerts/notifications beyond the badge/banner · budget history/graphs · admin-level budgets.
