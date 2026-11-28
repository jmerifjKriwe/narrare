# A proportional Lane B development path — Change 1

**Status:** approved by the product owner on 2026-11-28. This is a governed
process change, not a Lane B change; the new protocol applies only after this
change merges. This document records Change 1 only.

## Context

Lane B carries bounded fixes, follow-ups, refactors and UI corrections inside
one capability folder. Its protocol today names one whole-diff review but does
not say how many fix rounds follow, when the gate runs, or what evidence is
kept. The result is either a second review layer Lane B does not need or a
review whose findings are deferred to a later change.

Standing rule 2 binds every capability to a green E2E. Read literally, it also
demands an E2E from tools no user can reach: demos, generators, screenshot and
showcase harnesses, and CI hooks.

## Change

### 1. Lane B's review loop

- One independent review of the whole diff against `main` replaces the separate
  task review and the final review. That first review pins tree hash A.
- The implementer runs the full `just verify` for the affected scope once,
  before the first review, and records the exact command and output.
- One consolidated fix round answers every `Important` and `Nit` finding. No
  finding is deferred: the change's scope is the whole diff. The fix round
  produces tree hash B.
- The scoped re-review reads only the diff A→B plus the findings it answers —
  one re-review, at most. It does not re-read tree B as a whole.
- After the fixes, only the gate covering each fixed path runs; a second full
  `just verify` is not owed.
- The coordinator commits only after the review is green.
- Evidence is temporary and not committed: `.superpowers/sdd/lane-b-<slug>/`
  holds tree hashes A and B, the diff A→B, the exact commands and output, the
  review, the fix round and the re-review.

### 2. The E2E boundary

Standing rule 2 proves user-reachable app behavior. A maintainer- or
developer-only tool — a demo, generator, screenshot or showcase tool, or a CI
hook — has no user-reachable path and owes unit or integration tests, never an
E2E. The narrow exception is a change to `.github/workflows/` or
`.github/actions/`, which owes the smoke suite `settings` as proof the harness
runs.

### 3. Mirrors

`TESTING.md` and `REVIEW.md` state the same boundary. A CI-definition change is
the narrow harness exception: it owes the smoke suite `settings`, not every
capability suite.

### 4. Dead showcase tooling

No showcase E2E spec exists in the tree. Remove the unused `showcase` pytest
marker from `pyproject.toml`, the `and not showcase` filter from `justfile`, and
the dead showcase instructions from
`docs/design/stitch/SCREENSHOT-COMPARISON.md` and `scripts/side_by_side.py`.

## Non-goals

- The architecture spec
  `docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md` is
  unchanged.
- This change does not run as Lane B, whatever its file and line counts; it is a
  governed process change.
- No new gate, test, registry or mandatory document is introduced.

## Acceptance

- `AGENTS.md` names all six elements of the Lane B loop.
- `CONSTRAINTS.md` rule 2, `TESTING.md` and `REVIEW.md` agree on reachability
  and the `settings` harness exception.
- `rg -n "showcase" pyproject.toml justfile scripts/side_by_side.py` returns no
  matches, and `SCREENSHOT-COMPARISON.md` contains no dead showcase command or
  E2E path.
- `just verify` is green once before review; the review and one scoped
  re-review are green; the commit carries the `Assisted-by` trailer.
