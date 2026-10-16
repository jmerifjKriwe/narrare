# W0-1 — Push-Run Failure Cluster Diagnosis (2026-09-15 .. 2026-10-15)

> **Task:** W0-1 of `docs/superpowers/specs/2026-10-16-ci-r1-event-driven-redesign.md`
> **Method:** `gh api` (runs, jobs, check-run annotations) over all 25 failed CI push
> runs in the window. Read-only; no repo/workflow changes.
> **Headline:** The "24-run recurring main-gate failure cluster" is **not a check
> failure at all**. All 24 runs were **GitHub Actions billing blocks** — the jobs were
> never started ("The job was not started because recent account payments have failed
> or your spending limit needs to be increased"). The 25th failure (Oct 1) was a
> genuine `tsc` failure from the msw v2→v3 dependabot merge, fixed 32 minutes later.

---

## 1. Run table (all failed CI `push` runs in window)

25/60 push runs failed. Clusters: **A = billing block (24)**, **B = msw/tsc (1)**.

| # | Run ID | Date (UTC) | Head SHA | Failed jobs | Cluster |
|---|---|---|---|---|---|
| 1 | 34995957059 | 09-15 16:35 | 2c2d1b2 | changes+arch+warnings | A |
| 2 | 35007949237 | 09-15 18:30 | 472ca88 | changes+arch+warnings | A |
| 3 | 35015172080 | 09-15 19:42 | 2ed5e8c | changes+arch+warnings | A |
| 4 | 35017767674 | 09-15 20:08 | 6e0ec8e | changes+arch+warnings | A |
| 5 | 35113418218 | 09-16 15:09 | 237b520 | changes+arch+warnings | A |
| 6 | 35116694792 | 09-16 15:38 | 87e1368 | changes+arch+warnings | A |
| 7 | 35122556689 | 09-16 16:32 | 5e1c943 | changes+arch+warnings | A |
| 8 | 35130086817 | 09-16 17:44 | 09efd6a | changes+arch+warnings | A |
| 9 | 35134092293 | 09-16 18:23 | adc6a8a | changes+arch+warnings | A |
| 10 | 35137053663 | 09-16 18:51 | 5a02fed | changes+arch+warnings | A |
| 11 | 36532487736 | 09-29 06:42 | 4806c59 | changes+arch+warnings | A |
| 12 | 36536319465 | 09-29 07:23 | 9788a32 | changes+arch+warnings | A |
| 13 | 36540278827 | 09-29 08:02 | c0d231a | changes+arch+warnings | A |
| 14 | 36544296060 | 09-29 08:41 | c301ee4 | changes+arch+warnings | A |
| 15 | 36547607913 | 09-29 09:12 | e077ee8 | changes+arch+warnings | A |
| 16 | 36560038178 | 09-29 11:09 | 5e50ec9 | changes+arch+warnings | A |
| 17 | 36562760243 | 09-29 11:36 | c40810e | changes+arch+warnings | A |
| 18 | 36570953105 | 09-29 12:51 | 92866d5 | changes+arch+warnings | A |
| 19 | 36575406073 | 09-29 13:28 | 4d195d8 | changes+arch+warnings | A |
| 20 | 36580208368 | 09-29 14:06 | 78fb0ea | changes+arch+warnings | A |
| 21 | 36597439738 | 09-29 16:24 | ebd1bb2 | changes+arch+warnings | A |
| 22 | 36607810411 | 09-29 17:50 | 907ac63 | changes+arch+warnings | A |
| 23 | 36725137459 | 09-30 13:54 | d2dd0d4 | changes+arch+warnings | A |
| 24 | 36727720436 | 09-30 14:15 | e28af2a | changes+arch+warnings | A |
| 25 | 36914715471 | 10-01 19:29 | 6a8744c | Frontend (Type check) + E2E (Build frontend) | B |

Pre-window footnote: run 34909191798 (09-14 23:30) + Release Please 34909191791 show the
identical Cluster-A signature — the billing window actually opens 09-14 23:30.

Every run after 10-01 21:52 succeeded — **34 consecutive green push runs, 10-02..10-15**.

## 2. Signature clusters

### Cluster A — Billing block (24 runs, two incident windows)

**Signature:** `Detect Changes` + `Architecture Constraints` + `warnings-summary`
conclusion `failure`; ALL `needs`-gated jobs `skipped`; **zero steps executed in the
failed jobs** (jobs API: `steps=[]` for every job in the run); no logs ever written
(job-log endpoint → Azure `BlobNotFound`, `gh run view --log-failed` empty, logs zip 0
bytes). Annotation on every failed check-run:

> *"The job was not started because recent account payments have failed or your
> spending limit needs to be increased. Please check the 'Billing & plans' section in
> your settings"*

**Windows:** 09-14 23:30 → 09-16 18:51 (11 CI runs incl. pre-window) and
09-29 06:42 → 09-30 14:15 (14 runs). Recovery is visible at the next push with **no
intervening repo change** (no pushes at all 09-17..09-28; none 09-30 14:15..10-01 18:22).

**Cross-workflow corroboration (decisive):** the Release Please workflow — different
jobs, same push events — failed at **exactly the same timestamps** in both windows
(25 push runs of Release Please, 09-14..09-30, one-to-one with the CI failures). Two
independent workflows failing minute-identically is an account-level cause, not repo
content.

**Why exactly those 3 jobs?** In `ci.yml`, `changes` (Detect Changes) and
`architecture` are the only root jobs (no `needs`), and `warnings-summary` is gated
`if: always() && !cancelled()` (ci.yml:1128–1131), so these three are created at run
start regardless of the skip chain. When billing blocks, GitHub marks the already-
created jobs `failure` and never creates the dependent ones → `skipped`. The "cluster
at changes/architecture" is therefore an artifact of **job topology**, not of those
checks' content.

**Root-cause chain (≥2× why):**
1. Why did the runs fail? → The three initially-created jobs were refused by GitHub
   with a billing annotation; nothing ever executed (steps=0, no logs).
2. Why the billing block? → Account-level payment/spending-limit state. GitHub Free
   includes 2,000 min/mo; measured usage is ~2,078 min/30d (spec §3) — i.e. demand sits
   **above** the included quota, so once included minutes are exhausted (or the $0
   spending limit binds), all new job starts are refused until state changes.
3. Why did it *recur across weeks* and then *self-heal*? → The block is a property of
   the account, not the repo: it persisted across incident windows, vanished without
   any commit between failure and next success, and the failed jobs bill **0 minutes**
   (never started). Nothing in ci.yml or the checks influenced it either way.

**Categorization per task rubric:** neither (a) state/doc drift, nor (b) a broken
check, nor (c) flaky — it is **(d) account/billing infrastructure**. Direct pushes from
agent worktrees are **not** implicated; the identical block hit Release Please runs of
the same pushes, and the msw-merge run (a merge commit) ran normally in the same week.

**Flake evidence (same signature passing later without a fix):** conclusive —
- 09-30 14:15 failure → 10-01 18:22 success with **zero commits in between**;
- 09-16 18:51 → 09-29 06:42: identical signature resumed after a 12-day no-push gap,
  again without any CI/config change;
- all 34 post-10-01 runs green on unchanged workflow code.

### Cluster B — msw v3 type error (1 run, 10-01 19:29, genuine failure)

**Signature:** `Frontend` job, step `Type check` (tsc) exit 1 and `E2E Tests` job,
step `Build frontend` exit 1:
> *Object literal may only specify known properties, and 'onUnhandledRequest' does not
> exist in type 'PartialObjectDeep<SharedOptions, …>'*

**Root-cause chain (≥2× why):**
1. Why did type check fail? → 6a8744c5 (merge of `dependabot/npm_and_yarn/major-updates`,
   a 2-parent merge **pulled directly from an agent worktree without PR CI**) bumped
   `msw ^2.15.0 → ^3.0.0` in `packages/web/package.json`; msw v3 renamed
   `onUnhandledRequest` → `onUnhandledFrame`, and tsc's excess-property check rejects
   the obsolete option in the test setup.
2. Why did it land on main? → Merge-bot + worktree pushes bypass PR gating (no branch
   protection possible on GitHub Free); the dependabot branch's CI ran on its own
   branch event, but the tsc error surfaced only against the merged tree/state.
3. Why only 1 run? → Fixed 32 min later by 7cd43e26 *"fix(web): adapt test setup to
   msw 3 — onUnhandledRequest → onUnhandledFrame per installed v3 types"* (merged via
   fbd02a04, PR #232); all 6 subsequent pushes on 10-01 green.

**Flake evidence:** none — genuinely broken at that SHA, deterministically, fixed by
the named commit. The check worked exactly as designed. (Not part of the W0 cluster
premise: it failed in Frontend/E2E, not changes/architecture.)

**Boundary note (avoids re-diagnosis):** the post-10-08 nightly failures (schedule
runs, e.g. 38531844492, 38700481557) carry **real** test annotations
(TestingLibraryElementError, E2E exit 1) — those are the W0-3 streak, unrelated to
billing. The nightly did not exist before 10-03, so it has no billing-window overlap.

## 3. Fix scope (scoped only — NOT implemented)

| Cluster | Repo fix? | Scope | Regression test meaningful? |
|---|---|---|---|
| A — billing block (24 runs) | **No repo-code fix exists or is needed.** Actions: (1) PO one-time in GitHub settings → Billing: verify payment method and raise spending limit above $0 (API check requires `user` scope: `gh api /users/…/settings/billing/actions` → 403 here); (2) reduce demand below the 2,000-min quota — that is exactly Waves 1–3 of the spec; (3) optionally treat billing-annotated runs as "not-a-code-failure" in dashboards (annotation string is machine-detectable) | 0 workflow files, 0 LOC (settings + budget only) | **No** — billing state cannot be reproduced in CI; a test would be theater |
| B — msw v3 tsc (1 run) | **Already fixed on main** (7cd43e26). Residual is process, not code: merge commits pulled from dependabot/worktree branches bypass PR CI; the durable mitigation is the spec's PR-gating discipline, not a new file | 0 files, 0 LOC (closed) | **No** — tsc *is* the regression guard and it caught the break; no test gap exists |

**Spec-impact corrections (for the PO/architecture):**
1. §3's "24-run recurring main-gate failure cluster, root cause unknown" resolves to a
   billing artifact; **W0-2's premise ("root-cause fix + regression test, 5 green runs")
   has no repo-side implementation**. Recommend re-scoping W0-2 to the PO billing
   action + a red-run classification note, and treating the green-streak gate as
   already satisfied (34 consecutive green since 10-02).
2. §9.1's Wave-0 credit (−300..−400 min/mo "red-run churn") **overstates savings** for
   the push cluster: billing-blocked jobs never started → **0 billed minutes** for all
   24 runs. The real Wave-0 minute win is only the nightly-streak half (W0-3/W0-4);
   the push-cluster win is signal hygiene (no red noise), not minutes.
3. The measured baseline's "CI push 438 min / 60 runs" is unaffected (failed runs
   contributed ~0 billed minutes), so Wave-1 push-slim math stands.

