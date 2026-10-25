---
description: Review the whole branch against the spec and the ledger before merge
agent: reviewer
---

Review the whole branch before merge. Merge base or branch: $ARGUMENTS

Merge base: !`git merge-base main HEAD` — verify it and use the one you name.

The change is `<merge-base>..HEAD`. Read the spec at
`docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md` and, when
the branch touches `web/`, `docs/superpowers/specs/2026-10-22-frontend-design.md`.
Read the plan the dispatch names. Read the ledger at the path the dispatch names
(or `.superpowers/sdd/<plan-basename>/progress.md`): the settled rulings, the
parked findings, and the deferred minors. Triage which deferred items must be
fixed before merge.

This is the broad review: architecture, seams between tasks, generated artifacts
against their sources, merge integrity, production readiness. The per-task
reviews already covered the tasks; do not re-review them line by line, but do
not assume they caught a cross-task defect.

Report in your agent's output format, plus this section after `### Assessment`
and before the final three-line block:

## Merge
**Verdict:** PASS / FAIL
**Merge base:** <sha>
**Commits:** <n> — <base7>..<head7>
**Notes:** conflicts, generated-artifact drift, files changed outside the plan.
