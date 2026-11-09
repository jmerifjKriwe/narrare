# Implementation Plan: LLM Audit View and i18n Lazy-Loading

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only LLM usage summary endpoint and UI view (D15), and make
non-active locale catalogs load on demand instead of eagerly (A3).

**Architecture:** D15 is a new kernel read endpoint + a TanStack Query settings
page, reusing the existing `llm_calls` table and scoped repository base. A3
restructures the generated `catalogs.ts` into per-locale dynamic imports and
updates `i18n.ts` to load/fallback/cache catalogs by locale.

**Tech Stack:** Python 3.14, FastAPI/SQLAlchemy, Vite/React/TanStack Router/TanStack Query, existing `just generate`.

**Spec:** `docs/superpowers/specs/2026-11-09-llm-audit-view-and-i18n-lazy-loading-design.md`

## Global Constraints

- No new standing rule, checker, hook, or required field (CONSTRAINTS §8).
- Capability folders never import another capability; imports point `api → capabilities → kernel`.
- Generated files are regenerated with `just generate`, never hand-edited.
- English in code/tests; user-visible text in en/de/fr.
- Every user-owned row carries `user_id`; data access through the scoped repository base.

---

## Work Package 1 — D15: LLM Audit View (backend)

### Task 1: Summary endpoint

**Files:**
- Create: `app/kernel/llm/router.py` (or add to an existing kernel router)
- Modify: `app/api/main.py` (mount the router)
- Create: `app/kernel/llm/tests/test_llm_summary.py`

**Steps:**
- [ ] Define `GET /api/llm-calls/summary?days=7|30|90|0` returning aggregate
      counts by task_key, scoped to the current user.
- [ ] SQL: `SELECT task_key, count(*), count(*) FILTER (WHERE status='error')
      FROM llm_calls WHERE user_id = :uid AND (days=0 OR created_at >= now() - :interval)
      GROUP BY task_key`.
- [ ] Add `days` validation (0, 7, 30, 90).
- [ ] Mount router in `create_app()`.
- [ ] Unit test: seed llm_calls rows, assert summary returns correct aggregates.
- [ ] Run `just check` and `just test-file app/kernel/llm/tests/test_llm_summary.py`.

### Task 2: i18n keys (D15)

**Files:**
- Modify: `i18n/en.json`, `i18n/de.json`, `i18n/fr.json`

**Steps:**
- [ ] Add keys: `settings.usage.title`, `settings.usage.total`, `settings.usage.calls`,
      `settings.usage.errors`, `settings.usage.period`, `settings.usage.allTime`.
- [ ] Run `just check-generated` to verify catalog consistency.

---

## Work Package 2 — D15: LLM Audit View (frontend)

### Task 3: Usage page

**Files:**
- Create: `app/capabilities/settings/web/UsagePage.tsx`
- Modify: `app/capabilities/settings/web/routes.tsx` (add route)
- Create: `app/capabilities/settings/web/UsagePage.test.tsx`

**Steps:**
- [ ] TanStack Query hook calling `/api/llm-calls/summary?days=...`.
- [ ] Table: task key, calls, errors. Totals row.
- [ ] Date-range selector (7 / 30 / 90 / all).
- [ ] Register route in `routes.tsx`.
- [ ] Unit test for the query hook.
- [ ] Run `just test-frontend`.

---

## Work Package 3 — A3: i18n Lazy-Loading (generator)

### Task 4: Restructure generator

**Files:**
- Modify: `scripts/generate_capabilities.py` (`typescript_catalogs`)

**Steps:**
- [ ] Change output: `catalogs.ts` exports only `locales` array and `Locale` type
      (no runtime catalog data, no static imports).
- [ ] Generate per-locale modules `catalogs.<locale>.ts` exporting a `catalog`
      object (dynamic-importable).
- [ ] Derive `MessageKey` from a type-only import of the en JSON.
- [ ] Run `just generate` and verify `check-generated` passes.
- [ ] Run `just check` and `just test-frontend`.

### Task 5: Runtime change

**Files:**
- Modify: `web/lib/i18n.ts`

**Steps:**
- [ ] Add module-level cache for loaded catalogs.
- [ ] `t()` uses cached catalog or falls back to en; triggers async load.
- [ ] On locale switch, load the new locale and re-render.
- [ ] Source locale (en) eagerly loaded.
- [ ] Unit tests for fallback behavior.
- [ ] Run `just test-frontend`.

---

## Verification

- [ ] `just check` green
- [ ] `just check-generated` green (no drift)
- [ ] `just test` green
- [ ] `just test-frontend` green
- [ ] `just build` green (bundle size reduction visible)

## Review Focus

- A3: type safety — `MessageKey` must still catch missing keys at compile time.
- A3: no flash of English on locale switch (fallback is acceptable but brief).
- D15: query must be scoped to `user_id` (rule 4).
- D15: no new database table or migration.
EOF