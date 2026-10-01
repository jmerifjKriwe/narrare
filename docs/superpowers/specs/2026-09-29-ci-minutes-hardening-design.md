# CI Minute Optimization + GitHub Actions Hardening — Design

> **Status:** Approved (2026-09-29) — spec awaiting final review
> **Repo anchor:** `ebd1bb26`
> **Deciders:** PO (rulings below), Dev Coordinator (analysis + draft)
> **PO rulings baked in (binding, not re-litigated):**
> 1. PRs are the CI gate; direct pushes to `main` end (behavioral change for
>    agent worktrees). Push CI = smoke only.
> 2. Off-PR cadence = nightly FULL run (incl. E2E + Integration), not weekly.
> **Related:** TanStack incident followup (https://tanstack.com/blog/incident-followup),
> zizmor usage docs (https://docs.zizmor.sh/usage/), eval-nightly.yml (prior
> quota-driven slimming, same pattern), ADR-087 (testing governance layering).

---

## 1. Goal & Non-Goals

**Goal.** Fit monthly GitHub Actions usage of the private repo (GitHub Free,
2000 min/month) with headroom, and close the supply-chain gaps the TanStack
npm-compromise incident exposed — mapped to THIS repo's actual threat model,
not copied blindly.

**Non-Goals.**

- No runner changes (no ARM, no self-hosted, no larger runners).
- **No cache removal** (deliberate divergence from TanStack — see §5.5).
- No Dependabot config changes: Dependabot's own `dynamic` update runs are
  free (GitHub Changelog 2024-04-22) and Dependabot PRs go through the same
  PR gating as everything else.
- No publish/pipeline redesign (release-please stays as-is).

## 2. Evidence (measured via GitHub API, Sept 1–14 2026)

261 runs, 1468 jobs analyzed:

| Trigger | Job-minutes | Runs | Notes |
|---|---|---|---|
| `push` | **943** | **126 on `main`** (~9/day) | agent worktrees pushing directly |
| `pull_request` | 458 | ~49 | |
| Dependabot `dynamic` | 222 | 93 | **free — does not count toward quota** |
| `schedule` | 20 | 1 | |

CI workflow: 104 runs ≈ 1328 min — Frontend 388, Integration 340, Unit 219,
E2E 192, Typecheck 102, Architecture 80, Security 36, Lint 22, plus sub-minute
jobs (Detect Changes, warnings-summary, badge). Quota was exhausted by Sept 14.

**Root causes (≥2× why):**

1. **Path-filter bypass on push.** Expensive jobs are gated
   `github.event_name == 'push' || (path/draft conditions)` — the
   `changes` job (dorny/paths-filter) exists but its outputs are OR'd away
   for every push. *Why?* Historical "always full CI on main" assumption.
   *Why harmful?* Every one of the ~9 daily direct pushes runs the full
   monorepo CI (Frontend/VRT even on backend-only commits).
2. **Push frequency.** ~9 pushes/day directly to `main` from agent worktrees.
3. **Job sprawl.** 11–13 jobs/run; several sub-minute jobs each bill ≥1 min
   (per-job minute rounding) plus per-job setup (checkout + `uv sync`).
4. **Badge amplifier.** `update-coverage-badge` commits to `main` via
   `git-auto-commit`; the push trigger has no path filter → each badge commit
   re-triggers a full push CI run.

## 3. Decision 1 — Trigger Model (approved)

| Event | Jobs that run |
|---|---|
| `pull_request` | Full CI, path-gated via existing `changes` outputs + draft-PR skip (behavior unchanged from today's PR path) |
| `push` (main/develop) | **Smoke only**: Architecture Constraints, Lint & Format, Type Check (pyright), Security Scan (~2.5 min measured ≈ 4–5 min billed) |
| `schedule` (new nightly cron) | Full CI incl. E2E + Integration (~13 min) |
| `workflow_dispatch` | Full CI (manual debugging) |

> Update 2026-10-01 (PR #233): the three smoke jobs lint/typecheck/security
> are consolidated into the `quality` job ("Lint, Typecheck & Security");
> push smoke is now Detect Changes + Architecture + quality.

Implementation pattern — remove `github.event_name == 'push' ||` overrides;
expensive jobs get:

```yaml
if: >-
  github.event_name == 'schedule' ||
  github.event_name == 'workflow_dispatch' ||
  (github.event_name == 'pull_request' && <existing path/draft condition>)
```

`warnings-summary` must not run pointlessly when test-unit/frontend are
skipped on push: guard with
`if: always() && !cancelled() && needs.<x>.result != 'skipped'` style
conditions.

The nightly `schedule` trigger runs on the default branch — this makes the
nightly the post-merge safety net for regressions that bypassed PR review.

## 4. Decision 2 — Micro-Fixes (approved)

1. **Badge job**: commit message gets `[skip ci]` (GitHub honors it → badge
   pushes never re-trigger CI). Badge runs on push-to-main + schedule only.
2. **`timeout-minutes` on EVERY job.** Default is 360 min/job — a single hang
   can consume ~18% of the monthly quota. Suggested values: tiny jobs 5,
   smoke jobs 10, frontend/unit 20, integration/e2e 30.
3. **Nightly budget report**: ~10 s step in the nightly run that aggregates
   month-to-date job-minutes via GitHub API (`actions: read` permission,
   `GITHUB_TOKEN` — jobs endpoint, same aggregation as §2) and emits a
   warning annotation at >80 % of the 2000-min quota. Early warning instead
   of the "dead on the 14th" surprise.
4. **Phase 2 (optional, separate task)**: merge Lint+Typecheck+Security into
   one job (shared `uv sync`, saves ~2–3 min/run in setup + rounding).

## 5. Hardening (TanStack lessons → this repo's threat model)

### 5.1 SHA-pin all action refs
All ~20 `uses:` refs move from mutable tags (`@v7`, `@v6`, `@v4`, `@v1.12.2`,
`@v5` …) to full 40-char commit SHAs + version comment:

```yaml
- uses: actions/checkout@<full-sha> # v7.0.1
```

Dependabot's `github_actions` ecosystem (already active) keeps SHA-pinned
actions updatable. Closes the tag-poisoning vector (xygeni-action incident
03/2026; TanStack's org-wide pinning response).

### 5.2 zizmor as blocking PR check
Small dedicated job, runs only when `.github/**` changed (the
`changes.workflows` filter output already exists!) plus in the nightly.
**Plain CLI, blocking exit code — NO SARIF/code-scanning upload**: this repo
is private on the Free plan (no GHAS → code scanning unavailable). Config
`.github/zizmor.yml` enables `unpinned-uses` (pedantic-level rule) alongside
the defaults. zizmor itself must be SHA-pinned like every other action.

### 5.3 CODEOWNERS for `.github/`
`.github/` gets an owner entry → workflow changes require owner review.
Pairs with 5.2: zizmor catches mechanical issues, CODEOWNERS catches design
issues.

### 5.4 `persist-credentials: false`
On all `actions/checkout` steps EXCEPT the badge job (which needs the token
to push). Rationale: architecture/lint/typecheck/security/test jobs execute
PR-supplied scripts (`scripts/*.py`) — defense in depth against the repo
token persisting in those workspaces.

### 5.5 Caches stay (explicit divergence from TanStack)
TanStack removed caches because a fork-writable cache poisoned a job that
held an npm publish token. That path does not exist here: no
`pull_request_target` anywhere, no publish tokens in CI (release-please uses
only `GITHUB_TOKEN`), and under a plain `pull_request` trigger fork-PR caches
are scope-isolated to the PR and cannot poison main-branch caches. Caches
REDUCE minutes here — removing them would worsen the quota problem.
`pnpm@11.5.2` already provides `minimumReleaseAge: 1440` (24 h install
cooldown) by default — documented, not configured.

## 6. Cost Forecast (monthly, ~126 merges/PRs + nightly)

| Item | Status quo (extrapolated) | After design |
|---|---|---|
| push on main | ~1900 min | ~550 min (smoke × merges) |
| PR runs | ~950 min | ~950 min (unchanged, path-gated) |
| nightly full | — | ~390 min |
| **Total** | **~2850 min** (quota dead by the 14th) | **~1900 min** + budget report as early warning |

Biggest lever remains behavioral (PO ruling 1): agents stop pushing directly
to `main`; work flows through PRs. If push frequency to main drops to merge
level only, the smoke row shrinks further (~225 min).

**Risk disclosure — PR volume assumption.** The ~950-min PR row assumes
agents batch work into ~100 PRs/month (~9.4 min per path-gated PR, as
measured on today's PRs). If instead every one of today's ~270 monthly direct
pushes becomes its own PR, the PR row grows to ~2500 min and the quota breaks
again. Guardrails: the nightly budget report (§4.3) surfaces this within a
day, and the reserve levers are Phase 2 consolidation (§4.4), weekly-instead-
of-daily nightly (§8), and draft-PR cheap-gating. Batching discipline is part
of PO ruling 1, not optional.

## 7. Verification

- Local before commit: YAML validation + `actionlint` + `zizmor` run locally.
- Post-merge observation:
  1. one push to `main` → only smoke jobs run (~4 jobs);
  2. one backend-only PR → Frontend job skips;
  3. next nightly → full matrix runs, budget report posts.
- `scripts/check_architecture.py` stays green (workflow files are inputs to
  the gate-drift check).

## 8. Open Items

- Phase 2 job consolidation (§4.4) — separate small task after this lands.
- pyright `actions/cache@v6` (combined, auto-save-on-exit) → split into
  `actions/cache/restore` + explicit gated save, following the TanStack
  lesson of making cache writes visible/auditable. Low urgency (no secrets in
  that job), do together with Phase 2.
- Revisit quota if PR volume grows: weekly full nightly instead of daily is
  the next reserve lever (PO explicitly declined for now — ruling 2).
