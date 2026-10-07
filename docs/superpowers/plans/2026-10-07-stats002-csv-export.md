# STATS-002 — Cost CSV Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Month-scoped CSV export of the user's AI cost records via a streaming endpoint + panel button. Binding spec: `docs/superpowers/specs/2026-10-07-stats002-csv-export-design.md` (B-1..B-7; PDF rejected).

**Architecture:** Repository streams `usage_records` rows for the month window → service formats CSV lines (stdlib `csv`) → `StreamingResponse`; FE button does an authenticated blob download. All inside the existing `analytics/` module — no new seams, no new deps.

## Global Constraints

- English; RULE-06 (router delegates) / RULE-08 (SQLAlchemy only in repository); TDD; ≤3 files / ≤250 new LOC per task; conventional commits; never `git commit --no-verify`/`-n`.
- Month semantics identical to the costs endpoint (default = server-local current month; validation regex + year-window guard ⇒ 422; UTC bucketing).
- Test commands: `uv run pytest <path> -v`; FE `pnpm vitest run <path>` (from `packages/web`); i18n `pnpm check:i18n` (repo root).

---

### Task B1: API — repository stream + service CSV + export endpoint

**Files:**
- Modify: `apps/api/narrare/analytics/repository.py` (stream method)
- Modify: `apps/api/narrare/analytics/service.py` (CSV line formatting + month-window resolution reuse)
- Modify: `apps/api/narrare/analytics/router.py` (+ `contracts.py` ONLY if a typed stream protocol is warranted — otherwise skip; keep ≤3 files: if contracts needs touching, put the shared month-window helper consolidation in service only)
- Test: `tests/unit/api/analytics/test_costs_export.py` (create)

**Interfaces:**
- Consumes: `UsageRecordRow`; the service's existing month validation (`InvalidMonthError` + year-window guard); router conventions from `get_monthly_costs`.
- Produces (binding):
  - `UsageRecordRepository.stream_month(user_id: UUID, start: datetime, end: datetime) -> AsyncIterator[UsageRecordRow]` — `select(...).where(user-scoped, created_at in [start,end)).order_by(created_at)` with `execution_options(yield_per=<repo-appropriate chunk>)` (mirror house streaming-repository patterns; RULE-08 stays intact).
  - `CostQueryService.export_csv_lines(user_id: UUID, month: str | None) -> AsyncIterator[str]` — yields the BOM+header line then one CSV line per row (`csv.writer` over an in-memory line per row is fine; per B-5 keep it stdlib-simple); empty cells for NULL cost/novel; ISO-8601 UTC timestamps.
  - Router: `GET /costs/export` returning `StreamingResponse(service.export_csv_lines(...), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="narrare-costs-<month>.csv"'})` — month Query param with the same pattern; `InvalidMonthError` handled by the already-registered handler (422). Header building may live in the service (returns headers dict) to keep the router a delegator.

- [ ] **Step 1: Write failing tests** — mirror `test_costs_router.py` harness (real service over a fake repo): 200 with content-type + disposition + BOM + exact header row; row formatting (unpriced ⇒ empty cost cell; novel NULL ⇒ empty; token/duration ints); user scoping via repo args; 422 invalid + year-edge months; 401; streaming shape (first lines arrive without exhausting the generator — e.g. `aiter` partially consumed in the test). Repository stream test: real-PG integration optional (mirror `test_usage_record_aggregation.py` fixtures if DB reachable; else unit-level query-shape assertions like Task 6's pattern).
- [ ] **Step 2: Run — expect FAIL.** **Step 3: Implement.** **Step 4: Run — expect PASS** (`uv run pytest tests/unit/api/analytics -v`).
- [ ] **Step 5: Commit** `feat(api): streaming CSV export of monthly usage records` (add the touched files).

---

### Task B2: FE — export button + i18n

**Files:**
- Modify: `packages/web/components/analytics/AnalyticsCostsPanel.tsx` (+ optionally a tiny `lib/api/analytics.ts` helper — prefer adding the fetch-blob helper THERE to keep the panel lean)
- Modify: `packages/web/lib/api/analytics.ts`
- Modify: `packages/i18n/messages/en/analytics.json` + `de` + `fr` (4 files total — coordinator-approved for this slice; i18n trio is inseparable)
- Test: `packages/web/components/analytics/AnalyticsCostsPanel.test.tsx` (extend) — if that pushes the file past limits, a sibling `__tests__` file per house convention

**Interfaces:**
- Consumes: the authenticated fetch wrapper (`lib/api/core.ts`); `useAnalyticsCosts` month state.
- Produces: `downloadCostsCsv(month: string): Promise<void>` in `lib/api/analytics.ts` — GET `/api/v1/analytics/costs/export?month=...` → `response.blob()` → object-URL `<a download>` click → revoke; button in the panel header (next to month selector, labeled `analytics.costs.exportCsv`, disabled while in flight; error surfaces via the panel's existing error path or a quiet console + re-throw — match house UX for download failures).

- [ ] **Step 1: Failing tests** — button renders + label; click triggers the download helper with the selected month (mock); disabled during flight; i18n parity via check:i18n.
- [ ] **Step 2: FAIL.** **Step 3: Implement.** **Step 4: PASS** (`pnpm vitest run components/analytics`).
- [ ] **Step 5: Commit** `feat(web): cost CSV export button (en/de/fr)`.

---

### Task B3: Docs — feature-file rider

**Files:**
- Modify: `docs/features/analytics/STATS-002-cost-tracking.md`

Remove "CSV/PDF export" from the deferred slices; add a dated (2026-10-07) history note: CSV export implemented per spec addendum `2026-10-07-stats002-csv-export-design.md` (streaming, month-scoped); **PDF formally rejected** (design-sheet ruling recorded). Gate: `just check-architecture`. Commit: `docs(features): STATS-002 CSV export implemented — PDF rejected`.
