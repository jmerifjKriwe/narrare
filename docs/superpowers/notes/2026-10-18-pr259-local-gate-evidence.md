# PR #259 — Local Full-Gate Evidence (2026-10-18)

Full local gate at `32074f09` + the bandit parity fix on `feature/ci-r1-wave1`
(PR #259, CI R1 waves 1–3). The GitHub Actions PR run is expected to fail-start
on the account billing block (jobs never start, 0 billable minutes — W0-1
class, PO action pending); this local matrix is the authoritative gate evidence.

## Matrix

| Gate | Result |
| --- | --- |
| gate-scripts (architecture/rule checks) | 0 errors · 0 warnings · 0 findings |
| ruff · ruff format | 0 findings · clean |
| pyright (main) · pyright (tests) | 0 · 0 |
| unit | 14,017 passed / 0 failed · coverage 94.71% (post-fix) |
| integration | 920+18 · golden 38 |
| frontend (vitest + chain) | 3,916 passed · chain green |
| E2E | 50 passed + 1 xfail |
| zizmor · actionlint | 0 findings · 0 findings |

"post-fix" = includes this commit's fix: `tests/unit/scripts/test_bandit_scope_parity.py`
helper now resolves the CI Bandit invocation through the composite
`.github/actions/quality/action.yml` (W1-3/W1-4 moved the step verbatim out of
ci.yml job bodies; the helper parsed ci.yml only → 3 red tests, now green with
a loud-zero guard against future moves).

## Deviation — E2E port shift

The local E2E run executed with shifted ports to avoid collision with the
locally running dev stack; the CI workflow port configuration is unchanged.
Port assignment is environment configuration, not test logic — no coverage or
quality impact (all 50 specs passed + 1 xfail as pinned).

## Merge criterion

The wave-PR merge criterion (§15.1, CI R1 event-driven redesign,
`docs/superpowers/specs/2026-10-16-ci-r1-event-driven-redesign.md`) — full
local gate green at the tip that would merge — is **met** by the matrix above.
