# The GitHub surface — a map

**Status:** as configured on 2026-11-05 (the [GitHub platform design](../superpowers/specs/2026-11-05-github-platform-design.md) is the record of the decisions and their reasons; this page is the map of what now exists, not a second rulebook)

What lives here: `.github/workflows/` (the workflows), `.github/actions/` (the
composite setup), `.github/dependabot.yml`, the repository settings and the
main ruleset. Everything below describes state — why each piece is shaped the
way it is lives in the design spec, not here.

## Workflow map

| File | Triggers | Jobs | Blocks merge |
| --- | --- | --- | --- |
| `ci.yml` | `pull_request`, `push: main`, `workflow_dispatch` | `lint-types` (calls `_lint.yml`), `changes`, `tests` (calls `_test.yml`), `frontend`, `build`, `e2e-suites` (matrix, calls `_e2e.yml`), `dependency-review` (PR only), `workflow-lint`, `ci-required` | yes — `ci-required` is the ruleset's only required check |
| `nightly.yml` | `schedule` (daily 03:17 UTC), `workflow_dispatch` | `gate`, `audit`, `lint-types`, `tests`, `frontend`, `build`, `e2e-suites` (every capability), `nightly-result` | no — a red run reports through the [`ci/nightly` issue](#the-nightly-and-its-audit) |
| `release-please.yml` | `push: main`, `workflow_dispatch` | `release-please` | no |
| `codeql.yml` | `pull_request` (code paths), `push: main` (code paths), `schedule` (weekly, Sunday 06:07 UTC), `workflow_dispatch` | `analyze` (matrix: `python`, `javascript-typescript`, `actions`) | no — advisory |
| `scorecard.yml` | `schedule` (weekly, Sunday 07:11 UTC), `push: main`, `branch_protection_rule`, `workflow_dispatch` | `analysis` | no — advisory |
| `publish.yml` | *(dormant)* | image build, attest, SBOM, release assets | no |

`publish.yml` is dormant: **it does not exist on the tree** and nothing runs
until a `Dockerfile` does. When created, its trigger is `release: published`
plus `workflow_dispatch` — an image build keyed to a release, not to every
push. (Shape and its permissions are specified in the design spec,
"`publish.yml` (dormant)".)

`_lint.yml`, `_test.yml` and `_e2e.yml` declare no trigger of their own
(`on: workflow_call` only): each defines one job (`lint-types`, `tests`,
`e2e (<capability>)`) and runs only when called — `ci.yml` and `nightly.yml`
call them with the same job names, so aggregators never had to rename a
gate. The Postgres service and the Playwright cache live inside the
reusables; the composite in `.github/actions/setup` carries uv, Python, the
locked sync, pnpm, Node and just, one place for the versions — with
`python: false` and `node: false` for the jobs that need only the other
half (`frontend` and `build` take no Python).

Two named, deliberate shapes a reader should not "fix":

- **The `./` vs `$/` trade.** Every internal `uses:` is written
  `./.github/...` with a `zizmor: ignore[self-repository]` comment. zizmor
  prefers the `$/{...}` self-repository template, but the actionlint image
  the `workflow-lint` job pins (1.7.7, by digest) does not know that
  syntax — and this gate needs both probes green together. Flip to `$/`
  when either trigger fires:
  1. the actionlint image pin is bumped past the version that understands
     `$/`, or
  2. `sha_pinning_required` (see settings below) rejects the `./`
     self-reference.
  The trade is commented at every site (`ci.yml`, `nightly.yml`,
  `_lint.yml`, `_test.yml`, `_e2e.yml`).
- **Pin hygiene.** Actions are pinned by commit SHA with a trailing release
  comment; Dependabot's weekly `github-actions` group keeps the pins
  current. Four versions Dependabot cannot see are pinned as inputs or
  inline and bump manually: the actionlint digest, zizmor's
  `version: 1.30.1`, the Codecov CLI (`version: v11.3.2`) and
  `pip-audit==2.10.1` (the `uvx` invocation in nightly's audit job).
  Dependabot's updater scans workflow files only, so it may not bump the
  `uses:` pins inside a composite action's `action.yml` — verify after the
  first composite lands (`.github/actions/setup`) that its nested pins move
  with the weekly group; if they do not, they join this list.

## `ci-required` — the required-check aggregator

The ruleset requires `ci-required` and nothing else, so a job split never
edits the ruleset. The job runs `if: always()` (a skipped required check
passes — the hole this closes) and judges each result explicitly. The `jobs:` comment in `ci.yml` states the same conditions; this table
summarises them:

| Result handed to a gate | Verdict | Why |
| --- | --- | --- |
| `changes` succeeded, capabilities `[]`, `e2e-suites` **skipped** | green | nothing was owed; the skip is the owed one |
| `dependency-review` **skipped** on a push or dispatch | green | the dependency review is a pull-request duty; this is the second legitimate skip |
| all gates `success` (dependency-review `success` on a PR) | green | |
| `changes` ended anything but `success` | red | it cannot name the owed suites |
| `changes` succeeded but handed over an **empty** capabilities string | red | a successful run prints at least `[]`; empty is a broken handoff, never "legitimately none" |
| capabilities `[]` but `e2e-suites` ended anything but **skipped** | red | nothing was owed, so it must be skipped |
| capabilities non-empty and `e2e-suites` ended anything but `success` | red | the suites were owed |
| `lint-types`, `tests`, `frontend`, `build` or `workflow-lint` ended anything but `success` | red | none of these has a legitimate skip — a `skipped` result is a broken graph, and a skipped required check passes |
| `dependency-review` on a pull request ended anything but `success` | red | a pull request owes the review |
| `dependency-review` on a push or dispatch ended anything but `skipped` or `success` | red | only a pull request runs it, so only `success` and `skipped` are legitimate outside one |

## `scripts/affected.py` — who owes which suite

One resolver, called by `ci.yml`'s `changes` job (PR: `--base origin/main`,
push to main: `--none`, dispatch: `--all`) and by the nightly gate
(`--all`). Fail-open throughout: an unreadable range answers *every* suite,
never none; an unrecognized path owes every suite — an unknown change is a
reason to run more, not less. Stdlib only, so it runs before any `uv sync`.
The classes:

| Class | Paths | Owes |
| --- | --- | --- |
| `HARNESS` | `.github/workflows/`, `.github/actions/` | the smoke suite `settings` alone — proof the harness still works, measured on PR #594's CI: settings 1m33s (setup 1m54s, chat 1m58s, knowledge 4m6s, writing 7m48s, prompts 13m12s, so `settings` beat `setup`, the design's default). Fails open to every suite when no known capability carries that suite |
| `SHARED` | `app/kernel/`, `app/api/`, `app/generated/`, `web/`, `i18n/`, `app/conftest.py`, `app/capabilities/conftest.py`, `justfile`, `pyproject.toml`, `uv.lock`, `pnpm-lock.yaml` | every suite |
| `RELEASE` | `pyproject.toml`, `uv.lock`, `CHANGELOG.md`, `.release-please-manifest.json`, `package.json`, `web/package.json`, `app/kernel/version.py`, `web/lib/api/openapi.json` | nothing, but only when a change touches *only* release files (checked first, before the shared overlaps) |
| `INERT` | `docs/`, `README*`, `CHANGELOG.md`, `LICENSE`, `AGENTS.md`, `CONTRIBUTING.md`, `TESTING.md`, `scripts/`, `docker-compose*.yml`, `.pre-commit-config.yaml`, `.release-please-manifest.json`, `.github/` | nothing |
| *(a path under `app/capabilities/<name>/`)* | | that capability's own e2e suite |
| *(anything else)* | | every suite |

A `HARNESS` path beside any product path loses: the product path's answer
never runs fewer suites than the smoke.

## The ruleset (id 18702224) on `main`

| Element | State |
| --- | --- |
| Required status checks | `ci-required` only, strict (branches must be up to date) |
| Merge methods | `merge` only — squash and rebase are off |
| `pull_request` | 1 approval; `require_last_push_approval`; `dismiss_stale_reviews_on_push: false`; `require_extra_approval_for_unattributed_changes: true`; review-thread resolution required |
| `copilot_code_review`, `code_quality` | kept |
| `non_fast_forward`, `deletion` | kept |
| Bypass actor: repository admin | **kept** — the owner escape hatch. GitHub forbids self-approval; without the bypass the solo owner could not merge their own PR. Documented in the design spec, not a general gate |
| Bypass actor: the Dependabot integration (actor 29110) | **removed** — automated content merges like any other PR: a human approves, the owner merges |

## Repository settings

| Setting | State |
| --- | --- |
| `allowed_actions` | `selected`: GitHub-owned + verified creators + the explicit third-party allowlist — `astral-sh`, `pnpm`, `extractions`, `gitleaks`, `codecov`, `googleapis`, `softprops`, `docker`, `sigstore`, `ossf`, `zizmorcore`. A new third-party action is a one-line settings change |
| `sha_pinning_required` | `true` — the SHA pins this directory carries stop being convention and become enforced |
| `delete_branch_on_merge` | `false` |
| `allow_auto_merge` | `false` |
| "Allow GitHub Actions to create and approve pull requests" | off — why the release PR is authored by a GitHub App token and needs a human approval |
| Secret scanning: `secret_scanning_non_provider_patterns`, `secret_scanning_validity_checks` | **`disabled`** — the settings PATCH that turns these on did not take during the 2026-11-05 rollout and is the open item on this page; everything else in that rollout did land. The limitation is live, not a documented intent: non-provider patterns and validity checks are not running. Re-applying the settings PATCH is the fix |

## Sourcery — the review bot

The review bot is Sourcery; its review settings live in the Sourcery
dashboard, not in a repository file. Current state:

- Ignore title keywords: `chore: release` (a release PR moves version
  strings and the changelog; the human check there is the OpenAPI version
  contract in `tests`, not an AI review).
- Path filters: `app/generated/**`, `web/lib/api/**`, `web/dist/**`,
  `assets/**`, `**/*.lock`, `uv.lock`, `pnpm-lock.yaml`.
- Draft PRs: off. Review profile: Balanced. Base branch: `main`. Labels
  allowlist: empty.
- "Let Sourcery approve pull requests": **off** — a bot approval would
  satisfy the 1-approval rule for foreign PRs too.
- The "Sourcery review" check is advisory: it names no context in
  `ci-required`, so it never blocks a merge. The dependency review is what
  blocks a pull request; CodeQL — advisory like Sourcery — feeds the
  Security tab for triage.

The dead review-bot config file was deleted from the working tree on
2026-11-05 — its bot was replaced by Sourcery, which took over the review
check, and the file had stopped doing anything. Historical mentions in
`docs/architecture/decisions/`, the plans and the reports are records and
stay untouched.

## CodeQL (advanced setup)

`codeql.yml`, advanced-setup CodeQL replacing repository default setup, and
advisory — it names no context in `ci-required`, so a finding is a triage
item, never a blocked merge.

- Languages: `python`, `javascript-typescript`, `actions` — one runner per
  language, `build-mode: none` inside each matrix entry.
- `queries: code-scanning` — the action's default suite and the equivalent
  of default setup's queries, so the migration changed *who runs* CodeQL,
  not *what it looks for*. (`default` is not a query pack the CLI resolves:
  `init` fails with "Query pack default cannot be found".)
  `security-and-quality` is deliberately deferred — raising the suite is its
  own decision, with its own review of the noise it brings.
- Path-filtered: `app/**`, `web/**`, `scripts/**`,
  `.github/workflows/**`, `.github/actions/**`, excluding
  `app/generated/**`, `web/lib/api/**`, `web/dist/**`, `assets/**`. The
  weekly sweep re-analyzes the whole tree with no filter. Being advisory is
  what makes the filters safe: a filtered-out pull request cannot register
  a *missing required check* and pass silently.
- **Fork caveat:** advanced setup cannot upload SARIF for `pull_request`
  events from forks (`security-events: write` is not granted there); pushes
  and same-repo PRs are unaffected. Default setup handled forks. Revisit
  trigger: external contributors become regular — then revert to default
  setup.
- Migration order was binding: GitHub rejects advanced setup while default
  setup is configured, so default setup was disabled before `codeql.yml`
  merged. If this workflow ever leaves, disable advanced setup *before*
  re-enabling default setup, in that order.

## Scorecard

`scorecard.yml`, advisory. Runs the OSSF Scorecard over the repository
itself and publishes the result (`publish_results: true` — the repository
is public, which is what makes the score and its badge valid); the same
SARIF lands in the Security tab. Weekly plus every `main` push, so
ruleset changes (for which GitHub offers no event) are graded without a
long wait.

Known blind spot: the `branch_protection_rule` trigger covers **classic
protection rules only**. `main` is protected by a ruleset, and rulesets
have no event — so a ruleset edit re-grades at the next push or weekly run,
not on the edit itself. The trigger stays as the listener for classic
protection settings; do not read its absence on a ruleset edit as silence
meaning anything.

## The nightly and its audit

- `gate` first asks the only schedule question: did `main` move since the
  last successful nightly (it compares the last successful
  `event=schedule` run's `head_sha`)? Unchanged → everything below skips,
  no runner minutes. Manual dispatch always proceeds — whoever ran it
  asked for a sweep. It also resolves the full suite list from
  `scripts/affected.py --all --json`; the matrix is derived, never static.
- `audit` is the lockfile sweep: `uv export --locked --no-dev` writes the
  runtime requirements — judged directly by `uvx pip-audit==2.10.1
  --strict` — and `pnpm audit --prod --audit-level high` checks the
  JavaScript side. It
  **reddens the nightly but blocks no PR**: a CVE published against an
  existing prod dependency has no PR to ride in on, which is exactly why
  the sweep exists. Dev dependencies are *not* covered here — they are
  reviewed on PRs by `dependency-review` (high severity + the
  AGPL/GPL deny list), so neither surface is unjudged.
- `nightly-result` keeps **one** open issue labeled `ci/nightly`: opened
  on the first failure, a comment per further failure, closed the morning
  a nightly goes green. Scheduled runs only — a manual dispatch reports
  to nobody but its own log.

## Dependabot

| Ecosystem | Schedule | Groups | Cooldown | Notes |
| --- | --- | --- | --- | --- |
| `uv` | monthly | minor/patch, major | `default-days: 7`, majors 30 | `uv`, never `pip` — the pip updater cannot touch `uv.lock` |
| `npm` | monthly | minor/patch, major | `default-days: 7`, majors 30 | entry at `/`, not `/web`, so `pnpm-lock.yaml` moves with the manifest |
| `github-actions` | weekly | minor/patch, major | `default-days: 3` — the Actions updater supports `default-days` only, so there is no 14-day major hold | weekly is what keeps the SHA pins current |

- No `docker` and no `devcontainers` entry: a `docker` entry returns with a
  `Dockerfile`, a `devcontainers` entry with a dev container. Empty entries
  against absent trees were part of the defect this platform fixed.
- `rebase-strategy` is the default (`auto`); the old `disabled` let PRs rot
  behind strict status checks.
- Every update commits as `chore(<scope>)` — Dependabot's default
  `build(deps)` is not a conventional-commit type this repository allows.
- Security advisories fire immediately, independent of the schedule and
  cooldowns. Limit `5` open PRs per ecosystem. The cost win against the old
  setup comes from grouping (one PR per group, not per bump), not from
  testing less — dependency paths stay `SHARED` in `affected.py` and owe
  every suite.
