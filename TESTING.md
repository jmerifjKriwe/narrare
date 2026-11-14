# Testing

Narrare's test strategy. The authoritative gate is the end-to-end suite;
unit and integration tests exist to make failures cheap to find and fix.

## Philosophy

- **E2E is the gate.** A capability is done when a green E2E drives the real
  UI, the real backend and the real database. Nothing else counts as "done".
- **Unit and integration tests are leverage, not gates.** They exist to catch
  regressions in logic cheaply and to document intent. They do not replace E2E.
- **No coverage percentage target.** Coverage is a diagnostic, not a goal.
  New logic with state or parsing ships with a test in the same commit; review
  checks that critical logic is not left untested.
- **No mocks of the database.** Backend tests run against a real Postgres.
  In-memory fakes drift from production behavior and are not permitted.

## Layers

| Layer | Tool | Scope | Database |
|---|---|---|---|
| Backend unit/integration | pytest (async) | Repositories, services, providers, parsing | Real Postgres (per-run database) |
| Frontend unit | vitest | Logic with state or parsing (stream parser, autosave, i18n pluralization, routing params, pub/sub seams) | None (API client mocked) |
| End-to-end | pytest + Playwright | One spec per capability, real browser + API + DB | Real Postgres (per-suite database) |

## What is tested where

| Concern | Layer | Rationale |
|---|---|---|
| Stream-frame parsing, autosave debounce, i18n pluralization | Frontend unit | Pure logic; E2E covers it only indirectly and slowly |
| Routing params and validation | Frontend unit | Type-level plus runtime checks |
| Pub/sub seams (proposal bus, active chapter) | Frontend unit | Stateful, easy to regress, hard to observe in E2E |
| Repository queries, service logic, provider streaming | Backend integration | Needs real SQL and real HTTP shapes |
| User flows (writing, chat, setup, extraction, review) | E2E | The gate; covers wiring across all layers |

## What is not tested

- Render-only components with no logic.
- CSS, layout, visual styling.
- Code already covered by E2E where a unit test would only duplicate it.

E2E covers these sufficiently; adding unit tests would add maintenance cost
without catching new failures.

## Mandatory unit tests

Logic with state or parsing **must** ship with a unit test. Concretely:

- A stream reader, parser, or frame decoder.
- An autosave, debounce, or retry mechanism.
- A pluralization, formatting, or locale rule.
- A pub/sub bus, state store, or reducer.
- A routing param parser or validator.

Pure rendering and wiring do not require unit tests.

## Gates and CI

- `just check` — lint and types (ruff, Biome, pyright, tsc).
- `just check-generated` — regenerates the capability views, the OpenAPI document,
  the typed client and the docs index; fails if the committed files change (CI
  only: `pnpm dlx` needs the network).
- `just test` — backend integration suite.
- `just test-frontend` — vitest unit suite.
- `just test-e2e` — the E2E suites the change touches (`all`, or a capability name, for more).
  Two workers when the machine has 6 GB available, one below that (`NARRE_E2E_WORKERS`
  or the second argument overrides); each worker owns its own port pair and database.
- `just test-e2e-file <path|node>` — one E2E file or node, with the suite's marker and
  timeout and no resolver: the inner loop for a browser test (`--lf` passes through;
  just joins the arguments unquoted, so a `-k` selection must be a single word).
- `just fuzz [seconds]` — a bounded Atheris run over the interchange parser
  (advisory; weekly in CI via `fuzz.yml`, not part of `verify`).
- `just verify` — check, test, test-frontend and the E2E, plus the production
  build, with the E2E narrowed the same way; it deliberately omits the CI-only
  `check-generated`.
- `just test-frontend-changed` — only the web tests the working tree touches;
  the inner loop for frontend work. Full suite via `test-frontend`.

CI runs `just check`, `just check-generated`, `just test` and `just test-frontend`
on every PR, plus the production build; the E2E narrows to the capabilities a
change touches and runs in parallel per capability behind one `e2e` check. A push
to `main` owes no E2E — the merge tree is the tree the PR tested — and the nightly
runs every suite, covering direct pushes too, when `main` moved.

**The rebuild interim (W0).** The capability UIs were demolished for the
frontend rebuild, and their E2E suites left with them — a suite tests a
screen, and the screens are gone. Each rebuilt screen ships its own suite
again as it lands, setup first (W2); until then every change resolves to
zero suites and `just test-e2e` prints the interim reason instead of
starting a browser. The gate's rules are suspended, not rewritten: the
narrowing, the workers and the fake-provider rule are unchanged and return
with the setup suite.

All of them must pass. No new gate or
tool is introduced by this document — it states expectations, not mechanisms.

## Data and fixtures

- Backend tests get the real test database named per run — worktree token plus
  a per-run token, so two pytest runs never share tables — reset per session. No
  in-memory substitutes.
- The test server defaults to the compose stack (`localhost:5433`); when
  another checkout holds that port, `NARRE_TEST_DATABASE_URL` re-aims every
  suite and every E2E stack at its own Postgres; the per-run names are minted
  on whichever server that door opens.
- Frontend tests mock only the API client; the logic under test runs unmocked.
- E2E suites create their own databases and their own port pair per xdist worker;
  see the capability conftests and `app/kernel/testing/stack.py`.

## Naming and structure

- Backend: `test_*.py` beside the code it tests, under the capability or
  kernel folder.
- Frontend: `*.test.ts` / `*.test.tsx` beside the source file.
- E2E: `app/capabilities/<name>/e2e/test_*_e2e.py`.

## Review checklist

When reviewing a change, check:

- [ ] New logic with state or parsing has a unit test.
- [ ] No database mock was introduced.
- [ ] E2E still passes for touched capabilities.
- [ ] Frontend changes that add state have corresponding vitest coverage.

## Related

- `AGENTS.md` — capability rules and the E2E gate.
- `CONTRIBUTING.md` — branch model, commit convention, PR process.
- `docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md` — structure and boundaries.