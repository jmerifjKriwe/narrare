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
| Backend unit/integration | pytest (async) | Repositories, services, providers, parsing | Real Postgres (`narrare_v2_test`) |
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

- `just check` — lint and types (ruff, pyright, tsc).
- `just test` — backend integration suite.
- `just test-frontend` — vitest unit suite.
- `just test-e2e` — capability E2E suite.
- `just verify` — all of the above plus the production build.

CI runs all four on every PR and every push, plus the production build; the E2E
narrows to the capabilities a change touches. All of them must pass. No new gate or
tool is introduced by this document — it states expectations, not mechanisms.

## Data and fixtures

- Backend tests use the real test database (`narrare_v2_test`), reset per
  session. No in-memory substitutes.
- Frontend tests mock only the API client; the logic under test runs unmocked.
- E2E suites create their own databases; see the capability conftests.

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