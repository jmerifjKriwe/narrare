# Spec: LLM Audit View and i18n Lazy-Loading

**Date:** 2026-11-09
**Status:** Draft
**Author:** Coordinator
**Implements:** Audit follow-up items D15 (LLM-Call-Audit-View) and A3 (i18n Lazy-Loading)

---

## 1. Problem

### D15 — LLM Audit View

Every LLM call is recorded in the `llm_calls` table (since WP0-A): tokens, model,
status, task key, novel id, timestamp. But this data is invisible to the user.
There is no UI surface that shows "how much LLM usage has happened, by which
capability, with what cost". The data exists; the view does not.

### A3 — i18n Lazy-Loading

`web/lib/generated/catalogs.ts` statically imports all locale catalogs (en, de, fr)
for all capabilities. The result is a 125 KB `i18n-*.js` chunk that is eagerly
loaded on every page load, even though only one locale is active at a time. Two
of three locales are wasted bandwidth on every session.

## 2. Goals

### D15
- A read-only endpoint `/api/llm-calls/summary` returning aggregate usage
  (call count, token totals, error count) grouped by capability and task key,
  scoped to the current user.
- A UI view (reachable from Settings) showing the aggregates in a table,
  with a date-range filter (last 7 / 30 / 90 days, all time).
- No new database table, no new migration, no new standing rule.

### A3
- Only the active locale's catalog is loaded at runtime; other locales are
  fetched on demand when the user switches language.
- The `MessageKey` type (compile-time key checking) is preserved.
- `just generate` and `check-generated` continue to pass.
- No change to the i18n JSON source format or to the generator's validation
  (missing key = build error).

## 3. Non-Goals

- D15: no cost estimation (cost_usd is NULL until WP2's catalog). No export.
  No per-call detail view (summary only).
- A3: no streaming/chunked loading. No service worker caching. No change to
  the overlay (formality) loading strategy beyond mirroring the locale approach.

## 4. Design

### D15 — Backend

New router `app/kernel/llm/router.py` (or added to an existing kernel router)
with:

```
GET /api/llm-calls/summary?days=7|30|90|0
```

Returns:
```json
{
  "period_days": 7,
  "totals": { "calls": 42, "errors": 3 },
  "by_task": [
    { "task_key": "writing.continuation", "calls": 20, "errors": 1 },
    { "task_key": "chat.ask", "calls": 15, "errors": 2 },
    ...
  ]
}
```

Implementation: a single SQL query aggregating `llm_calls` by `task_key`,
filtered by `user_id` and `created_at >= now() - interval`. Uses the scoped
repository base (rule 4). `days=0` means all time.

### D15 — Frontend

- New route `/settings/usage` (or a section on the existing settings page)
  rendered as a TanStack Query component.
- Table: task key, calls, errors. Totals row at the bottom.
- Date-range selector (radio or select): 7 / 30 / 90 / all.
- i18n keys: `settings.usage.title`, `settings.usage.total`, etc. (en/de/fr).

### A3 — Generator Change

The generator (`scripts/generate_capabilities.py`, `typescript_catalogs`) currently
produces one `catalogs.ts` with static imports of all locales. Change to produce:

1. A `catalogs.ts` that exports only the `Locale` type and `locales` array
   (no runtime catalog data).
2. Per-locale modules `catalogs.<locale>.ts` (or `catalogs/<locale>.ts`) that
   export a `catalog` object, loaded via dynamic `import()`.
3. The `MessageKey` type is derived from the source locale's JSON directly
   (type-only import), preserving compile-time key checking.

### A3 — Runtime Change (`web/lib/i18n.ts`)

- `t()` becomes: if the active locale's catalog is loaded, use it; otherwise
  fall back to the source locale (en) and trigger an async load.
- A module-level cache holds loaded catalogs.
- On locale switch, trigger load of the new locale; re-render when ready.
- The source locale (en) is always eagerly loaded (type source + fallback).

### A3 — Bundle Impact

Expected: initial bundle drops by ~80 KB (gzipped) — the two non-active
locales are no longer in the main chunk. They load on demand (~40 KB each).

## 5. Constraints

- No new standing rule, checker, hook, or required field (CONSTRAINTS §8).
- Generated files are regenerated with `just generate`, never hand-edited.
- `check-generated` must pass after the change.
- English in code/tests; user-visible text in en/de/fr.
- Every user-owned row carries `user_id` (D15 query filters by it).
- No new database table or migration.

## 6. Risks

- A3: the type system relies on `keyof typeof catalogs.en`. If the generator
  stops emitting `catalogs`, the type derivation must move to a type-only import
  of the en JSON. This is the riskiest part — needs careful testing.
- A3: `t()` is called synchronously in many places (including outside React).
  If a locale isn't loaded yet, falling back to en is correct but may show
  English briefly. Acceptable for a language switch (rare event).
- D15: the `llm_calls` table may be large for heavy users. The summary query
  uses `GROUP BY task_key` with a date filter — should be fast with an index
  on `(user_id, created_at)`. May need an index migration (rule: change init,
  recreate DB — no Alembic).

## 7. Open Questions

1. Should D15 live under `/settings/usage` or as a separate top-level route?
2. Should A3's dynamic imports use Vite's `import()` (automatic code splitting)
   or explicit `import()` with a loading state?
3. Should the active locale be persisted so the lazy load happens once per
   session, or re-loaded on every page navigation?
EOF