## 4. Evidence excerpts

1. Check-run annotation, all 24 Cluster-A failed jobs:
   `The job was not started because recent account payments have failed or your spending limit needs to be increased.`
2. Jobs API, run 35007949237: `104512346690 Detect Changes failure steps=0` ·
   `104512347331 Architecture Constraints failure steps=0` · `104512365541 warnings-summary…` — and logs endpoint →
   `<Error><Code>BlobNotFound</Code><Message>The specified blob does not exist.` (jobs never ran).
3. Check-run annotation, run 36914715471 (Cluster B):
   `Object literal may only specify known properties, and 'onUnhandledRequest' does not exist in type 'PartialObjectDeep<SharedOptions, …>'`
4. `git show 6a8744c5`: `packages/web/package.json | 2 +-` with `- "msw": "^2.15.0"` / `+ "msw": "^3.0.0"`;
   fix commit 7cd43e26 `fix(web): adapt test setup to msw 3 — onUnhandledRequest → onUnhandledFrame` (32 min later).
5. Cross-workflow corroboration: Release Please push runs fail at identical timestamps
   (e.g. CI 36532487736 ↔ RP 36532487776, both 09-29 06:42; CI 34995957059 ↔ RP 34995957079, 09-15 16:35).

— Platform layer, 2026-10-16
