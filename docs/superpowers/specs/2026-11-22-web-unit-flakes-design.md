# Design: Web-Unit-Test-Flake Stabilization

## Problem
The web unit suite (Vitest, 67 files) intermittently flakes under full-suite
load. Issue #908 (zen exit-flush guard) is the open representative; its
root cause is unconfirmed and latent. Contributing factors:

- 67 isolated forks (one per file), ~2.4 s startup each, on a 4-core box.
- Inconsistent wait budgets: only 12/67 heavy DOM files set
  `asyncUtilTimeout=5000`; the rest rely on the 1 s default.
- Timing-sensitive chains (ProseMirror typing → flush → guard → focus return)
  assert intermediate state synchronously.

## Approach
1. Standardize wait budgets: every heavy DOM file either sets
   `asyncUtilTimeout=5000` with a documented reason, or has no timing-sensitive
   waits. (No global raise; no `--no-isolate`, which breaks 488 tests via
   cross-file leakage.)
2. Convert the zen exit-flush guard's synchronous assertions to condition-based
   waits; give the focus-return wait an explicit 10 s ceiling with a matching
   test timeout, since it depends on React's async commit.
3. Cap Vitest concurrency to 2 workers under CI to reduce scheduling jitter.

## Non-goals
- Disabling isolation globally.
- Raising timeouts without understanding the failing assertion.
- Backend/E2E flakes (separate issues).

## Lane
Cross-cutting test-infra change; no new user-visible surface, no new route,
endpoint, or schema. E2E gate unaffected.