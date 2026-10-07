# STATS-002 — Budget Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** User-level monthly USD budget with warn-badge default and opt-in hard block (429) via a pre-call gate at `ModelRegistry.get_model()` — ADR-094. Binding spec: `docs/superpowers/specs/2026-10-07-stats002-budgets-design.md` (A-1..A-9).

**Architecture:** Core `BudgetGuard` Protocol slot + `BudgetExceededError` (shared errors) + gate in `get_model()`; API-side guard armed by the sink's in-process running total (startup-hydrated) + cached budget config on `user_ai_settings` (Alembic 0044); costs endpoint budget block; FE badge/banner/settings; 429 handler.

## Global Constraints

English; Core HTTP/DB-free (guard Protocol + slot pure; the DB-backed impl lives in API); RULE-03/06/08/14/18b (budget values are user settings, not module constants); TDD; ≤3 files / ≤250 new LOC per task (STOP+report if a gate forces more); conventional commits; never `--no-verify`/`-n`.

---

### Task A1: Core — `BudgetExceededError` + `llm/budget.py` guard slot

**Files:** Create `packages/core/narrare_core/llm/budget.py`; Modify `packages/core/narrare_core/shared/errors.py`; Test `tests/unit/core/llm/test_budget.py` (create)

**Interfaces (binding for A2/A5):**
```python
# shared/errors.py
class BudgetExceededError(NarrareError):  # follow the file's base-class/id conventions; stable attrs: user_id, month_spend_usd, monthly_budget_usd
    ...
# llm/budget.py
class BudgetGuard(Protocol):
    def check(self, user_id: UUID) -> None: ...   # raises BudgetExceededError
def set_budget_guard(guard: BudgetGuard | None) -> None: ...
def get_budget_guard() -> BudgetGuard | None: ...
def check_budget(user_id: UUID | None) -> None    # unset guard or None user => no-op; else guard.check(user_id)
```
Tests: slot set/unset; None user no-op even with guard set; delegation + exception propagation; error attrs. TDD; commit `feat(core): budget guard slot + BudgetExceededError (ADR-094)`.

### Task A2: Core — `get_model()` gate

**Files:** Modify `packages/core/narrare_core/llm/gateway.py`; Test `tests/unit/core/llm/test_gateway_budget_gate.py` (create)

Binding: at the TOP of `get_model()` (before any provider/client work): `check_budget(usage_user_id.get())` — one line + import; raises propagate (this seam MAY raise — ADR-094's controlled inversion; do NOT wrap). Tests: guard set + over-budget + user ⇒ `get_model` raises before provider resolution (assert provider factory NOT called); no guard / no user ⇒ unaffected; both downstream paths (`prepare()` and `run()`) inherit the gate — pin with one path test each (registry path via `registry_run`, capability path via a `NarrareAgent` model acquisition — mirror existing fixtures). Existing gateway/registry suites green. TDD; commit `feat(core): pre-call budget gate at ModelRegistry.get_model (ADR-094)`.

### Task A3: API — `user_ai_settings` columns + Alembic 0044

**Files:** Modify `apps/api/narrare/settings/models.py`; Create `apps/api/alembic/versions/0044_budget_settings.py`; Test extend `tests/unit/api/settings/` (+ round-trip integration if the DB is reachable, mirroring the 0043 pattern)

Binding (A-5): `monthly_budget_usd NUMERIC(10,2) NULL`, `budget_mode TEXT NOT NULL DEFAULT 'warn' CHECK (IN ('warn','block'))`; mirror sibling column style; migration up/down symmetric. TDD; commit `feat(api): budget columns on user_ai_settings + Alembic 0044`.

### Task A4: API — settings endpoints (get/set budget)

**Files:** Modify the user-AI-settings service + router (locate via `settings/` family; mirror sibling field endpoints); Test extend the settings test module.

Binding (A-7): get/set `monthly_budget_usd` (nullable Decimal, ≥0, 422 on negative/garbage) + `budget_mode` (enum); write-through cache invalidation hook (A-5) — invalidate the guard's config cache on write; response schema mirrors sibling field shapes. TDD; commit `feat(api): monthly budget settings endpoints`.

### Task A5: API — sink arming + DB-backed guard + 429 handler

**Files:** Modify `apps/api/narrare/analytics/usage_sink.py` (running total + hydration); Create `apps/api/narrare/analytics/budget_guard.py` (DB-backed `BudgetGuard` impl: cached config + running total comparison + month rollover); Modify `apps/api/narrare/_app/{lifespan.py,main.py}` (hydrate + `set_budget_guard(...)` at startup, clear at shutdown; register `BudgetExceededError` handler → 429 `{"detail", "code": "BUDGET_EXCEEDED"}`); Tests: `tests/unit/api/analytics/test_budget_guard.py` + wiring test extension

Binding (A-2/A-4): running total per user per UTC month (startup `SELECT user_id, COALESCE(SUM(cost_usd),0) … WHERE created_at >= <month-start> GROUP BY user_id` — repository method, RULE-08); increment on priced writes in the sink AFTER successful insert; lazy month rollover (month-key compare resets totals); guard.check: no budget ⇒ return; warn ⇒ return; block + spend ≥ budget ⇒ raise with attrs; config cache with write-through invalidation (A4 hook); handler registered decorator-form (InvalidMonthError precedent). End-to-end wiring test on the real app: 200 under budget; 429 at/above in block mode; warn mode never blocks; unset guard (shutdown) no-op. TDD; commit `feat(api): budget guard arming + 429 handler (ADR-094)`. If >3 files is gate-forced (e.g. repository split), STOP+report for re-slice.

### Task A6: FE — badge, banner, settings field, i18n

**Files:** Modify `packages/web/components/analytics/{AnalyticsCostsPanel.tsx,CostTotalsCard.tsx}` (+ a small banner component inline or in the panel); Modify `packages/web/lib/api/analytics.ts` (+ budget block type + settings write via the settings api module); Modify the AI settings component (locate via settings-ai family) — budget field + mode toggle; i18n en/de/fr (`analytics.budget.*` + settings keys); Tests: panel + settings extensions

Binding (A-6/A-8): costs response `budget` block (None when unset) drives the badge (OK/over); 429 `BUDGET_EXCEEDED` from any AI query error path → dismissible banner with i18n text (block mode explains the stop + where to change); settings field (decimal, nullable) + mode select (warn/block); parity via check:i18n. TDD; commit `feat(web): budget badge, block banner, settings (en/de/fr)`.

### Task A7: Docs closure + ADR-094 flip

**Files:** `docs/features/analytics/STATS-002-cost-tracking.md` (deferred list; history note; status → `stable` — budgets was the LAST deferred STATS-002 code slice apart from read-time re-pricing/per-series which stay documented non-goals); `docs/architecture/decisions/ADR-094-*.md` (→ ✅ Implemented + completion note); `docs/architecture/decisions/INDEX.md` (row flip); `docs/_shared/CURRENT_STATE.md` (entry). Gate + commit `docs: close STATS-002 budgets — ADR-094 implemented`.
