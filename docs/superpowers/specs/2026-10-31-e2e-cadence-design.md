# E2E cadence and CI parallelism — design

Date: 2026-10-31
Status: approved by the human partner in the planning session (variant 1 + CI variant A,
spec change as a dated correction, not an ADR).

## Intent

The E2E suite is the only place where "works" has a definition (spec §7). Mandated after
v1 shipped UI that did not work, it must stay a real gate — but it is the slowest gate in
the pipeline: on 2026-10-31 the full run took 8:41 of the CI wall clock, while every other
job finished within 1:30. The local full gate (`just verify`) pays the same suite.

Goal: keep the guarantee (every capability proven through the real UI before merge, all of
them periodically), while making the loop fast where speed can be had without weakening it.

## Measured baseline (run 41177559473, e2e job, all suites)

| part | seconds |
|---|---|
| job scaffolding (20 s playwright install, 12 s postgres container, actions) | 48 |
| stack handovers: 18 test files × 9.2 s (schema from models, uvicorn, `pnpm dev`, port waits) | ~165 |
| the tests themselves, 76 browser tests, avg 3.8 s, slowest 13 s | ~289 |
| test step total | 467 |
| job wall clock | 8:41 |

The fake LLM provider streams with `asyncio.sleep(0)`; there is no artificial pacing to
shorten. No configuration knob recovers the 289 s or the 165 s. The only real lever is
running suites concurrently, and the harness blocks that today: `web/vite.config.ts` binds
`strictPort: 3100`, and ~100 `page.goto("http://127.0.0.1:3100/…")` calls are literal, so two
suites cannot share a runner. (`stack.py` reads `NARRE_E2E_API_PORT`/`NARRE_E2E_WEB_PORT` and
claims in its docstring that a busy port needs no code edit — today that is false.)

## Options considered

1. **Status quo.** 8:41 per push; a `main` push repeats exactly what its PR ran.
2. **Local: no E2E in `just verify`; E2E only by explicit call.** Cheapest, but the default
   gate stops proving the UI — the v1 failure mode. Rejected.
3. **Local: affected by default, all on demand (chosen).** `just verify` runs the suites the
   change touches, mirroring CI; `just verify all` for risky changes.
4. **CI: matrix per capability with an aggregating `e2e` check (chosen).** Wall clock =
   longest suite (writing, ~4:10). No product file touched; public repo, so the six runners
   cost nothing. Keeps the required check name, so the ruleset stays as it is.
5. **CI: parametric ports + parallel processes inside one job.** Same wall clock, keeps the
   check name without an aggregator, but rewrites ~100 test call sites and the vite config —
   a daily-working test harness changed for a CI speedup. Rejected for now; the dead port
   knobs become a follow-up issue, which is that route's precondition.

## Decisions

### One filter, two callers

`scripts/affected.py` (stdlib only, no app imports) replaces the inline bash in the `changes`
job and is used by `just`. It resolves a path list to capability names.

Path table (single source of truth):

- **shared → all suites**: `app/kernel/`, `app/api/`, `app/generated/`, `web/`, `i18n/`,
  `app/conftest.py`, `app/capabilities/conftest.py`, `justfile`, `pyproject.toml`, `uv.lock`,
  `pnpm-lock.yaml`, `.github/workflows/ci.yml`
- **capability → that suite**: `app/capabilities/<name>/` where `<name>` is an existing
  capability directory
- **inert → none**: `docs/`, `README*`, `CHANGELOG.md`, `LICENSE`, `AGENTS.md`,
  `CONTRIBUTING.md`, `TESTING.md`, `scripts/`, `docker-compose*.yml`, `.pre-commit-config.yaml`,
  `.release-please-manifest.json`, `.github/` (except `ci.yml`)
- **anything else → all** (fail-open)

Two holes in today's inline filter, closed by the move:

- `app/conftest.py` matches nothing today → a PR touching it runs no E2E. It decides the
  test database for the whole suite.
- `app/capabilities/conftest.py` matches as capability `conftest.py` today → the job calls
  `app/capabilities/conftest.py/e2e/`, which does not exist, and the E2E job goes red.

Fail-open is observable: every fallback prints its reason (stderr locally, `::notice::` in
CI) and yields all suites.

### Local scope

`just test-e2e [scope]` and `just verify` share one resolver. `scope` is `affected`
(default), `all`, or a capability name. Base for `affected`: `merge-base HEAD <default
branch>`, resolved from `refs/remotes/<remote>/HEAD` (this repository's remote is `narrare`),
plus the working tree including untracked files. An unreadable base is not "nothing
changed": it is all suites. An empty result prints one line and runs no browser. Recipe
count stays 22 — a parameter, not a new recipe.

### CI

- `changes` emits `capabilities` as a JSON array (`[]` when none, `all` expanded to the six
  names). A push to `main` emits `[]`: the merge tree is the tree the PR just tested, so the
  push repeats nothing. Direct pushes to `main` get their E2E from the nightly.
- `e2e-suites` is a matrix job over that array (`fail-fast: false`, name `e2e (<name>)`),
  each entry running `app/capabilities/<name>/e2e/` with `-m e2e --timeout=60`.
- `e2e` is the aggregator and the only required check. Green only if: `changes` succeeded,
  and either the list was legitimately empty, or every matrix entry succeeded. Red if
  `changes` failed, or any entry failed or was cancelled. This closes an existing hole: a
  failed `changes` job currently leaves `e2e` skipped, and a skipped required check passes.
- Nightly uses the same matrix with all six entries: still every suite, just in parallel.
- Expected: ~4:10 instead of 8:41 per PR that owes a browser; writing becomes the pacemaker.

### Documentation

Spec §6 (job list and "Runs on PR and on push to `main`"), §7 scheduling sentence, §8 bullet,
and a dated correction note in §2 for the job count (six → seven definitions, aggregator
named). `AGENTS.md` Verify line, `CONTRIBUTING.md`, `TESTING.md`.

The dead port knobs in `app/kernel/testing/stack.py` become a `follow-up` issue under index
#308 ("Reviews and audits outside a wave").

## Non-goals

- No change to what E2E proves, to the fake-at-the-boundary rule, or to the nightly's
  "everything" guarantee.
- No parametric ports, no xdist, no test-harness rewrite.
- No new recipe, no new dependency, no new gate.

## Anti-goals (would make this a failure even if the workflow is green)

- A path the filter does not recognise silently running nothing.
- A green `e2e` check while no browser ran and the change owed one.
- A new capability whose suite runs but does not block its merge.
- Local `verify` proving less than CI on the same tree.

## Left to the builder

Exact YAML for the matrix and the aggregator step, the bash that reads `needs`, the notice
copy, and the wording of the spec corrections. Everything else is pinned in the plan.
