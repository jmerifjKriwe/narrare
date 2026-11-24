# Plan: Web-Unit-Test-Flakes (issue #908) — condition-based waits, no isolation loss

## Goal
Reduce flakiness of the web unit suite (Vitest) under full-suite load without
losing test isolation. Issue #908 (zen exit-flush guard) is the open
representative; the cause is unconfirmed and latent (1 failure in 6 full runs).

## Evidence gathered (2026-11-22)
- Full run: 67 files, 1387 tests, ~136 s, 0 failures ×3.
- `--no-isolate`: 488 failures / 31 files (cross-file leakage from module-level
  `vi.mock`, shared singletons, `Range.prototype` patches, fake timers).
- `--maxWorkers=1`: 1387 tests green, 153 s (+12 %).
- Only 12/67 files set `asyncUtilTimeout=5000`; the rest rely on the 1 s default.

## Why not `--no-isolate`
It is not a one-time refactor. Disabling isolation makes "side-effect-free tests"
a **permanent invariant** for every future test: every module-level mock,
singleton mutation, timer fake, DOM/global patch must be restored per file.
The repo's tests deliberately use those side effects, so the cost is ongoing
discipline, not a single migration. And it does not address the actual failure
mode (timing budgets under load) — it trades contention flakes for leakage
flakes that are harder to attribute. Rejected on cost/benefit.

## Tasks

### T1 — Capture 908's assertion frame
Run 5–10 full `pnpm --dir web test` runs with verbose reporter; extract the
failing `it` name and assertion. Do not raise timeouts before this.
- Gate: a captured frame names the failing assertion (focus return, alertdialog,
  contenteditable, …).

### T2 — Audit wait budgets
List all `findBy*`/`waitFor` calls in the 12 heavy DOM files and the 55 others;
classify as (a) state-condition wait, (b) arbitrary budget. Output a table
(file, count, kind).
- Gate: no unclassified waits in the heavy files.

### T3 — Convert timing-sensitive chains (writing first)
Rewrite the zen-guard chain in `WorkspacePage.test.tsx` and the autosave/flush
paths in `ZenMode`/`workspace` tests to condition-based waits (wait for the
actual state, not the 5 s budget). Keep the 5 s outer `asyncUtilTimeout` as a
safety net with a comment explaining why.
- Gate: the converted test still fails fast when the condition never holds.

### T4 — Standardize the budget policy
Decide per file: either raise `asyncUtilTimeout` to 5000 with a documented
reason (heavy jsdom render), or rely on condition waits with the default. No
silent defaults in heavy files. Document the rule in TESTING.md.
- Gate: every heavy DOM file either sets the budget with a reason or has zero
  timing-sensitive waits.

### T5 — CI stability cap
Add `maxWorkers: 2` (or 1) to the web unit invocation in CI only, leaving
local dev at the default. Measure the delta.
- Gate: CI run green with the cap; duration recorded.

### T6 — Verify
5 full runs + 1 serial run after T3/T4, all green. Re-open 908's trigger
check: no recurrence in the 5 runs.
- Gate: `just test-frontend` green 5×; 908 stays closed or gets a concrete fix.

## Out of scope
- Disabling isolation globally.
- Raising timeouts without understanding the failing assertion.
- Backend/E2E flakes (separate issues, mostly closed).

## Lane
Crosses multiple capability folders and test infra → Lane A (design doc +
this plan). No new user-visible surface; the E2E gate is unaffected, but the
capability E2E suites still must run green per the branch.
