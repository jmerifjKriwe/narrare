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

The composite gained a `python` input (default `"true"`); `astral-sh/setup-uv`,
`actions/setup-python` and the `uv sync --locked` step carry
`if: inputs.python != 'false'`. `extractions/setup-just` stays ungated — every
job but the nightly `audit` runs a `just` recipe, and one ungated install keeps
the composite a single answer.

Four call sites pass `with: { python: "false" }`: `frontend` and `build` in
`ci.yml`, and `frontend` and `build` in `nightly.yml`.

Gates, run 2026-11-05:

```
docker run … rhysd/actionlint:1.7.12 -color        → exit 0, no output
uvx zizmor==1.32.0 .github/workflows .github/actions →
  No findings to report. Good job! (15 ignored, 27 suppressed)   → exit 0
```

Wall clock: the baseline is `main` run 42088177589 (`frontend` 52 s, `build`
22 s). The after is the PR run; its step list must show no
`Sync Python dependencies` step in either job. Recorded in the proof section.

## Task 2 — Playwright cache (#599)

The browser cache keeps the exact key
`${{ runner.os }}-playwright-${{ hashFiles('uv.lock') }}` and gains
`restore-keys: ${{ runner.os }}-playwright-`. The comment above it was wrong
after the change ("a stale browser can never match a new lock") and now says
what happens: a restore may hand back the previous browser, `playwright install`
adds the one the new lock names, and a Playwright bump still saves under a new
key instead of overwriting the old one.

Gate, run 2026-11-05:

```
docker run … rhysd/actionlint:1.7.12 -color → exit 0, no output
```

The cache-step proof is the PR's e2e run; recorded in the proof section.

## Task 3 — Postgres digest (#603)

`pgvector/pgvector:pg17` resolves to the index digest
`sha256:7d0a41464797aeb9862dfdc0bbf1526b82cfd324cdd8036df19e3545f4a9ccb8`
(`docker buildx imagetools inspect`, tag last updated 2026-10-31). All four
service blocks now pin it with `# pg17` as the name: `_test.yml`, `_e2e.yml`,
and both services in `docker-compose.dev.yml`.

Gates, run 2026-11-05:

```
docker compose -f docker-compose.dev.yml config --quiet   → exit 0
docker pull pgvector/pgvector@sha256:7d0a4146…            → exit 0
docker run … rhysd/actionlint:1.7.12 -color               → exit 0
rg -n "pgvector/pgvector" .github/workflows docker-compose.dev.yml
  → four lines, one digest
```

The running dev services were not restarted: they already hold the same image,
and `docker compose config` plus the pull prove the pin resolves. The PR's
`tests` and e2e jobs start the pinned image for real.

## Task 4 — PGDG retry (#610)

## Task 5 — dev audit (#597)

## Task 6 — tool pins bumped

## Task 7 — monthly pin check (#598)

## Task 8 — one copy of the verdicts (#605)

## Task 9 — the three records (#596, #600, #602)

## Task 10 — the four proofs (#604)
