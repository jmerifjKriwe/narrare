# GitHub platform design

**Status:** approved in conversation 2026-11-05 · builder check 2026-11-05 folded in (appendix)
**Scope:** `.github/**`, `scripts/affected.py`, `justfile` (one recipe), repository settings, rulesets, review bot

## Intent

One workflow, one concern. Today `ci.yml` is three workflows in one file (PR
gate, post-merge verification, nightly sweep), `release-please.yml` is release
orchestration plus a publish pipeline that cannot run, and Dependabot is
configured so that every update — a lockfile bump or a single action SHA —
runs all six E2E suites. The workflows themselves are the one part of the
repository no gate checks.

The target: `ci.yml` is the merge gate, `nightly.yml` is the full sweep,
`release-please.yml` orchestrates releases, `publish.yml` builds artifacts,
`codeql.yml` and `scorecard.yml` are security signals. Dependabot bundles
instead of fanning out. One required check instead of four.

## Why now

- `ci.yml` carries three trigger families under one `concurrency` block, one
  badge and one required-check set. The `nightly-guard` job runs on every PR
  and push to answer a question only the schedule asks.
- `release-please.yml:75-339` is a `publish` job behind `if: false` — ~260
  lines of Docker, SBOM and release-bundle code that cannot run because the
  tree has neither `Dockerfile` nor `docker-compose.release.yml`.
- `scripts/affected.py` classifies `.github/workflows/ci.yml` as `SHARED`
  (all suites) but the rest of `.github/` as `INERT` (no suites). Evidence:
  PR #516 (`actions/checkout` bump) and #511 (`setup-uv` bump) each ran all
  six E2E suites; PR #512 (`docker/login-action`, touching only
  `release-please.yml`) ran none.
- `uv`/`npm` Dependabot bumps change `uv.lock`/`pnpm-lock.yaml`, which are
  `SHARED`: PR #518 (11 updates) and #520 (9 updates) each ran all six E2E
  suites.
- `dependabot.yml` has a `docker` entry pointing at `/.devcontainer`, which
  does not exist.
- No `timeout-minutes` on any `ci.yml` job: a hung E2E job can run six hours.
- Required checks are four job names; every job split is a ruleset edit.
- Repository settings: `allowed_actions: all`, `sha_pinning_required: false`
  — the SHA pins are convention, not a guard.
