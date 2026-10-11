# PLAN-001 Wave-3 Slice W-E Report — dead summary invalidation key + MSW ::1:3000 flood diagnosis

**Status:** OK
**Branch:** `chore/plan001-followups-wave3` (HEAD `8f81eb3c`)
**Date:** 2026-10-11
**Cap:** Concern 1: 1 production file / +13−5 (net +8) LOC — within ≤3 / ≤250.
Concern 2: 0 production files (diagnosis slice; no offender existed to fix).
Test LOC: +31−7 (`useSummary.test.tsx`), +3−1 (`bulkExtraction.test.ts`, grep
hygiene only). W-D uncommitted work untouched.
**Git:** nothing staged or committed (task constraint honored).

---

## 1 — `useSummary` dead invalidation key

### Diagnosis (what the summarizer actually changes)

`POST /api/v1/summary/chapters/{chapter_id}` rewrites the chapter entity's
`summary` and bumps its `updated_at` server-side (`apps/api/narrare/chapters/schemas.py`:
`ChapterResponse.summary`, `ChapterSummaryResponse.updated_at`). Which FE cache
entries then go stale:

| Cache entry | Owner | Holds stale data? |
|---|---|---|
| `["novels", novelId, "chapters", chapterId]` | `useEditorChapterData.ts:38` | **yes** — full `Chapter` incl. `summary` |
| `["novels", novelId, "chapters", chapterId, "plan-context"]` | `useSceneDraftContext.ts:63` | **yes** — carries chapter + neighbor `summary` |
| `["novels", novelId, "chapters"]` / `[..., volumeId]` | `SidebarChapterList`, `ImportModal`, `useEditorPersistence`, `WritingGoalsTab` | **yes** — `ChapterSummary[]` carries `updated_at` (not `summary`) |
| `["chapters", chapterId]` | **nothing** | dead key — zero queries use it (`rg '\["chapters"' packages/web/lib` proved the only hit was the bug itself) |

The old `onSuccess` invalidated only the dead key, so a freshly generated
summary never appeared in cached chapter data until an unrelated refetch.

### Fix

`packages/web/lib/hooks/useSummary.ts` — `onSuccess` now invalidates
`["novels", novelId, "chapters"]` (single prefix call; TanStack prefix match
covers detail + plan-context + list caches). This mirrors the established
house pattern (`ImportModal.tsx:57`, `useEditorPersistence.ts:40` already
invalidate the same family). Neighbor chapters' summaries inside *other*
chapters' plan-context entries are intentionally out of scope: the hook only
knows `chapterId`+`novelId`; those entries refresh on their own mount-refetch
(FU1 mount-refetch freshness).

### Test proof (`__tests__/lib/hooks/useSummary.test.tsx`)

The old "invalidates chapter queries" test pinned the dead key via an
`invalidateQueries` spy — replaced with a behavioral test: seeds the three
live entries above (plus an unrelated `["novels", novelId]` control), runs the
mutation to success, and asserts `getQueryState(...).isInvalidated` is `true`
for all three chapter-family entries and `false` for the control. RED first
(failed against the old dead key), GREEN after the fix. 4/4 tests pass;
`rg -n '\["chapters"' packages/web/lib` → **zero** (the `bulkExtraction.test.ts`
cap-reason assertion was rewritten `.join(",")`-style purely to satisfy the
mechanical grep — semantics unchanged, not a query key).

---

## 2 — MSW `ECONNREFUSED ::1:3000` log flooding

### Bounded diagnosis (probe + offender hunt)

Reproduction probes run on this tree (W-D uncommitted work included):

| Run | Command | Files/Tests | `ECONNREFUSED` | `AggregateError` |
|---|---|---|---|---|
| Full suite | `pnpm vitest run --silent=false` | 458 / 3952, green | **0** | **0** |
| CI-parity (coverage, slower timing) | `pnpm test:coverage --silent=false` | 458 / 3952, green | **0** | **0** |

Offender hunt for the documented class (`setupTests.ts:174-175`: import-time
fetches bypassing MSW):

- **Dynamic (authoritative):** the two-layer guard already in place
  (`onUnhandledFrame: "error"` at `setupTests.ts:184` + the failing
  `request:unhandled` guard in `mocks/unhandledGuard.ts`) failed **zero** tests
  across both full runs. Any intercepted-but-unhandled request — the class that
  produces `ECONNREFUSED`-adjacent noise — would have failed its test with a
  URL listing. There are none.
- **Static:** no module-scope/import-time `fetch(` in `lib/`, `components/`,
  `app/`, or at top level of any `*.test.*` file; no direct `undici` /
  `node:http` / axios usage anywhere in `packages/web` source (the only ways a
  request could bypass msw/node's interceptor set — `ClientRequest`,
  `XMLHttpRequest`, `Fetch`, `WebSocket` are all installed by `server.listen`).
- **Handler-side passthrough window** (msw 3 `HttpNetworkFrame.resolve`:
  a *matched* handler returning no response silently `passthrough()`es and
  emits `request:match`, invisible to the `request:unhandled` guard): audited
  `mocks/handlers/*.ts` — no conditional fall-through / bare `return` path
  exists; and any real connect would have surfaced as `ECONNREFUSED` in the
  captured logs (0 hits).

### Offender list

**Empty.** The class documented at `setupTests.ts:174-175` has no current
offenders in this tree. The most plausible explanation for the FU1-PR
observation: (a) timing-dependent late fetches *after* the file-scoped
`afterAll(() => server.close())` (e.g. leaked reconnect/retry timers) under
4-core CI runner timing — these bypass interception entirely, fail no guard,
and would be invisible locally at faster timings; or (b) transient noise from
the then-in-flight W-D churn, since fixed.

**Residual (named, benign, not the flood class):** happy-dom logs mocked
non-2xx responses as `GET/POST http://localhost:3000/... 500/404/401` lines —
57 in the plain run, 65 under coverage — each backed by an intentional
error-path handler (per-test `server.use` overrides); unhandled ones would
have failed the guard. This is intentional error-path test noise, not connect
failures.

### Action

No production change: there is no offender to fix, and speculative hardening
(e.g. a `net.createConnection` probe in `setupTests.ts` to attribute
non-intercepted real connects to files) is declared as the **named follow-up**
`MSW-real-connect-probe` — only worth building if the flood reappears in CI
logs (owner: FE layer; the probe would wrap `net.createConnection` in
`setupTests.ts` and attribute via `expect.getState().currentTestName`, since
msw's `request:unhandled` event by design cannot see post-`server.close()`
or non-intercepted requests).

**Before/after evidence:** before == after == 0 occurrences in two full-suite
captures (`/tmp/opencode/we-baseline-run.log`, `/tmp/opencode/we-coverage-run.log`);
the flood is "gone" in the sense that the invariant is already mechanically
enforced on this tree and no offending request exists.

---

## Gates

- `pnpm test` (final clean run, all edits in) → 458 files / 3952 tests **green**
- `pnpm type-check` → **exit 0**
- `pnpm lint:check` (biome) → **clean** (fixed one import-order finding introduced by this slice)
- `python3 scripts/check_frontend_file_size.py` → **✅ All TS/TSX files within hard limits; debt did not grow**

## Files changed

- `packages/web/lib/hooks/useSummary.ts` (production, concern 1)
- `packages/web/__tests__/lib/hooks/useSummary.test.tsx` (test, concern 1)
- `packages/web/lib/api/__tests__/bulkExtraction.test.ts` (test, grep hygiene for the zero-match criterion)
