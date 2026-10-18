# W0 Round 2 — Both Post-#258 Nightlies Failed: GitHub Actions Billing Outage (NEW Cluster E)

> **Task:** W0 round 2 diagnosis — the two nightlies after PR #258 (squash `10d9bec6`,
> merged 2026-10-17T07:00:25Z) both failed, breaking the W0 formal gate
> (3 consecutive green nightlies).
> **Date:** 2026-10-18 · **Author:** Platform layer (read-only, log/annotation analysis)
> **Method:** `gh api` run/job/check-run annotation analysis; local checkout verified at
> `10d9bec6` (the merged head). No repo edits; this note is the only file written.
> **Headline:** **Not a code failure.** Every job since 2026-10-17T07:00Z fails before
> step 0 with an account billing annotation. The W0 fixes from #258 never executed —
> zero evidence about their quality. The 3-green-nightly clock is suspended, not lost.

---

## 1. Run table (CI workflow, 2026-10-16 → 2026-10-18)

| Run | Date (UTC) | Event | Head | Result | What happened |
|---|---|---|---|---|---|
| 38936245638 | 10-16 16:59 | pull_request | `4a0e34a2` (#258 branch) | ✅ success | 10 jobs green (E2E skipped per known gate hole) — **last green run before outage** |
| 39012015022 | 10-17 07:00 | push | `10d9bec6` (#258 merge) | ❌ failure | `release-please` job: **billing annotation**, 0 steps |
| 39012015162 | 10-17 07:00 | push | `10d9bec6` | ❌ failure | Detect Changes + Architecture Constraints: **billing annotation**, 0 steps; all test jobs skipped |
| **39012581075** | **10-17 07:09** | **schedule** | **`10d9bec6`** | ❌ **failure** | **Nightly 1** — Detect Changes, Quota Budget Report, Architecture Constraints: **billing annotation**, 0 steps; 9 downstream jobs skipped |
| **39107505608** | **10-18 07:23** | **schedule** | **`10d9bec6`** | ❌ **failure** | **Nightly 2** — identical: same 3 root jobs, same annotation, 0 steps; 10 downstream jobs skipped |
| 39111657309 | 10-18 08:29 | pull_request | `8de4d5bf` (open W1 branch) | ❌ failure | Same billing annotation on Detect Changes + Architecture Constraints (incl. new "Nightly Gate" job, skipped) |

**Onset window:** 2026-10-16T17:00Z (last green) → 2026-10-17T07:00Z (first red).
**Every** Actions run in both repos workflows since onset is red with the same
annotation, across three different head SHAs (`10d9bec6`, `8de4d5bf`) and two
workflows (CI, Release Please).

## 2. Per-job conclusions — the two nightlies

### Nightly 39012581075 (2026-10-17T07:09:31Z, attempt 1, `10d9bec6`)

| Job | Job ID | Conclusion | Steps executed | Duration |
|---|---|---|---|---|
| Detect Changes | 117338052932 | ❌ failure | **0** | 3s |
| Quota Budget Report | 117338053078 | ❌ failure | **0** | 2s |
| Architecture Constraints | 117338053157 | ❌ failure | **0** | 2s |
| Frontend / zizmor / Frontend Smoke / Unit / Lint-Typecheck-Security / warnings-summary / Coverage Badge / E2E / Integration | — | skipped (needs failed) | — | — |

### Nightly 39107505608 (2026-10-18T07:23:53Z, attempt 1, `10d9bec6`)

| Job | Job ID | Conclusion | Steps executed | Duration |
|---|---|---|---|---|
| Detect Changes | 117616438864 | ❌ failure | **0** | 4s |
| Quota Budget Report | 117616438722 | ❌ failure | **0** | 4s |
| Architecture Constraints | 117616438933 | ❌ failure | **0** | 4s |
| Frontend / zizmor / Frontend Smoke / Unit / Lint-Typecheck-Security / warnings-summary / Coverage Badge / E2E / Integration / Frontend Standalone Smoke | — | skipped | — | — |

`runner_name` is empty on every failed job — **no runner was ever allocated**.
Identical failure annotation on all 11 failing jobs across all 5 red runs:

```
The job was not started because recent account payments have failed or your
spending limit needs to be increased. Please check the 'Billing & plans'
section in your settings
```

## 3. Cluster E (NEW) — GitHub Actions account billing outage

**Signature:** job `conclusion: failure` with `steps: []` and empty `runner_name`,
completed in 2–4s, check-run annotation = payment/spending-limit message.
Hits root jobs (no `needs`) instantly; every `needs:`-dependent job → skipped.

**Root cause chain (≥2× why):**
1. *Why did both nightlies fail?* GitHub refused to start any hosted runner because the
   account's billing state is broken (failed payment or spending limit reached). The
   three root jobs fail at allocation time; all test jobs never run. Not caused by
   `10d9bec6`: Release Please (zero repo code) and the next PR's CI fail identically.
2. *Why did it coincide with the #258 merge?* Coincidence of timing: the outage began in
   the 14-hour window between #258's fully green PR CI (10-16 16:59Z) and the merge push
   (10-17 07:00Z). The first billable run after onset was the merge push; the schedule
   cadence then propagated two red nightlies.
3. *Why does this break the W0 formal gate?* The gate requires 3 consecutive green
   nightlies, but an account-level outage makes every run red regardless of code — and
   nothing in the repo (no streak bookkeeping exists at `10d9bec6`) can distinguish
   "tests failed" from "runners never started", since the billing evidence lives only in
   check-run annotations, invisible to workflow logic.

## 4. Comparison against the W0-3 clusters — verdicts

| Job (both nightlies) | Verdict vs. W0-3 | Reasoning |
|---|---|---|
| Detect Changes | **NEW — Cluster E** | Zero steps; W0-3 never saw this job fail (it was the needs-root that fanned out skips) |
| Quota Budget Report | **NEW — Cluster E** | Zero steps; same annotation |
| Architecture Constraints | **NEW — Cluster E** | Specifically **not** cluster C (uv/CPython drift): Oct-10 failed *inside* `uv sync` with a psycopg cp315 wheel error; here no step ran at all. The #258 `UV_PYTHON` 3.14 pin is present at `10d9bec6` (ci.yml ~line 190) but unexecuted |
| E2E / Frontend / Unit / Integration | **Not assessable** | Skipped. Cluster A (E2E timeout flake) and B (KBEnhanceReview vitest flake) had **no opportunity to resurface** — the W0 fixes (hydration-safe waits in `tests/e2e/foundation.py`, `helpers/editor_ai.py`, vitest race fix) never ran. No evidence they are insufficient; no evidence they work either |
| Cluster D (FK noise) | Not assessable | No API logs produced (no steps ran) |

**Conclusion:** the W0 gate is **suspended by an infrastructure outage, not broken by a
code regression**. The streak counter cannot advance until billing is restored.

## 5. Fix scope (NOT implemented — no repo edits made)

| Fix | Files | Est. LOC | Notes |
|---|---|---|---|
| **E (primary) — restore billing** | none (GitHub account Settings → Billing & plans: fix payment method / raise spending limit) | 0 | Owner/ops action, blocks all CI. After restore: trigger `gh workflow run ci.yml` (workflow_dispatch) to verify recovery and re-baseline before counting the streak again |
| **E (repo-side guard, optional, fold into in-flight W1 gate work)** | `.github/workflows/ci.yml` on the W1 branch (head `8de4d5bf` — the PR run shows a new "Nightly Gate" job; not yet on `main`) | ~20–40 | Infra-outage discrimination: treat a needs-job failure with zero executed steps (or billing annotation surfaced via a pre-job API check) as "not counted"/auto-rerun-once, so the 3-green streak isn't reset by account outages |
| **Side risk (flag only, cluster-C family)** | watch-only | 0 | Every failed job carries: *"The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026"* (actions/runner-images#14748). The first post-fix nightly lands on a new OS image — ci.yml notes font-rendering-sensitive baselines (VRT); expect possible one-off drift, don't misread it as a W0 regression |

## 6. Key evidence

```
# Check-run annotation, identical on ALL 11 failing jobs across 5 runs (10-17/10-18):
"The job was not started because recent account payments have failed or your
spending limit needs to be increased. Please check the 'Billing & plans' section in your settings"

# Nightly 1, Detect Changes (job 117338052932): API job object
conclusion: "failure", steps: [], runner_name: "",
started 2026-10-17T07:09:31Z → completed 07:09:34Z (3s)

# Push run on the #258 merge commit (39012015162, 10-17 07:00:27Z) — same annotation,
# all test jobs skipped → outage predates any test execution of 10d9bec6

# Last green run anywhere: 38936245638 (PR #258 CI, 10-16 16:59Z, head 4a0e34a2):
10 jobs success (Architecture, Detect Changes, zizmor, Frontend Smoke, Frontend,
Lint/Typecheck/Security, Unit, Integration, warnings-summary; E2E skipped)

# Every failed job also carries a NOTICE annotation:
"The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026"
(https://github.com/actions/runner-images/issues/14748)
```

## 7. Bottom line for the W0 gate

1. The two red nightlies are **not** evidence against the #258 W0 fixes — no test ever ran.
2. Resolve billing first; then run one **workflow_dispatch** CI to confirm recovery;
   the 3-consecutive-green count restarts from the first post-recovery nightly.
3. Unchanged from W0-3: `E2E Tests` is still skipped on `pull_request` (PR #258's own CI
   confirms it), so the merged W0-hardened E2E suite remains nightly-only-exercised —
   the W0-3 §4 gate-hole recommendation stands for W1.