- `.coderabbit.yaml` remains although CodeRabbit was replaced by Sourcery
  (recent PRs #593/#525/#524 show "Sourcery review").
- The live ruleset (id 18702224) grants a second always-bypass to the
  Dependabot integration (actor 29110). Dependabot PRs are the one class of
  automated content that can merge without a human; the design's approval
  model closes it.

## Goals

- Six top-level workflows: `ci`, `nightly`, `release-please`, `publish`,
  `codeql`, `scorecard`.
- Three reusable workflows: `_lint.yml`, `_test.yml`, `_e2e.yml`; one
  composite action for setup; plain jobs for `frontend` and `build`.
- One required status check: `ci-required`.
- `affected.py` path classes: `HARNESS`, `RELEASE`, `SHARED` (unchanged
  otherwise).
- Dependabot: `github-actions` weekly and grouped, `uv`/`npm` monthly and
  grouped, explicit `cooldown`, dead `docker` entry removed. The Dependabot
  cost win comes from grouping, not from resolver changes.
- Security baseline: `actionlint`, `zizmor`, dependency review, CodeQL
  advanced setup, Scorecard.
- `timeout-minutes`, least-privilege `permissions`, caches and per-workflow
  `concurrency` everywhere.

## Non-goals

- Merge queue, self-hosted runners, OS/Python matrix, canary or release
  channels.
- Auto-merge, including for Dependabot actions updates.
- Container publishing before a `Dockerfile` exists.
- Changes to product tests or E2E scope.
- Return of v1 gates (mutation testing, VRT, eval-nightly).

## Anti-goals

- More blocking checks than today: four required contexts become one.
- Duplicate CodeQL (default setup and advanced setup at the same time).
- Path-filtered required workflows whose check stays pending when the filter
  does not match.
- CI commands that bypass the `just` recipes.
- A gate without a named failure it prevents.

## Approaches considered

**A — conservative split.** Four workflows (`ci`, `nightly`,
`release-please`, `security`), no reusable workflows, no composite action.
Lowest risk, but the setup steps are copied between `ci.yml` and
`nightly.yml`, and those copies drift — the very defect that made the pip
Dependabot era die in `uv sync --locked`. Rejected.

**B — modular platform (chosen).** Six concern workflows, three reusable
workflows, one composite setup action, a single required check, a security
baseline and a phased migration. More files, but each has one job, and the
duplication lives in exactly one place per concern.

**C — maximal.** B plus merge queue (`merge_group` in every workflow),
self-hosted runners for E2E, OS/Python matrix, release channels,
environment approvals on every deploy. Sensible with several contributors
and PR volume; today it doubles CI runs per PR for no observed failure.
Rejected for now; Phase 6 records the revisit triggers.

## Decisions

| Point | Decision | Reason |
| --- | --- | --- |
| CodeQL | advanced `codeql.yml`; default setup disabled | path filters, generated-code exclusion, SHA-pinned action, advisory status; caveats below |
| Admin bypass | stays, repository-admin role | GitHub forbids self-approval; without the bypass the solo owner could not merge their own PRs. Documented as owner escape hatch, not a general gate. |
| Dependabot integration bypass | removed | a ruleset bypass lets automated content merge without a human; Dependabot needs no bypass to author, rebase or close its PRs, and the owner merges them like any other PR. Pure hardening, no workflow change. |
| `allowed_actions` | `selected` | GitHub-owned + verified creators + explicit third-party allowlist |
| `rebase-strategy` | `auto` (remove `disabled`) | `disabled` + `strict_required_status_checks_policy` lets Dependabot PRs rot; #513/#514 closed unmerged |
| `require_last_push_approval` | stays `true` | re-approval after a Dependabot rebase on foreign PRs is accepted; owner bypass covers the solo case |
| Sourcery approval | off | bot approval would satisfy the 1-approval rule for foreign PRs too; raising to 2 weakens it instead |
| Sourcery review check | advisory, not required | it is an AI review, not a deterministic gate; security findings surface through CodeQL/dependency review |
| HARNESS smoke | one suite, default `setup` | proves the harness works without six browser suites; builder verifies `setup` is the fastest |
| Reusable workflows | yes, three | `_lint`, `_test`, `_e2e`; `frontend` and `build` are plain jobs on the composite action — the duplication worth removing is the Python+Node+Postgres setup, not three pnpm lines |
| Auto-merge | off | a compromised action release runs with the workflow token; blast radius too high |
| Merge queue | not now | solo repo, merge commits, low volume; revisit when combined merges break `main` |
| `publish.yml` | only when a `Dockerfile` exists | dead code was one of the defects being fixed |
| Coverage invocation | new recipe `test-cov` | removes today's inline CI pytest invocation; adds the 24th public recipe. The spec's §6 count (21) is already stale against the 23 the justfile carries; the spec list and count are corrected to 24. |
| `main` concurrency | per-SHA group, no cancellation | every merge keeps its own coverage report; a shared group with cancellation off would serialize and delay the newest signal |
| Ruleset rewrite | additive only | a ruleset update replaces the rules array; every rule not named here is carried over verbatim (inventory below) |

## Target architecture

### Workflow map

| File | Triggers | Jobs | Blocks merge |
| --- | --- | --- | --- |
| `ci.yml` | `pull_request`, `push: main`, `workflow_dispatch` | `changes`, `lint-types` (uses `_lint`), `tests` (uses `_test`), `frontend`, `build`, `workflow-lint`, `dependency-review` (PR), `e2e-suites` (matrix, uses `_e2e`), `ci-required` | yes, via `ci-required` |
| `nightly.yml` | `schedule` 03:17 UTC, `workflow_dispatch` | `gate`, `lint-types` (uses `_lint`), `tests` (uses `_test`), `frontend`, `build`, `e2e-suites` (all capabilities, uses `_e2e`), `audit`, `nightly-result` | no |
| `release-please.yml` | `push: main`, `workflow_dispatch` | `release-please` | no |
| `publish.yml` | `release: published`, `workflow_dispatch` | image build, attest, SBOM, release assets | no |
| `codeql.yml` | `pull_request` (code paths), `push: main` (code paths), `schedule` weekly | `analyze` matrix: `python`, `javascript-typescript`, `actions` | no |
| `scorecard.yml` | `schedule` weekly, `push: main`, `branch_protection_rule` | `analysis` | no |

`publish.yml` does not exist until a `Dockerfile` does. Until then: no file,
no `if: false`.

Job names inside the reusable workflows stay `lint-types` and `tests`, so
the functional gates keep their names and logs; the caller-level check
names change to `lint-types / lint-types` and `tests / tests` once the
extraction happens — harmless, because by then the ruleset requires only
`ci-required`, which is defined in `ci.yml` itself and never moves.

### `ci.yml`

```
changes ─┬─ lint-types ─────────┐
         ├─ tests ──────────────┤
         ├─ frontend ───────────┼─ ci-required
         ├─ build ──────────────┤
         ├─ workflow-lint ──────┤
         ├─ dependency-review (PR only)
         └─ e2e-suites (matrix) ──┘
```

- `changes` runs `affected.py`: `--base origin/main` on a PR, `--none` on a
  push to `main`, `--all` on dispatch; `--release-pr` for the release
  branch. No Dependabot flag — the resolver needs no special case, because
  a dependency bump legitimately owes every suite and the cost win comes
  from Dependabot's grouping.
- `lint-types` = `just lint` + `just typecheck` + gitleaks, via `_lint.yml`
  (today's combined job, unchanged in scope). `tests` = `just test`, or
  `just test-cov` on `main` pushes (coverage + JUnit + Codecov), via
  `_test.yml`. `frontend` = `just test-frontend`; `build` = `just build` —
  plain jobs on the composite setup. CI calls the same recipes the local
  gate calls; the one inline pytest invocation in today's `ci.yml` is
  replaced by the `test-cov` recipe.
- `workflow-lint` runs `actionlint` and `zizmor` on every event. Seconds of
  cost, no path filter — a path-filtered required workflow is the
  pending-check trap. It is blocking from the day it lands, and the tree is
  clean the day before: the introducing phase starts by running both tools
  locally and fixing or explicitly suppressing (with a comment) every
  finding. A baseline of silent suppressions is not an option; the design's
  no-silent-suppression rule is absolute.
- `dependency-review` runs on `pull_request` only; fails on high severity
  and on licenses in the deny-list (`AGPL-1.0`, `AGPL-3.0`, `GPL-2.0`,
  `GPL-3.0`; the project is MIT and viral licenses would force relicensing —
  LGPL stays allowed). `ci-required` treats its skip on non-PR events as
  green.
- `e2e-suites` fans the `changes.capabilities` matrix out over `_e2e.yml`.
- `ci-required` runs `if: always()`, checks every `needs` result
  explicitly: red when a job failed or was skipped without a legitimate
  reason (a broken `changes` handover, an empty capabilities string), green
  when a skip is owed (no capability, dependency review on push). This
  generalizes today's `e2e` aggregator and closes the same skipped-check
  hole for every job.
- A push to `main` still owes no E2E: the merge tree is the tree the PR's
  required checks tested; direct pushes are covered by the nightly.
- `concurrency`: PRs use `ci-${{ github.ref }}` with
  `cancel-in-progress: true`; `main` pushes use
  `ci-${{ github.ref }}-${{ github.sha }}` with
  `cancel-in-progress: false`. The per-SHA group is load-bearing: the same
  group with cancellation off would *serialize* runs — GitHub queues
  within a group — and delay the newest main signal behind the previous
  run. Per SHA, every merge runs in parallel and delivers its own coverage
  report for its own SHA; cancelling would delete a report only that run
  could produce (the defect today's `!cancelled()` upload comment already
  fights). The post-merge run is telemetry, not a gate: the PR's required
  checks already tested the merge tree under
  `strict_required_status_checks_policy`.

### `nightly.yml`

- `gate` answers the only schedule question first: is `main` still where
  the last successful nightly left it? It reads the last successful
  `nightly.yml` run with `event=schedule` and compares `head_sha`;
  unchanged skips everything below. Manual dispatch always proceeds. On
  every proceeding run it also resolves the full suite list via
  `affected.py --all --json` and exports it as an output — the matrix is
  derived, never a static list, so a new capability is picked up by
  existing machinery and not by a second copy of the mapping.
- Then the same gates `ci.yml` uses: `lint-types`, `tests` (plain `just
  test` — coverage is a `main`-push concern and the Codecov dashboard keys
  on those runs; the nightly reports through the `ci/nightly` issue),
  `frontend`, `build`, and `e2e-suites` with every capability.
- `audit` runs `pip-audit` against `uv export --no-dev` output and
  `pnpm audit --prod`. It reddens the nightly but blocks nothing on the PR
  path.
- `nightly-result` opens or updates one issue labeled `ci/nightly` on
  failure (failed run link, failed jobs) and closes it when a nightly goes
  green again. A red nightly must not be discoverable only by scrolling
  through Actions.
- `concurrency: nightly`, no cancel-in-progress.

### `release-please.yml`

Only the GitHub App token and the release-please action. The `publish` job
is deleted, not disabled. Two stale comments go with it:

- `release-please.yml:17` says "the three `extra-files` entries" — there
  are four (`uv.lock` among them).
- `release-please.yml:33-34` says `uv.lock` is "known, accepted drift"
  release-please cannot address — `release-please-config.json:24-28`
  updates exactly that entry.

The release PR remains a normal PR: it runs `ci.yml` like any other,
carries no E2E (`--release-pr`), and keeps `lint-types`, `tests` (the
OpenAPI version contract lives there), `frontend` and `build`.

### `publish.yml` (dormant)

Created when a `Dockerfile` returns, not before. Shape: `release:
published` plus `workflow_dispatch`; `environment: release` with required
reviewers; `permissions: contents: write, packages: write, id-token:
write, attestations: write`; `docker/metadata-action`,
`docker/build-push-action` with `provenance: mode=max` and `sbom: true`,
`actions/attest-build-provenance`, keyless Cosign, release assets via
`softprops/action-gh-release`. No long-lived tokens.

### `codeql.yml`

Advanced setup, advisory, path-filtered (`app/**`, `web/**`, `scripts/**`,
`.github/workflows/**`, `.github/actions/**`; excluding `app/generated/**`,
`web/lib/api/**`, `web/dist/**`, `assets/**`), languages `python`,
`javascript-typescript`, `actions`, `default` query suite (not
`security-and-quality` — raise later, deliberately), build mode `none`,
`security-events: write` at the job, `timeout-minutes: 30`.

Migration order is binding: disable default setup first, then merge
`codeql.yml`. GitHub rejects advanced setup while default setup is
configured. Do both in one operation and verify the first run analyses all
three languages.

Accepted trade-off: advanced setup cannot upload SARIF for `pull_request`
events from forks (`security-events: write` is not granted there). Default
setup handles forks. If external contributors become regular, revert to
default setup — recorded as a revisit trigger, not a defect.

### `scorecard.yml`

`ossf/scorecard-action`, weekly plus `push: main` and
`branch_protection_rule`, `publish_results: true` (the repository is
public), SARIF upload to the Security tab. Signals supply-chain regressions
the rulesets and settings sections here are responsible for.

### Reusable workflows and composite action

- `_lint.yml`: inputs `python-version`, `node-version`, `pnpm-version`;
  one job `lint-types`: setup + `just lint` + `just typecheck` + gitleaks.
- `_test.yml`: input `coverage`; one job `tests`; declares the
  `pgvector/pgvector:pg17` service on 5433; `just test`, or `just test-cov`
  when `coverage` is set.
- `_e2e.yml`: input `capability`; same service; Playwright chromium; `just
  test-e2e <capability>`.
- `.github/actions/setup/action.yml`: uv, Python, pnpm, Node, just — one
  place for the versions. Checkout stays with the caller. `frontend` and
  `build` are plain jobs in `ci.yml` and `nightly.yml` that use it.
- Reusable workflows declare their own `permissions` and `services`; the
  caller must grant enough. `CODECOV_TOKEN` is passed explicitly to
  `_test.yml`, never via `secrets: inherit`.
- Caches: `setup-uv` with `enable-cache`, `setup-node` with the pnpm cache,
  and a `~/.cache/ms-playwright` cache keyed on the Playwright version so
  the matrix stops downloading chromium once per capability.
- Caveat recorded for the builder: Dependabot's `github-actions` updater
  covers workflow files and reusable workflows; whether it pins `uses:` in
  composite actions is not documented. Verify after the first composite
  lands; if not covered, those pins are manual and the docs page says so.

### `affected.py`

- `HARNESS`: `.github/workflows/**`, `.github/actions/**` → one smoke
  suite (default `setup`; the builder verifies it is the fastest) instead
  of all suites. Proves the harness works; a broken invocation is caught
  same-day, not next nightly.
- `RELEASE`: unchanged.
- `SHARED`: unchanged, except `.github/workflows/ci.yml` moves to
  `HARNESS` (the whole workflows directory takes its place).
- Dependency paths (`pyproject.toml`, `uv.lock`, `pnpm-lock.yaml`,
  `package.json`, `web/package.json`) deliberately stay `SHARED`: a
  dependency bump can break any capability and owes every suite. The cost
  win comes from Dependabot's grouping, not from testing less.
- `.github/dependabot.yml` and other `.github/` files stay `INERT`.
- Every classification keeps its reason line and its tests; the resolver
  stays stdlib-only and fail-open.

### `dependabot.yml`

- Remove the `docker` / `/.devcontainer` entry. `devcontainers` returns
  with a devcontainer; `docker` at `/` returns with a `Dockerfile`.
- `uv` and `npm`: monthly, grouped (minor-patch, major), `cooldown`
  `default-days: 7`, `semver-major-days: 30`, `open-pull-requests-limit:
  5`.
- `github-actions`: weekly, grouped (`actions-minor-patch`,
  `actions-major`), `cooldown` `default-days: 3`, `semver-major-days: 14`.
- `rebase-strategy: disabled` removed (default `auto`).
- Commit prefixes and labels unchanged (`chore` + scope, so release-please
  ignores the bumps).

### Branch protection and repository settings

The ruleset update is a replace operation: the rules array submitted is the
whole truth. Everything not named as a change below is carried over
verbatim. Inventory of the live ruleset (id 18702224), with the target
state:

| Rule | Target |
| --- | --- |
| `required_status_checks` (`tests`, `e2e`, `lint-types`, `build`; strict) | replaced by `ci-required` alone; strict policy stays |
| `pull_request` (1 approval, `require_last_push_approval: true`, `dismiss_stale_reviews_on_push: false`, `required_review_thread_resolution: true`, `require_extra_approval_for_attributed_changes: true`, `require_code_owner_review: false`) | unchanged |
| `allowed_merge_methods: ["merge", "squash"]` | `["merge"]` only |
| `copilot_code_review` (`review_on_push: true`) | kept — removing a review signal is not this design's claim |
| `code_quality` (warnings) | kept |
| `non_fast_forward`, `deletion` | kept |
| bypass: repository-admin role | kept, documented as owner escape hatch |
| bypass: Dependabot integration (29110) | **removed** |

Repository settings: `sha_pinning_required: true`; `allowed_actions:
selected` with GitHub-owned, verified, and an explicit third-party
allowlist (astral-sh, pnpm, extractions, gitleaks, codecov, googleapis,
softprops, docker, sigstore, ossf, zizmorcore); secret scanning
non-provider patterns and validity checks on; `delete_branch_on_merge:
false` and `allow_auto_merge: false` stay.

### Sourcery

- `.coderabbit.yaml` is deleted. Historical CodeRabbit mentions in ADRs,
  plans and reports are records, not live config, and stay untouched.
- Sourcery review settings live in the Sourcery dashboard, not in a
  repository file. `docs/architecture/github.md` documents the intended
  dashboard state so a future reader finds it:
  - Ignore title keywords: `chore: release`.
  - Path filters: `app/generated/**`, `web/lib/api/**`, `web/dist/**`,
    `assets/**`, `**/*.lock`, `uv.lock`, `pnpm-lock.yaml`.
  - Draft PRs: off (default; Sourcery also skips dependency bots and
    packaging-only changes by default).
  - Review profile: Balanced. Base branch: `main`. Labels allowlist: empty.
  - "Let Sourcery approve pull requests": **off** (decision above).
- The "Sourcery review" check stays advisory.

## Migration phases

Each phase merges on its own and leaves `main` green. The ordering is
load-bearing: the aggregator and the ruleset switch land **before** the
reusable extraction, because a job that `uses:` a reusable workflow reports
its check under a new name (`tests / tests`), and the four old required
contexts would go pending and block every PR mid-migration.

| Phase | Contents | Verification |
| --- | --- | --- |
| 1 | `nightly.yml` split out; guard moves there; `ci.yml` loses `schedule`; `timeout-minutes` and `permissions: {}` everywhere | manual nightly dispatch runs the sweep; a PR run has no guard job |
| 2 | `just test-cov` recipe; `workflow-lint` job (after a local `actionlint`+`zizmor` pass over the tree has fixed or comment-suppressed every finding); `ci-required` aggregator; ruleset switch to `ci-required` only, rules carried per the inventory above | first green `ci-required`; then a test PR proves a red job reddens it; a deliberate skip-scenario proves the aggregator's judgement |
| 3 | `_lint`, `_test`, `_e2e`, composite setup, caches; `affected.py` `HARNESS` class and tests | draft PRs: docs-only → no E2E; code → affected suites; action bump → smoke suite; check names may change (`tests / tests`) without touching the ruleset |
| 4 | `dependency-review` (deny-list as above); `codeql.yml` plus default-setup disable in one operation; `scorecard.yml`; `sha_pinning_required`; action allowlist | CodeQL analyses all three languages after the switch; Scorecard SARIF arrives; dependency review reddens a test PR with a known-vulnerable or denied-license pin |
| 5 | `release-please.yml` publish deletion and stale comments; `.coderabbit.yaml` deletion; badges; `docs/architecture/github.md` | release-please still opens and tags; no publish job exists |
| 6 (optional) | merge queue, self-hosted runners, OS matrix | separately planned |

## Verification

- Local per phase: `just check`, `just test`, `just test-e2e <capability>`,
  `just verify`.
- Event proof per phase: a draft PR exercises `ci.yml`; a manual dispatch
  exercises `nightly.yml`; a push to `main` exercises `release-please.yml`
  and the post-merge leg.
- Bidirectional proof for every new gate: make it fail deliberately
  (an `actionlint` error, an unpinned action for `zizmor`, a
  known-vulnerable pin for dependency review, a skipped-job scenario for
  `ci-required`), read the red output, revert, read the green output.
- The ruleset switch happens only after the first green `ci-required` run;
  the submission carries the full rules inventory above, and the diff is
  read back through the API afterwards.
- CodeQL migration is one operation: disable default setup, merge
  `codeql.yml`, confirm analyses for `python`, `javascript-typescript` and
  `actions` in the Security tab.

## Risks and accepted trade-offs

- More files to read. Mitigated by `docs/architecture/github.md` (the map,
  the why, the Sourcery dashboard state) and the `_` prefix for reusable
  workflows.
- Reusable workflows add a layer to logs. They stay thin: one concern, no
  conditionals.
- `HARNESS` smoke means an action bump runs one browser suite. Accepted;
  the alternative (none) delays a broken harness to the nightly.
- Advanced CodeQL loses fork-PR SARIF upload. Accepted until external
  contributors are regular; revert trigger recorded.
- The nightly runs every capability's E2E nightly. Unchanged cost, new
  visibility through the `ci/nightly` issue.
- The action allowlist can block a new third-party action mid-task.
  Accepted; adding one is a one-line settings change.
- Dependabot rebases trigger CI again. Accepted; weekly groups bound it.
- `main` pushes run in parallel, one concurrency group per SHA. On a
  public repo the minutes are free; the cost is concurrent runners, and
  the report for every merged SHA is the point. The per-SHA group also
  avoids the serialization trap: with a shared group and cancellation off,
  the newest run would wait for the previous one.

## What is left to the builder

- Exact YAML for every workflow and the composite action; SHA-pinned
  actions with release comments in the established style.
- The action allowlist contents from the workflows actually used.
- Runner tool versions (Python 3.14, Node 22, pnpm, just) centralized in
  the composite action; the exact Playwright cache key.
- The `ci-required` result table (which skips are legitimate, which are
  failures) written as explicitly as today's `e2e` aggregator comment.
- The `test-cov` recipe and the spec §6 correction (21 listed, 23
  actual, 24 after this plan).
- The ruleset and settings changes as `gh api` calls, in order, with the
  API diff read back after each.
- Whether `setup` is the fastest suite for the HARNESS smoke; pick the
  fastest, record the measurement.
- The `actionlint` + `zizmor` baseline pass and every suppression comment
  it produces.
- The nightly `audit` job's exact tools and thresholds.
- The CodeQL default-setup disable plus first-run verification.
- Badges and `docs/architecture/github.md`.

## Appendix: builder check, 2026-11-05

A fresh reviewer read this design against the live repository and ruleset
and asked ten questions. Resolutions, folded into the body above:

1. **Phase ordering vs required-check names** — the aggregator and ruleset
   switch moved ahead of the reusable extraction (phase table note).
2. **Unmentioned ruleset rules** — carried over verbatim; the Dependabot
   integration bypass is removed and the full inventory is now in the
   design (decisions and ruleset sections).
3. **Reusable/job shape** — three reusables (`_lint` keeps one `lint-types`
   job, `_test` one `tests` job); `frontend` and `build` are plain jobs.
4. **Coverage invocation** — new `just test-cov` recipe; the inline pytest
   exception disappears; the spec §6 count is corrected to 24 (21 listed,
   23 actual, 24 after this plan).
5. **`--dependabot` / `DEPENDENCY` was a no-op** (dependency paths are
   already `SHARED`) — the flag and class are dropped; grouping carries the
   cost win.
6. **Nightly coverage** — none; the nightly tests plain, reports through
   the issue, Codecov stays keyed to `main` pushes.
7. **Cancel-in-progress on `main`** — no; PRs use a per-ref group with
   cancellation, `main` uses a per-SHA group without it. A shared group
   with cancellation off would serialize and delay the newest signal.
8. **Nightly suite enumeration** — derived from `affected.py --all --json`
   in `gate`, never a static list.
9. **License policy** — deny-list (`AGPL-*`, `GPL-2.0`, `GPL-3.0`); LGPL
   allowed.
10. **`workflow-lint` day one** — blocking, with the tree cleaned and every
    suppression commented before the phase lands.
