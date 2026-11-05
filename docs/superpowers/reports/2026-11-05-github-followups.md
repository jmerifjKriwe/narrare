# GitHub platform follow-ups — wave report

**Date:** 2026-11-05 · **Branch:** `ci/607-github-followups` · **Index:** #607
**Plan:** `docs/superpowers/plans/2026-11-05-github-followups.md`
**Design:** `docs/superpowers/specs/2026-11-05-github-followups-design.md`

One section per task, appended when the task lands. Every number here was read
from the command named next to it, not inferred.

## Task 0 — baseline

Branch renamed from `follow-up/607-github-platform` to
`ci/607-github-followups`; the worktree fast-forwarded to `narrare/main`
673306b3 ("Dependabot accepts the Actions cooldown again"). `git status
--porcelain=v1` empty before the first edit.

`gh run list --workflow scorecard.yml --limit 5` — three green `main` pushes:

| Run | Head | Result |
|---|---|---|
| 42088177236 | 673306b | success |
| 42086972305 | b38f11e | success |
| 42080606005 | ddd1b31 | success |

`gh api …/code-scanning/analyses` — nine Scorecard analyses, three categories
(`supply-chain/local`, `supply-chain/branch-protection`,
`supply-chain/online-scm`) on `refs/heads/main` per run, newest 2026-11-05T18:51:24Z.

`gh run list --workflow nightly.yml --limit 5` — one run, 42054755419, failed in
0 seconds on branch `ci/gate-proof`. No `schedule` and no `workflow_dispatch` run
of `nightly.yml` has ever completed.

`gh api repos/jmerifjKriwe/narrare --jq .security_and_analysis`:

```
secret_scanning                       enabled
secret_scanning_push_protection       enabled
secret_scanning_non_provider_patterns disabled
secret_scanning_validity_checks       disabled
dependabot_security_updates           enabled
```

`rg -c "zizmor: ignore\[self-repository\]" .github/workflows` — 14
(`ci.yml` 5, `nightly.yml` 6, `_lint.yml` 1, `_test.yml` 1, `_e2e.yml` 1).
`rg -c "1\.7\.7" .github/workflows docs/architecture/github.md` — 16
(`ci.yml` 6, `nightly.yml` 6, `_lint.yml` 1, `_test.yml` 1, `_e2e.yml` 1,
`docs/architecture/github.md` 1).

Cost baseline, `main` CI run 42088177589 (`673306b`): `frontend` 18:50:55 →
18:51:47 (52 s), `build` 18:50:55 → 18:51:17 (22 s). Both include checkout and
the full setup composite.

## Task 1 — setup `python: false` (#606)

## Task 2 — Playwright cache (#599)

## Task 3 — Postgres digest (#603)

## Task 4 — PGDG retry (#610)

## Task 5 — dev audit (#597)

## Task 6 — tool pins bumped

## Task 7 — monthly pin check (#598)

## Task 8 — one copy of the verdicts (#605)

## Task 9 — the three records (#596, #600, #602)

## Task 10 — the four proofs (#604)
