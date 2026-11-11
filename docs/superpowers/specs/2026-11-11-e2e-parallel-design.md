# E2E parallel, one dev server — design

Date: 2026-11-11
Status: approved by the owner in the session ("1+2 umsetzen"). The owner asked
for more workers on CI than locally; the attempt failed on timing-sensitive
assertions, so both stay at two (#775). This design supersedes the 2026-10-31
cadence design's "no parametric ports, no xdist" non-goals for the local harness
and the CI matrix job; the matrix itself, the per-capability split and what E2E
proves stay as they are.

## Intent

The browser suite is the slowest gate on both sides: locally `just test-e2e all`
runs every test in one process, and on CI the pacemaker is the `writing` job
(506 s in nightly run 43009447446), so the E2E matrix is the wall clock of a PR.

Measured on 2026-11-11, 4 cores / 9 GB:

| run | tests | wall | CPU |
|---|---|---|---|
| knowledge, serial | 39 | 251 s | 85 s user + 19 s sys |
| setup, serial | 5 | 24 s (stack start 5 s) | — |
| CI writing (nightly) | 75 | 506 s | — |

The suites wait on the browser and on the dev server, not on the CPU: ~0.4
cores on average. That is what makes more workers worth it, and what sets the
ceiling — three Chromium, Vite and uvicorn processes already sit on a 4-vCPU
runner.

Two fixed costs were measured separately:

- Each E2E file starts its own stack (schema from the models, uvicorn, `pnpm
  dev`, port waits): 5–9 s per file, 2.5–4.5 min of a full serial run.
- Each test loads the unbundled Vite graph cold: ~4 s per test on average, and
  no single test dominates (slowest knowledge test 13 s).

## Decisions

### 1. pytest-xdist, two workers

`just test-e2e [scope] [workers]` runs with `-n 2` unless
`NARRE_E2E_WORKERS` or the second argument says otherwise; `_e2e.yml` exports
`NARRE_E2E_WORKERS=2` for the per-capability job. The worker count is a
parameter, not a second recipe.

A third worker was tried and is shelved (#775): on a 4-vCPU runner it made
timing-sensitive layout and focus assertions flake — a label measured 36 px off
its row, a dialog still open after Escape, a drag that did not survive a reload
— while the same suites pass on a rerun and at two workers. The CI gate stays
reliable until those assertions wait for the fact they measure.

- Ports: a worker's pair is the configured pair moved by `WORKER_PORT_SPACING`
  (ten) per worker. `stack.py` derives it from `PYTEST_XDIST_WORKER` at import,
  so `-n 2` gives gw0 8000/3100 and gw1 8010/3110, and an explicit
  `NARRE_E2E_API_PORT=8199` moves the ladder to 8199/8209.
- Databases already isolate per process (`testsupport` mints a per-process
  token), so a worker needs no new database code — a worker *is* a process.
- The Vite child gets the worker's ports pinned, never the run's original
  environment: forwarding the unshifted pair would bind the neighbour's port.

### 2. Attached runs stay serial

`NARRE_E2E_ATTACH` drives one running instance with exactly one database; two
workers would race in it. The recipe forces `-n 0`, and `stack.py` refuses a
worker index above zero at import, so the container gate cannot silently turn
into a race when someone calls pytest directly.

### 3. One Vite dev server per pytest process

The stack still owns the API and its database per capability module — they are
the state under test — but the web server is stateless and the slowest piece to
start, so the first stack starts it and every later stack reuses it. A
session-scoped fixture in `app/conftest.py` stops it, and that runs in an xdist
worker too. A dev server that died is restarted by the next stack.

### 4. `just test-e2e-file <path>`

One E2E file, node or `-k` selection with `-m e2e --timeout=60` and no
resolver. The inner loop for a browser test; `--lf` and `-k` pass through.

## Rejected

- **A production build for E2E** (build once, `vite preview`). It would cut the
  per-load cost most, but it reverses #634: the dev graph is what proves the app
  under StrictMode's double effects, and preview still needs the cache header
  worked around. A separate dev-stack suite would have to keep that coverage.
- **One stack for the whole run** (API too). Capability databases differ (setup's
  fresh-instance surface, knowledge's provider stand-in), and an API process
  points at one database for its lifetime.
- **`--dist loadscope`.** It keeps a capability on one worker, which restores the
  stack count but gives the pacemaker suite no parallelism — exactly the job that
  needs it.
- **Loosening the expect timeouts** for parallel contention. The five-second
  default is the gate's own budget; a suite that needs more under load is a
  finding, not a configuration.

## Measured after the change

| run | before | after |
|---|---|---|
| knowledge, 2 workers | 251 s | 147 s |
| setup, 2 workers | 24 s | 18 s |
| writing, 2 workers | 506 s (CI, serial) | 329 s |
| all seven suites, 2 workers | ~15 min (sum of the serial suite walls) | 10 min 23 s, 173 tests |

The `before` for writing is the CI job's number: no serial local run was taken,
because knowledge's local wall clock matched CI within 3 % (251 s vs 244 s) and
it is the same 80 tests. The full serial local run was not re-taken either: the
measured serial evidence is knowledge (251 s) and setup (24 s) in the table, and
the local suite walls — CI minus the per-job scaffolding — add up to about
fifteen minutes.

Two workers are worth ~1.5–1.7×, not 2×: each worker pays its own stack starts
and its own cold Vite graph, and the suites were never CPU-bound enough to keep
four cores busy.

The three-worker local run failed twice over: this host had 7 of 9 GB used by
other sessions, workers were restarted and cold page loads ran into Playwright's
30 s navigation timeout; and on the runs where memory held, single UI tests
failed on layout and focus timing and passed on the next run. That is why the CI
setting is two, not three (#775).

**Known limitation.** A worker that dies without a clean session teardown leaves
its stack processes behind, as a crashed serial run always did with the API; the
next run's port wait (`_wait_for_free_port`) names the port and fails in 30 s
instead of pretending to test. The failed local run above was cleaned with a
`kill` of this worktree's `vite`/`uvicorn` processes.

## Non-goals

- No change to what E2E proves, to the fake-at-the-boundary rule, or to the
  per-capability matrix and its aggregating check.
- No new gate and no change to the pre-commit or pre-push hooks.
- No timeout loosening in response to contention.
