# CI R1 — Event-Driven Redesign: Implementation Spec

> **Status:** Approved direction (PO-sealed 2026-10-16; **amended in place 2026-10-16**:
> PO pulled reserve levers R1+R3+R5 into sealed scope, resolved OQ1/OQ2 — §5.8, §5.9,
> §9.2, §14; **amended in place again 2026-10-16 (2nd)**: PO adopted E2E path-gated on
> PRs citing the W0-3 diagnosis (§5.10, W1-12); Wave-0 outcomes recorded — §10;
> **amended in place 2026-10-18 (3rd)**: Actions billing outage #3 → November billing
> mode — local-gate merge criterion for PR #259, deferred-then-resumed formal gates,
> schedule-noise ruling, W0-2 addendum — §15) — implementation spec, binding
> **Spec author:** Architecture layer
> **Partially supersedes:** `docs/superpowers/specs/2026-09-29-ci-minutes-hardening-design.md` (see §2)
> **Baseline window (measured):** 2026-09-15 .. 2026-10-15, repo `jmerifjKriwe/narrare`
> **Target (amended 2×):** central ~1,520–1,540 billable min/mo (corridor ~1,430–1,680)
> without meaningful quality loss (bottom-up per row in §9.1; includes the PO-adopted
> E2E-on-PR gain of +18..36 min/mo — §5.10; the pre-amendment 950–1,150 corridor proved
> unreachable without the reserve levers — §9.2, §14 OQ1)

---

## 1. Goal & Non-Goals

**Goal.** Cut monthly GitHub Actions billable minutes from the measured ~2,078 min/30d
(projection with daily full nightly: ~2,600/mo; quota 2,000 on GitHub Free) toward the
**amended PO target of ~1,520–1,540 min/mo central (corridor ~1,430–1,680)** — without
meaningful quality loss — by making every minute event-driven: CI work runs when (and
only when) the thing it verifies changed, plus a bounded periodic probe for world
drift. The amended target includes the PO-adopted levers **R1** (behavioral PR
discipline, §5.9), **R3** (quality folded into test-unit on PR/nightly paths, §5.8)
and **R5** (absorbed into R3), plus — second amendment, post-Wave-0 — **E2E
path-gated on PRs** (§5.10): a deliberate quality gain purchased at +18..36 min/mo.

**Non-Goals.**

- No runner changes (sealed: no self-hosted, no ARM, no larger runners).
- Repo stays private (sealed: not made public for free minutes).
- No GitHub Pro investment (sealed).
- Caches stay (old spec §5.5, explicitly reaffirmed) — this spec ADDS caches (Wave 3).
- SHA-pinning, zizmor, `persist-credentials: false`, `timeout-minutes` discipline stays.
- No change to PR concurrency semantics (cancel-in-progress on PRs; nightly never
  cancellable by pushes).
- Eval Nightly stays `disabled_manually` (0 runs; out of scope).
- Mutation monthly stays as-is (1 run, 2 min, cache-noop — not minutes-relevant).
- No behavioral mandate enforcement in CI (branch protection is UNAVAILABLE on GitHub
  Free — API returns 403; no required checks exist or can exist). The R1 PR-discipline
  ruling (§5.9) is likewise PO-enforced process, never CI-enforced.

---

## 2. Superseded rulings (explicit)

The following rulings from `2026-09-29-ci-minutes-hardening-design.md` are **superseded**
by PO decisions sealed 2026-10-16:

| Old ruling | Old content | New ruling (this spec) |
|---|---|---|
| Ruling 2 (§1, §8) | "Off-PR cadence = nightly FULL run (daily), weekly declined" | **Event-driven incremental nightly**: daily cron stays, but a gate job decides per component whether anything changed since the last *successful* nightly's SHA; unchanged components skip. Optional weekly full probe — spec recommends YES (§5.1.4). |
| §3 push smoke composition | Push = changes + Architecture + quality (always all three) | Push = **changes + architecture always; quality only when the push touched code paths** (§5.3). |

Rulings from the old spec that **explicitly still stand**:

- Ruling 1: PRs are the CI gate; push CI = smoke only (this spec slims the smoke further).
- No self-hosted runners; repo stays private; no GitHub Pro.
- Caches stay and reduce minutes (§5.5 old spec).
- All hardening (SHA-pins, zizmor blocking, CODEOWNERS for `.github/`,
  `persist-credentials: false`, `timeout-minutes` everywhere) stays.
- Budget report as early warning stays (cadence changes: nightly → weekly, §5.7).
- Nightly schedule keeps the 02:37 UTC off-peak slot (validated vs GitHub scheduler
  skipping; see ci.yml lines 50–57).

---

## 3. Measured baseline (2026-09-15 .. 2026-10-15)

All numbers are per-job **billed** minutes (each job rounds up to 1 min). Block sums
reproduce the reported totals within rounding.

| Block | Runs | Min | Per-run / per-job detail |
|---|---|---|---|
| CI `pull_request` | 84 | **984** | Frontend 7.54 (×24), Integration 7.38 (×32), Unit 3.99 (×32), quality 3.55 (×31), Frontend-Standalone 1.24 (×27), architecture 0.79 (×54), changes 0.13 (×84), warnings-summary 0.08 (×84), zizmor 0.21 (×7) |
| CI `push` (all main) | 60 | **438** | avg 7.3; smoke = changes+architecture+quality+warnings (≈1+1+4+1 billed) |
| CI `schedule` (nightly) | 13 | **482** | successful full nightly ≈ 38 job-min: Integration 10.35, Frontend 9.52, E2E 5.65, Unit 4.88, quality 3.73, budget-report 2.25, architecture 1.15, rest <0.5. **5 of last 7 FAILED** |
| Release Please | 60 | **103** | ~1.7/run, fires on every main push, mostly no-op |
| Mutation monthly | 1 | 2 | cache-noop, not minutes-relevant |
| Eval Nightly | 0 | 0 | `disabled_manually` |
| Dependabot `dynamic` | — | free | does not count toward quota |
| **Total billable** | | **~2,078** | projection with daily full nightly ≈ **2,600/mo** |

Context facts that shape the design:

- 168 commits on main = 152 direct (parents=1) + 16 merges, arriving in 60 push events
  (batched pushes, avg ~2.8 commits/push). Merge method: squash since ~Oct 9.
- 25/60 push runs FAILED — 24 clustered at changes/architecture (recurring main-gate
  failure cluster, root cause unknown at spec time → Wave 0; W0-1 resolved it: GitHub
  account billing blocks, jobs never started, **0 billed minutes** — §10).
- Nightly failure streak (Frontend + E2E since ~Oct 10–14) correlates with the merge of
  the E2E-specs wave PR #256 → Wave 0 (W0-3 confirmed the #256 correlation; its
  cluster A motivates the E2E-on-PR lever, §5.10 — §10).
- Release-please PR #231: 30 runs stuck `conclusion=action_required` (bot-authored
  workflow runs need manual approval on private repos). Zero minute cost, but stale.
- Branch protection on main: UNAVAILABLE (GitHub Free, 403). No required checks exist —
  this is why the draft-PR rerun gap (§5.5) is a real correctness hole, not a nit.

---

## 4. Design overview

Four waves, strictly ordered. Wave 0 first (stop the red-run burn — it is both a quality
gain and the precondition for trustworthy nightly gating: an event-driven nightly whose
base is "last successful nightly" degrades to full runs while nightlies fail).

```
Wave 0  diagnose + root-cause fix the two failure clusters     (quality GAIN, ~−150 min/mo churn — corrected post-W0-1, §10)
Wave 1  ci.yml trigger/job restructuring (event-driven nightly, push slim, PR fixes)
Wave 2  release-please flow slimming (variant b)
Wave 3  setup caches (Playwright, spaCy, export toolchain)
```

**Amendment (2026-10-16):** the sealed scope additionally includes **R1** (process
ruling, §5.9), **R3 with R5 absorbed** (§5.8), and the R1 monitoring metric (W1-11).
**R4** (drop Sunday probe) remains the only in-spec reserve lever (§9.2).

Invariants for ALL new/modified YAML (checked per task):

- Actions SHA-pinned with version comments (existing pins reused; no new unpinned `uses:`).
- `persist-credentials: false` on every `actions/checkout` that doesn't need the token.
- `timeout-minutes` on every job.
- Canonical ternary form only (zizmor `unsound-ternary`): the *falsy-safe* direction,
  e.g. `fetch-depth: ${{ github.event_name != 'schedule' && 1 || 0 }}`. NEVER
  `== 'schedule' && 0 || 1` (true-branch 0 is falsy, `|| 1` always wins).
- Concurrency group unchanged:
  `${{ github.workflow }}-${{ github.event_name }}-${{ github.ref }}` with
  `cancel-in-progress` on PRs only — the nightly can never be cancelled by a push.
- No `pull_request_target`, no secrets beyond `GITHUB_TOKEN`, job-level minimal
  permissions.
- Local composite actions (introduced by §5.8) carry no third-party `uses:`; their
  steps are **moved verbatim** from the original job, never retyped — parity between
  the folded block and the push job must be structural, not discipline-dependent.

---

## 5. Wave 1 design — ci.yml trigger/job restructuring (approved direction, made precise)

### 5.1 Event-driven nightly (items 1+2 of the approved direction)

**Mechanism (verified).** A new `nightly-gate` job runs on the 02:37 cron. It:

1. Queries the last *successful* schedule run of `ci.yml` and its `head_sha`:
   `GET /repos/{repo}/actions/workflows/ci.yml/runs?event=schedule&status=success&per_page=1`
   → `head_sha` (job-level `permissions: actions: read`; `GH_TOKEN: ${{ github.token }}`
   via `env:`). Retry with backoff on 429/5xx (same pattern as budget-report,
   ci.yml lines 1190–1203).
2. Checkouts with `fetch-depth: 0` (the base SHA can be arbitrarily old; dorny
   fetch-doubling then never surprises).
3. Runs `dorny/paths-filter@ceb8a2b…` (existing SHA pin) with
   `base: ${{ steps.lastgreen.outputs.sha }}`. **Verified semantics** (dorny v4 README):
   on non-PR events with `base` = commit SHA, changes are detected against that commit
   via git; if the base has no common ancestor with HEAD (force-push/rebase) or history
   is empty, **all files are considered added → fail-open to a full nightly.** That is
   the desired safe direction and is documented as such.
4. Emits outputs:
   - `should_run` — `false` when no nightly-relevant path changed since base (idle day)
   - `backend`, `frontend`, `workflows` — component deltas since base
   - `e2e` — computed `backend || frontend` (E2E is full-stack)
   - `probe` — `true` on the weekly full-probe day (§5.1.4)
5. On `workflow_dispatch`: `should_run: true`, all components `true` (manual = full
   matrix, current behavior preserved; no base comparison).

All expensive jobs rewire from `github.event_name == 'schedule' || …` to
`needs.nightly-gate.outputs…` conditions:

| Job | New nightly condition (schedule path) |
|---|---|
| architecture | `should_run == 'true'` (always runs on active nights — universal fast-fail, incl. docs/eval/registry drift with no clean path mapping) |
| quality | **Folded into test-unit** (§5.8, amendment): no separate nightly quality job — the tool steps run as the first step-group inside test-unit, so they run exactly on unit nights (`should_run && (probe ‖ backend)`). Non-backend nights no longer run the Python-quality tools (inputs unchanged; gitleaks residual → §8). A push-only quality job remains (§5.3). |
| test-unit | `should_run && (probe ‖ backend)` |
| test-integration | `should_run && (probe ‖ backend)` |
| frontend | `should_run && (probe ‖ frontend ‖ workflows)` |
| test-e2e | `should_run && (probe ‖ e2e)`; PR path added by §5.10 (W1-12): `pull_request && draft != true && changes.e2e_specs` |
| zizmor | `should_run && (probe ‖ workflows)` |
| update-coverage-badge | **changed**: `github.event_name == 'schedule' && needs.test-unit.result == 'success'` — today it assumes the nightly always runs unit; with incremental nights unit may skip and the badge job would fail downloading a nonexistent artifact. |
| warnings-summary | unchanged logic (already result-aware via `!= 'skipped'`), gains `nightly-gate` in `needs` |
| budget-report | moves to its own weekly cron (§5.7) |
| release-orchestration | new Wave 2 job (§6) |

The `nightly-relevant` filter set for `should_run` = union of the existing `backend` +
`frontend` filter lists **plus** `.github/workflows/**` (workflow changes must wake the
nightly and self-exercise the matrix). It deliberately EXCLUDES pure docs — a docs-only
push day is an idle night. Exact list (reuse verbatim from the existing `changes` job,
ci.yml lines 130–164, so the two filters can never drift):

```
apps/** · packages/** · scripts/** · tests/** · evals/** · pyproject.toml · uv.lock ·
package.json · pnpm-lock.yaml · pnpm-workspace.yaml · .github/workflows/** · Dockerfile ·
docker-compose*.yml · justfile
```

**Common base, not per-component last-green (sealed).** Base = last successful nightly's
SHA for ALL components (simple, one gh-api call). A component runs when its delta
against that common base is non-empty. Consequence: if component X fails on night N, the
base stays at the last green SHA, so night N+1 re-runs X's accumulated delta — the design
is self-healing without per-component bookkeeping. *Per-component last-green state* is
named as an optional future refinement (needs persisted state; rejected for now —
complexity not justified by the corridor math).

**Idle-day cost.** The gate job (checkout full + gh api + dorny) ≈ 1–2 billed min/night;
all other jobs skip (skipped jobs are free).

**Nightly quality/coverage gating (amended).** The R3 fold (§5.8) dissolves the
quality→unit `needs` chain: the tools run inside test-unit, so unit nights exercise
them by construction; `update-coverage-badge` keeps its `needs.test-unit.result ==
'success'` guard. `test-integration` and `test-e2e` lose their `needs: [quality]`
edge and rewire to `architecture` (W1-4) — a missed rewire would silently skip them
once quality stops running on PR/nightly.

#### 5.1.4 Weekly full probe — RECOMMENDATION: YES

Add `probe: true` on Sundays (gate computes `date -u +%u` == 0), forcing the full
nightly matrix (~38 job-min + gate ≈ 39) regardless of deltas. Cost ≈ 4.3 × 39 ≈
**~168 min/mo** (included in the §9 forecast).

Rationale (why yes):

1. **World-drift blame isolation.** GitHub rotates runner images; this repo is unusually
   exposed (VRT screenshot baselines are font-rendering-sensitive — the reason frontend
   pins ubuntu-22.04, ci.yml lines 756–760). With a pure event-driven nightly, an
   environment change that breaks VRT would surface on the next *code* night and be
   mis-attributed to that code. A no-code-changed probe failure is unambiguously
   environmental.
2. **Idle-day flake detection.** Flaky tests that fail on fresh runners are today
   probed daily by the nightly; event-driven removes that. Weekly restores bounded
   detection (≤7d) at 6% of the old daily-probe cost.
3. **Exercises the "run everything" path weekly** — the incremental gating logic itself
   stays honest.

If the corridor math later forces a cut, dropping the probe is the first reserve lever
(§9.2, R4) — it is a single-line revert.

### 5.2 Incremental nightly per component

Covered by §5.1 (dorny filters computed against the common base). Each of
Frontend/Integration/Unit/E2E gates on its component's delta (E2E on backend ∨ frontend
nightly; on PRs, E2E gates on `e2e_specs` — §5.10).
Cross-component safety: because E2E runs when EITHER side changed, every active night
with code changes exercises the full stack end-to-end — the residual cross-component
blind spot is negligible (see quality-loss register §8).

### 5.3 Push slim: quality becomes path-filtered

Push smoke = `changes` + `architecture` **always**; `quality` runs only when the push
touched code paths. Implementation: job-level gating (extend the existing `changes` job
with a `code` filter consumed by `quality`'s `if`), NOT a workflow-level `on.push.paths`
(a workflow-level filter would also suppress changes/architecture on docs pushes —
violating the "always" requirement — and would change PR behavior).

`code` filter (exact, sealed in the brief; superset-check against measured push mix
done — docs/`CURRENT_STATE`-style pushes are the target):

```
apps/api/** · packages/** · scripts/** · evals/** · pyproject.toml · uv.lock
```

Rationale: 152 of 168 monthly main commits are direct pushes that bypass PR gating; the
path filter keeps same-push detection (quality: ruff, pyright, gitleaks, bandit,
pip-audit) for anything that can affect those tools' inputs, and skips pure
docs/state-machine pushes. pyright/ruff/bandit/pip-audit inputs are exactly the listed
paths (gitleaks on push scans shallow anyway; `pyproject.toml`/`uv.lock` are included).

Measured effect estimate: ~15/60 pushes are docs-only → saves ~15 × 4 ≈ 60 min/mo.

**R3 reconciliation (amendment 2026-10-16).** This push quality job is exactly what
R3 keeps alive: the fold (§5.8) merges quality into test-unit on the **PR and nightly
paths only** — the job above remains the ONLY quality gate for the ~152 direct code
pushes/month (PRs cannot gate them) and keeps the identical tool set via the shared
composite action. The `code` filter stays as sealed.

### 5.4 test-unit PR-gating on `needs.changes.outputs.backend == 'true'`

Today test-unit runs on EVERY PR-triggered run (ci.yml lines 451–454 have no path
condition) — docs/ADR/CURRENT_STATE PRs pay ~4 min each. New PR condition:

```yaml
if: >-
  github.event_name == 'schedule' || github.event_name == 'workflow_dispatch' ||
  (github.event_name == 'pull_request' &&
   (needs.nightly-gate.outputs.backend == 'true' || needs.changes.outputs.backend == 'true'))
```

(concrete splice finalized in W1-4; PR path consults `changes` as today, nightly
path consults the gate). **Amendment (R3/R5):** this condition now also carries the
folded quality tools (§5.8) — frontend-only, docs-only and workflows-only PRs skip
ruff/pyright/gitleaks/bandit/pip-audit along with unit. No tool input changes in such
PRs (the `backend` filter covers them; W1-4 adds `.gitleaks.toml` to it) — except
gitleaks' whole-tree secret scan, whose residual is registered in §8. Scripts that
docs-PRs could plausibly break (`check_doc_drift`, `check_adr_naming`,
`check_current_state_facts`, …) all run in the **architecture** job, which is not
path-gated on PRs.

### 5.5 `on.pull_request.types: [opened, synchronize, reopened, ready_for_review]`

Correctness fix. Default PR types omit `ready_for_review`, so jobs that skip drafts
(Integration, Frontend — and, once §5.10 lands, E2E on the PR path —
`github.event.pull_request.draft != true` guards) **never rerun**
when a draft is marked ready; with no branch protection (GitHub Free) nothing catches
the gap — a draft-red PR can be merged with its Integration/Frontend checks never having
run on the final code.

Cost (explicit, sealed): +1 CI run per draft→ready transition (est. ~8/mo × ~half-matrix
≈ +8..15 min/mo). This buys back a real gating hole; accepted.

### 5.6 Fold frontend-standalone into the frontend job

The standalone boot smoke (PR-only blind-spot guard, ci.yml lines 889–958) becomes a
post-`Build` step inside the `frontend` job: reuse the Build output, copy
static/public into the standalone tree, boot `server.js`, curl :3000 (steps lifted
verbatim from the standalone job). Frontend job stays on ubuntu-22.04 — the boot smoke
is not font-sensitive, and colocating avoids a second pnpm-install+build entirely.

Net minutes ≈ neutral-to-slightly-negative on paper (−27 standalone runs × 2 billed ≈
−54; +~1 min smoke on ~24 frontend runs ≈ +24; net ≈ −30/mo) — the real win is one
fewer job, less queueing, and the smoke now also runs on frontend-active nights.

### 5.7 Budget-report weekly

`budget-report` moves from nightly to its own Sunday cron (`7 3 * * 0`, off-peak like
02:37). Mechanism: second `schedule` entry; the job discriminates via
`github.event.schedule == '7 3 * * 0'`; `nightly-gate` adds
`if: github.event_name != 'schedule' || github.event.schedule == '37 2 * * *'` so the
gate doesn't run (and bill) on budget nights. Quality-loss register: quota-overrun
detection latency 1d → 7d (§8) — acceptable with the ~2× headroom the corridor provides.

### 5.8 R3 — quality folds into test-unit on PR/nightly paths (PO-adopted 2026-10-16)

**Conflict resolved.** §9.2's original R3 one-liner ("merge quality into test-unit")
collided with §5.3: a path-filtered `quality` job on PUSH is the only gate for the
~152 direct code pushes/month, and test-unit does not run on push — a blind fold
would strip ruff/pyright/gitleaks/bandit/pip-audit from the direct-push path.

**Decision — option (a):** the quality tool steps (ruff check/format, pyright +
pyright-tests, gitleaks, bandit, pip-audit, incl. the Pyright cache restore/save
steps) move INTO `test-unit` as a step-group ahead of pytest, on the **PR and nightly
paths**; the `quality` job survives as a **push-only** job (§5.3) with the identical
tool set. **R5 is thereby fully absorbed**: the folded tools inherit test-unit's
`backend`-gated condition (§5.4), so non-backend PR runs skip them — which R5 would
have achieved with a separate `if`, minus one job.

Mechanics (verified against current ci.yml):

- The shared steps live ONCE in a new local composite action
  `.github/actions/quality/action.yml` — **tool steps only** (ruff → pip-audit + the
  Pyright cache restore/save). Both call sites run it after their own
  checkout/setup-uv/sync; the per-job setup stays per-job because it legitimately
  differs (push: `fetch-depth: 0` for the gitleaks full-history scan; test-unit:
  reuses its own checkout for pytest). The cache-save `if`
  (`schedule ‖ push-main`) evaluates identically inside the composite.
- `test-unit`: sync becomes `uv sync --frozen --all-packages --group dev --extra
  embeddings` (pyright requires the embeddings extra — today only quality syncs it;
  with `setup-uv` caching the delta is ~0.1–0.3 min), `needs: [architecture,
  changes]` (replacing the dissolved `[quality]` edge with its own predecessor), and
  its `if` gains the PR-backend gate — one combined condition (§5.4).
- `test-integration` and `test-e2e`: `needs: [quality, …]` → `needs: [architecture,
  …]`. These rewires are load-bearing: a job whose `needs` references the now
  push-only quality would be **silently skipped** on every PR and nightly run.
- `changes.backend` gains `.gitleaks.toml` (tool-input parity: a gitleaks-config-only
  PR still exercises the folded tools; same precedent as `pyproject.toml`/`uv.lock`
  already in that filter). The §5.1 nightly-relevant list inherits it via the
  reuse-verbatim rule.
- `warnings-summary` and `update-coverage-badge` need no change (they gate on
  test-unit/frontend results, not on quality).

**Alternatives evaluated (rejected):**

- **(b) Extend test-unit's `if` to push-when-code-changed** (one job everywhere):
  every code push would run the full unit suite — ~45 code pushes/mo × (unit ~4 +
  folded tools ~2.8 − quality-alone ~3.5) ≈ **+150–190 min/mo**, i.e. paying ~3×
  R3's saving to realize it. Rejected on arithmetic alone (it would also buy a
  push-time unit-test quality gain the PO did not ask for).
- **(c) Keep quality a separate job everywhere; drop R3's saving from the forecast:**
  honest and simplest, but it refuses a PO-adopted merge that is safe once the push
  job stays, forfeiting the fold's ~40–50 min/mo of real overhead (setup + one
  job-rounding per backend run/night) while R5 would then need its own separate `if`
  task. No compensating gain. Rejected.
- **(d) Drop push quality entirely (nightly backstop only):** saves ~180 min/mo but
  is precisely the direct-push quality regression the PO ruled out (§5.3). Rejected
  by ruling.
- *Duplication mitigations:* YAML anchors are not viable (GitHub's anchor support
  covers scalar keys — `env`, `defaults`, step sub-fields — not sharing a `steps`
  list across jobs); a custom drift-check script is more machinery than the
  extraction it would guard. The local composite action is the established
  mechanism, adds no third-party `uses:` (supply-chain-neutral), and makes step
  drift between the folded block and the push job **structurally impossible**.

**Honest trade-off (vs the pre-amendment W1 design).** PR failure isolation is
unchanged in effect: today a quality failure already skips test-unit via the
`needs` chain (no unit results either way); what changes is the signal location (a
lint failure now fails the "Unit Tests" job) and one job-rounding per backend
run/night is saved. The real cost is the gitleaks narrowing — registered in §8.

### 5.9 R1 — behavioral PR/push discipline (process ruling, PO-enforced)

R1 is a **process ruling, not YAML**. No CI-side enforcement exists or is possible
(branch protection is unavailable on GitHub Free — §1 Non-Goals); the PO owns
enforcement, CI only makes the effect visible (W1-11 metric).

1. **Batch per PR:** push to PR branches in batches — target **≤1–2 `synchronize`
   events per PR** (agent worktrees make this natural: finish the review-fix batch,
   push once). `cancel-in-progress` already discards superseded runs; the ruling
   reduces run COUNT, never coverage — the final PR state is always fully verified.
2. **No single-trivial-change PRs:** fold trivial follow-ups (typos, comment fixes,
   lint nits) into the OPEN PR they belong to rather than opening a new one.
3. **Docs-only follow-ups fold into the next code PR** where check-gates allow —
   **except** handoffs that must land promptly: `CURRENT_STATE` updates and other
   SSOT-critical doc changes still land as their own (cheap, mostly-gate-skipping)
   docs PR when the handoff discipline requires it. **SSOT discipline wins over
   batching**; the ruling must never delay a handoff past its validity window.
4. **Monitoring (W1-11):** the weekly budget report gains a PR-run count (target
   ~50/mo, corridor 40–60). Sustained drift above ~60/mo is the PO's trigger to
   re-assert the ruling; ~10 extra PR runs ≈ ~100 min/mo and is visible in the same
   report, so erosion of the ruling is measurable, not anecdotal.

Forecast assumption for §9.1: 84 → ~50 PR-triggered runs/mo at unchanged run-type mix.

### 5.10 E2E path-gated on PRs (2nd amendment — PO-adopted 2026-10-16, post-Wave-0)

**Problem (W0-3, cluster A).** The Phase-B E2E wave (PRs #253/#256) landed spec files
that had NEVER executed in any PR context: `test-e2e`'s `if` admits only
`schedule ‖ workflow_dispatch` (ci.yml lines 985–987), so it is skipped on EVERY
`pull_request` run. New E2E specs therefore meet CI for the first time as **nightly
failures on main, post-merge** — exactly cluster A of the W0-3 streak
(`docs/superpowers/notes/2026-10-16-w0-3-nightly-streak-diagnosis.md`). PRs are the
only pre-merge gate this repo has (§2, Ruling 1); E2E is the only test class with no
PR-path entry point.

**Fix (W1-12).** The `changes` job gains an `e2e_specs` filter output; `test-e2e`
gains a PR branch in its `if`, composed onto W1-2's nightly rewire in the §5.4
test-unit pattern (schedule path consults `nightly-gate` outputs; PR path consults
`changes` outputs):

```yaml
if: >-
  github.event_name == 'schedule' || github.event_name == 'workflow_dispatch' ||
  (github.event_name == 'pull_request' &&
   github.event.pull_request.draft != true &&
   needs.changes.outputs.e2e_specs == 'true')
```

The bare `schedule` disjunct is replaced by W1-2's `should_run && (probe ‖ e2e)`
conjunction (same splice discipline as test-unit's combined `if` in W1-4); `changes`
joins test-e2e's `needs` so the output resolves. On schedule runs `e2e_specs` is empty
by construction (the dorny step runs `if: github.event_name != 'schedule'`, ci.yml
line 128) and the PR branch is false anyway. Naming: `e2e_specs` (changes output —
spec-suite files) is deliberately distinct from nightly-gate's derived `e2e`
(backend ‖ frontend): different semantics, different names.

**Filter contents — decision: `tests/e2e/**` ONLY.**

```yaml
e2e_specs:
  - 'tests/e2e/**'
```

- `packages/web/playwright.config.ts` (and `packages/web/tests/**`) are deliberately
  EXCLUDED — verified against the repo: the CI E2E job runs the **pytest** suite
  (`uv run pytest tests/e2e/`, ci.yml line 1113) via pytest-playwright fixtures in
  `tests/e2e/conftest.py` (`E2E_BASE_URL`, default :3000); it never reads the TS
  config. That config drives the Node `@playwright/test` runner of the frontend job
  (VRT + `packages/web/tests/e2e/frontend/*`), already PR-gated via the `frontend`
  filter (`packages/web/**`). Including it would bill a ~9-min full-stack job for
  changes that cannot affect the pytest suite.
- Shared boot infra (`scripts/seed_dev_user.py`, `justfile`, export toolchain) is
  likewise excluded: cross-job inputs already validated by the nightly (≤1d, via the
  `backend`/`frontend` filters) whose PR-time breakage surfaces in the jobs that own
  them (frontend build/boot: the `frontend` job incl. the W1-6 boot smoke). The PR
  path exists to validate the **specs** (the cluster-A gap), not to re-validate the
  app: app-side changes already wake the nightly E2E via `e2e = backend ‖ frontend`
  (§5.1) and hit unit/integration/frontend on the same PR.

**Cost.** `tests/**` is already in the `backend` filter (ci.yml line 140), so an
E2E-spec PR already pays the backend suite on the PR path today — W1-12 adds only
the E2E job itself: ~9 min × ~2–4 E2E-PRs/mo = **+18..36 min/mo** (§9.1 PR row;
conservative vs the 5.65 billed nightly E2E average).

**Draft interplay (W1-5).** The PR branch carries the same
`github.event.pull_request.draft != true` guard as Integration/Frontend. That skip is
safe ONLY because W1-5 adds `ready_for_review` to `on.pull_request.types` — otherwise
a draft E2E PR marked ready would never rerun E2E (no `synchronize` event) and could
merge with its specs never executed. W1-12 therefore lands with-or-after W1-5 (§11).

---

## 6. Wave 2 design — release-please flow slimming (variant b, approved)

**Verified semantics (release-please-action v5 README):** the action exposes exactly the
split inputs this needs — `skip-github-release: true` ("do not attempt to create
releases; useful if splitting release tagging from PR creation") and
`skip-github-pull-request: true` ("do not attempt to create release pull requests;
useful if splitting release tagging from PR creation"). Release creation is decided by
manifest-version-vs-latest-tag, so the two invocations are cleanly disjoint.

**Split:**

1. **Release-PR orchestration → nightly** (new `release-orchestration` job in ci.yml):
   `needs: [nightly-gate]`,
   `if: github.event_name == 'schedule' && needs.nightly-gate.outputs.should_run == 'true'`,
   job-level `permissions: { contents: write, pull-requests: write }`
   (escalation is schedule-only; the job is skipped on every `pull_request` event, so a
   PR run never holds a write token), `timeout-minutes: 10`, runs
   `googleapis/release-please-action@45996ed…` with the existing inputs PLUS
   `skip-github-release: true`. Latency for release-PR creation/update: ≤1 day
   (PO accepted).
2. **Release + publish stays push-triggered and prompt** (release-please.yml): trigger
   becomes
   ```yaml
   on:
     push:
       branches: [main]
       paths:
         - ".release-please-manifest.json"
         - "release-please-config.json"
   ```
   and the `release-please` step adds `skip-github-pull-request: true`. The manifest
   version on main only advances when a release PR merges (human merge → normal push,
   which triggers workflows; the GITHUB_TOKEN no-retrigger restriction applies only to
   token-authored commits, not human merges). At that moment manifest-version > latest
   tag → `release_created: true` → `publish` (Docker/GHCR + SBOM + bundle) runs
   same-day. HARD CONSTRAINT satisfied by construction. Idempotency: a manifest/config
   edit that doesn't advance past the tag produces no release (no-op run ~1.7 min).

**Alternative considered (rejected):** orchestration as a separate workflow on its own
schedule — it cannot reuse the nightly gate's code-day decision, so it would either run
every night (~30 × 1.7 ≈ 51 min/mo, worse) or duplicate the gh-api gate logic (two
sources of truth for "code-day"). Keeping it a job inside ci.yml reuses the gate output
and one concurrency domain.

**Cost math (honest, vs "≤ ~20 min/mo" target):** orchestration ≈ 1.7 min per code-day
(~20/mo ≈ 34 min) + ~2 releases/mo × (1.7 + publish ~10) ≈ 23 min + negligible no-op
runs ≈ **~55–70 min/mo total** (vs 103 measured). The ≤20 target is reachable ONLY with
weekly orchestration (latency ≤7d — rejected) or a conventional-commit pre-gate
(fragile: must mirror release-please's include-list; false negatives silently delay
release PRs). **PO ruling (2026-10-16, OQ2): ~55–70 min/mo with ≤1d orchestration
latency ACCEPTED** — recorded in §14.

**Settings note (PO one-time manual action, NOT a task):** approve the
github-actions[bot]-authored workflow runs / unstick release PR #231 — bot runs on
private repos park at `action_required`. Zero minute cost, but the PR is stale.

---

## 7. Wave 3 design — setup caches (zero quality loss)

All caches use `actions/cache` (restore + explicit gated save, mirroring the existing
Pyright cache pattern, ci.yml lines 340–410 — visible writes, never implicit post-step
side effects). PRs are restore-only; nightly/probe writes keep PR-supplied code from
poisoning shared cache keys (same trust boundary as §5.5 old spec).

| Cache | Jobs | Path | Key | Est. saving |
|---|---|---|---|---|
| Playwright Chromium | frontend, test-e2e | `~/.cache/ms-playwright` | playwright version (from lockfile/package resolution) + runner os | ~1 min/job × ~24 PR + ~12 nightly + ~4.3 probe ≈ **−40/mo** |
| spaCy models | test-integration, test-e2e | model install dir (task must confirm exact path from `just install-nlp-models`; if pip-cache-only is simpler, cache `~/.cache/pip` scoped to the model URLs) | model versions (hash of the model URLs in `justfile`) | ~1 min/job × ~32 PR + ~14 nightly + probe ≈ **−50/mo** |
| Export toolchain (pandoc/typst/EPUBCheck) | test-unit, test-integration, test-e2e | toolchain install dir (task must confirm from `scripts/install_export_toolchain.sh`; if it installs to `/usr/local/bin`, add a cacheable `NARRARE_TOOLCHAIN_DIR` target — ≤3-file change) | `hashFiles('scripts/install_export_toolchain.sh')` + os | ~0.5–1 min/job ≈ **−30/mo** |

Estimated total Wave 3: **−120..−160 min/mo** (already included in §9 forecast).

---

## 8. Quality-loss register (PO's key question — the honest table)

| Measure | What changes in detection latency | Verdict |
|---|---|---|
| Event-driven nightly | Changed components still get full-depth post-merge verification **≤ same day** (the nightly fires that night on any code-day). | No loss for changed code |
| Incremental per-component nightly | Unchanged components skip. Cross-component breakage (A's change manifesting only in B's tests): E2E gates on backend ∨ frontend, so every code night exercises the full stack; residual risk is a frontend-only change breaking a backend-only assertion — previously caught by next-day nightly, now ≤7d (probe) or on the PR path (same depth as today's PRs). | Tiny residual, bounded ≤7d |
| Idle-day probes | Daily implicit probe (nightly-every-day) → weekly explicit probe. World drift / runner-image rotation / flake-on-fresh-runner detection: 1d → ≤7d. | Accepted (probe preserves it, bounded) |
| Push quality path-filter | Docs/state-only pushes lose same-push quality — but they cannot change any quality-tool input (filter covers all inputs). | No loss |
| R3 quality fold (§5.8; absorbs R5) | PR-time gitleaks narrows to backend-gated runs: a secret introduced in a frontend/docs/workflows-only PR is caught ≤7d (probe) or on the next backend run instead of same-PR. Push path unchanged (full-history gitleaks on every code push). Failure isolation unchanged (a quality failure already skipped unit via `needs`); non-backend nights skip the Python tools, whose inputs they did not change. | Accepted (PO, R3+R5 adoption); residual bounded ≤7d |
| test-unit PR gating (backend) | Docs/ADR-only and frontend-only PRs skip unit — cannot affect unit outcomes; the docs-sensitive checks live in the un-gated architecture job. Since R3, the same gate also skips the folded quality tools (gitleaks residual → row above). | No loss for tools; residual in R3 row |
| R1 PR discipline (§5.9) | No detection change — removes redundant intermediate runs only; the final PR state is always fully verified. Process, PO-enforced (no CI enforcement possible on GitHub Free). | No loss |
| `ready_for_review` types | Pure gain: closes the draft-never-reruns hole (no branch protection exists to catch it). Cost +1 run/transition noted in §5.5. | Gain |
| E2E on PRs (§5.10, W1-12) | New E2E specs gain **PR-time validation** — previously their first CI contact was the post-merge nightly on main (W0-3 cluster A; PRs #253/#256). Draft PRs skip until marked ready — safe only because W1-5 reruns on `ready_for_review`. | Gain (deliberate purchase at +18..36 min/mo — §9.1) |
| Standalone fold | Same checks, same job; now also runs on frontend-active nights (previously PR-only). | No loss (slight gain) |
| Budget-report weekly | Quota-overrun warning latency 1d → 7d; headroom ≈ 2× quota in corridor. | Accepted |
| Release-PR latency | Orchestration ≤1 day (was: every push ≈ immediate). Release/publish on merge: unchanged (same-day, by construction §6). | Accepted (PO) |
| Nightly zizmor cadence | Runs code-nights + probe instead of every night; workflow-security drift on idle days: ≤7d. PR-side blocking behavior unchanged. | Accepted |
| Mutation monthly / Eval nightly / Dependabot | Unchanged. | — |

---

## 9. Forecast

### 9.1 Bottom-up (steady state, all waves + R1+R3+R5 landed, churn-free)

| Block | Measured (30d) | After redesign (amended scope) | Delta | Assumptions (auditable) |
|---|---|---|---|---|
| pull_request | 984 | **~450–525** (central ~475–490) | −~505 | R1: 84 → ~50 runs/mo at unchanged run-type mix (sealed post-W1 block ~850 × 50/84 ≈ 505; fewer synchronize events also shrink cancellation overhead — the measured quality ×31/84 start-frequency is largely cancellation skew). R3 fold: −~0.75/backend-run (setup + one job-rounding only; tools unchanged; `--extra embeddings` sync delta ~0.1–0.3 via uv cache) × ~19 backend runs. R5-absorbed: non-backend runs skip the folded tools, −~35 central (partial claw-back only — many of these runs never started quality anyway). Wave-3 caches −~55 at 50-run volume. 2nd amendment: **E2E-on-PR +18..36 (§5.10)** — ~2–4 E2E-PRs/mo × ~9 min; marginal only (E2E-spec PRs already ride the backend path via `tests/**` in the `backend` filter). |
| push | 438 | **~350** | −~88 | unchanged by R3 (push quality job retained verbatim, §5.8): ~45 code × 7 min + ~15 docs × 3 min; quality path-filter; Wave-0 removes the 24-run red cluster + fix-rerun churn (counted in W0 row). No push-volume credit taken for R1's docs-fold guidance (conservative). |
| schedule | 482 (13 runs) / 1,110 (30-day proj.) | **~590–670** (central ~620) | −~490 vs projection | sealed ~615–690 minus R3: quality leaves the fixed nightly set (−3.7 × ~20 code-nights), tools re-enter inside unit on backend nights (+~2.8 × ~14) and probe nights (+~12/mo); net ≈ −25. Non-backend nights lose the Python tools entirely (R5-absorbed; inputs unchanged). |
| Release Please | 103 | **~55–70** (central ~62) | −~45 | §6 math: ~20 code-days × 1.7 + ~2 releases × ~12; OQ2 ruling 2026-10-16: ACCEPTED at ≤1d latency |
| Mutation | 2 | 2 | 0 | unchanged |
| **Total** | **~2,078** (2,600 proj.) | **~1,445–1,620 central ~1,520–1,540** (−~1,070 vs projection) | | row-sum range; central = pre-amendment ~1,500 + 18..36 E2E-on-PR (§5.10; band width = 2–4 E2E-PR volume uncertainty); corridor widened to **~1,430–1,680** for the dominant R1 uncertainty (±10 PR runs ≈ ±100 min/mo) |
| Wave 0 (embedded churn in the measured baseline: ~5 failed nightlies ≈ ~150 wasted min — jobs ran partway; the 24 red push runs billed **0 min**, jobs never started — W0-1) | | | **~−150** additionally vs the churny baseline (corrected 2026-10-16 post-W0-1; was −300..−400) | W0-1 evidence: `docs/superpowers/notes/2026-10-16-w0-1-push-failure-diagnosis.md`; not double-counted in the rows above (rows are churn-free) |

**Honest target statement (amended 2026-10-16; 2nd amendment same day):** with
R1+R3+R5 landed **and the E2E-on-PR quality purchase made (§5.10)**, the steady
state is **~1,445–1,620 min/mo (central ~1,520–1,540 = pre-amendment ~1,500 +
18..36)** — matching the PO's amended target and ~76–77% of the 2,000-min quota (the
weekly budget report warns at 80%). The original 950–1,150 corridor is **retired as
unreachable at current volumes** under the PO's standing rulings (no runner changes,
no public repo, no Pro). Below ~1,520–1,540 the only remaining in-spec lever is R4
(drop Sunday probe, −~168, single-line revert → ~1,350–1,370); after that, only
volume or runner changes — both ruled out. Dominant uncertainty: R1 is behavioral
(±10 PR runs ≈ ±100 min/mo), E2E-PR volume second (±2 runs ≈ ±18 min/mo); the W1-11
PR-run metric makes R1's erosion visible weekly, not monthly.

### 9.2 Lever disposition (amended 2026-10-16: R1+R3+R5 sealed into scope — OQ1 resolved)

| # | Lever | Status | Est. saving (amended basis) | Quality cost |
|---|---|---|---|---|
| R1 | PR batching discipline (§5.9; 84 → ~50 PR runs/mo) | **ADOPTED** — process, PO-enforced; W1-11 metric | −~350 (PR block ~850 → ~505 at 50 runs) | none (final PR state always verified) |
| R3 | Merge quality into test-unit on PR/nightly paths; push-only quality job stays (§5.8) | **ADOPTED** | −~75 total (PR fold −~15; PR R5-absorbed skip of non-backend runs −~35; nightly net −~25: −~74 fixed-set removal + ~39 backend-night re-entry + ~12 probe) | gitleaks narrowing → §8 |
| R5 | Path-gate `quality` on PRs (backend ∨ frontend) | **ABSORBED into R3** — the fold's backend gate subsumes it and also skips frontend-only runs, which R5-as-stated would have kept | (inside R3) | (inside R3) |
| R4 | Drop Sunday probe | **Remaining reserve lever** — pre-agreed next cut if W1-10 measurement lands high (§5.1.4; single-line revert) | −~168 | world-drift ≤7d → next-code-night |
| R2 | Path-gate `architecture` on PRs (docs-only PRs skip) | Available, **NOT adopted** — value shrank under R1 (docs-PR volume down) | −~10 (was −~20 at 84 runs) | docs-drift checks lose PR-time run → nightly only |
| — | **E2E path-gated on PRs** (§5.10; 2nd amendment, post-W0-3) | **ADOPTED** — quality purchase, not a saving lever | **+18..36 (cost)** | Gain: E2E specs get PR-time validation (§8) |

The pre-amendment arithmetic (sealed ~1,920 − ~400 ≈ 1,500) and the amended bottom-up
(§9.1, central ~1,500: −~345 R1 − ~75 R3/R5) agree; the 2nd amendment adds the
E2E-on-PR cost (+18..36 → central ~1,520–1,540). The §9.1 per-row assumptions are
the auditable basis.
Below ~1,520–1,540 the next honest step is R4; after that only volume or runner
changes, which the PO's standing rulings exclude. No further levers are identified
in this spec.

---

## 10. Task breakdown (slicing; each task ≤3 files / ≤250 LOC, independently revertible)

Ownership: Wave 0 → Platform layer (log-based diagnosis via `gh api`; fixes may route to
the owning layer once diagnosed). Waves 1–3 → Platform layer (CI YAML). All tasks:
actionlint + `zizmor --config .github/zizmor.yml .github/workflows/` locally BEFORE
commit; `uv run python scripts/check_gate_drift.py` green; targeted `gh` observation
post-merge as specified per task.

**Wave 0 — stop the red-run burn (first; quality gain)**

> Execution note (2026-10-16): W0-1 and W0-3 diagnoses dispatched; evidence notes
> will land at `docs/superpowers/notes/2026-10-16-w0-1-*.md` and
> `docs/superpowers/notes/2026-10-16-w0-3-*.md`. W0-2/W0-4 are scoped off those
> findings.

- **W0-1 Diagnose push-run failure cluster (24× at changes/architecture).** Pull the 24
  failed runs' logs (`gh api` / `gh run view --log-failed`), cluster by error signature,
  identify root cause(s) with ≥2× why. Deliverable: evidence summary (issue comment or
  `docs/superpowers/notes/`). Files: 0 (docs only). Gate: root cause named with log
  evidence + reproducer or explicit non-repro rationale.
  **Status: DONE 2026-10-16 — root cause: GitHub account billing blocks, not a repo
  defect (see Wave 0 outcome).**
- **W0-2 Root-cause fix + regression test, push cluster.** Scoped by W0-1; sized when
  diagnosed (≤3 files / ≤250 LOC; if bigger, split before implementing). Gate: the 24-run
  signature covered by a regression test; 5 consecutive green push runs observed.
  **Status: CLOSED — no repo-side fix exists; converts to a PO one-time action (see
  Wave 0 outcome).**
  **3rd-amendment addendum (2026-10-18):** W0 round 2
  (`docs/superpowers/notes/2026-10-18-w0-round2-nightly-diagnosis.md`) diagnosed the
  post-#258 fail-start cluster (push, nightly, and PR runs alike) as the **SAME billing
  root cause — third occurrence** (2026-10-01 zero-actions wave · W0-1's 24-run push
  cluster · round 2). The note's optional repo-side "billing-annotation streak guard"
  is **REJECTED**: a guard running inside CI cannot observe an outage whose defining
  property is that CI never starts (fail-before-step-0), and §15's re-entry rule
  (streak observation restarts at billing return; first post-billing nightly =
  designed full re-baseline) already delivers the protection with zero LOC.
- **W0-3 Diagnose nightly Frontend+E2E failure streak (5/7 since PR #256 E2E specs).**
  Same method; explicitly test the #256-correlation hypothesis (spec-vs-implementation
  drift vs environment). Files: 0. Gate: root cause named with log evidence.
  **Status: DONE 2026-10-16 (see Wave 0 outcome).**
- **W0-4 Root-cause fix + regression tests, nightly streak.** Scoped by W0-3. Gate:
  3 consecutive green full nightlies (or probe runs) observed post-merge **(timing,
  3rd amendment: the streak clock is SUSPENDED while billing is dead — the two
  post-#258 nightlies fail-started with 0 jobs run and are not streak evidence; the
  count starts at billing return, §15)**.
  **Status: EXECUTED — landed as PR #258 (squash `10d9bec6`, merged 2026-10-17T07:00Z);
  formal gate deferred-to-resume (see Wave 0 outcome + §15).**

> **Wave 0 outcome (2026-10-16, recorded with the 2nd amendment; W0-3/4 landing
> updated by the 3rd — §15):**
>
> - **W0-1/W0-2 — resolved; NOT a code defect.** 24/25 failed push runs were GitHub
>   account billing blocks ("spending limit reached / payments failed") — jobs never
>   started, **0 billed minutes**; the cluster self-healed. W0-2 therefore closes with
>   **no repo-side implementation**; the residual is a PO one-time manual action
>   (GitHub billing settings: valid payment method + spending limit). The 25th run:
>   msw v2→v3 dependabot major bump merged DIRECTLY to main (tsc break, fixed 32 min
>   later) — recorded as process evidence supporting R1 (§5.9); no CI-side enforcement
>   possible (§1). Forecast consequence: §9.1's Wave-0 credit corrected to ~−150 (the
>   push cluster billed 0 min; the real churn was the nightly streak). Evidence:
>   `docs/superpowers/notes/2026-10-16-w0-1-push-failure-diagnosis.md`.
> - **W0-3/W0-4 — diagnosed and executed; landed as PR #258** (squash `10d9bec6`,
>   merged 2026-10-17T07:00Z; every post-merge run since then fail-starts on the
>   billing outage — W0 round 2 note — so the fixes have zero executed-CI evidence
>   yet; formal 3-green-nightly gate suspended until billing returns, §15).
>   **W0-4a**: python pin `python-version: "3.14"` on 7 `setup-uv` sites
>   (ci/release-please/mutation) + `.github/zizmor.yml` ignore-baseline re-triage;
>   `eval-nightly.yml` deliberately NOT pinned (`disabled_manually` — pin on
>   re-enable). **W0-4b**: hydration-safe waits (foundation/helpers/test_ai_writing +
>   conftest follow-up; live-verified 7/7 and 5/5). **W0-4c**: KBEnhanceReview
>   vacuous-waitFor race fix. Formal gate stays **3 consecutive green nightlies
>   post-merge**: the E2E fixes validate on main's nightly because PR runs do not
>   execute E2E until W1-12 (§5.10) lands — the very gap §5.10 closes. Evidence:
>   `docs/superpowers/notes/2026-10-16-w0-3-nightly-streak-diagnosis.md`.
> - **W0-4d** (writing_activity_events FK noise, non-fatal) — deferred to the normal
>   backlog; out of this spec's scope.

**Wave 1 — ci.yml restructuring (order matters: W1-1 adds the gate without behavior
change; W1-3 extracts the shared quality steps; W1-4 lands the R3 fold atomically;
each task is an independent revert)**

- **W1-1 Add `nightly-gate` job** (§5.1 steps 1–5: gh api last-green SHA, fetch-depth 0
  checkout, dorny `base:`, outputs `should_run/backend/frontend/workflows/e2e/probe`,
  `actions: read` job perms, retry/backoff, fail-open rules, dispatch=full).
  No consumer yet (outputs unused) → zero behavior change. Files: `ci.yml`. ~120 LOC.
  Gate: one nightly fires; idle-night and code-night outputs verified via run logs.
- **W1-2 Rewire job conditions to gate outputs** (§5.1 table, incl. the
  update-coverage-badge `result == 'success'` fix and warnings-summary needs update;
  the quality row is handled by W1-4, not here). Files: `ci.yml`. ~120 LOC. Gate:
  dispatch run = full matrix; simulated idle night = all expensive jobs skipped;
  component night = only changed components ran.
- **W1-3 Extract `.github/actions/quality` composite action** (§5.8: tool steps
  ruff → pip-audit + Pyright cache restore/save moved VERBATIM out of the `quality`
  job; the job calls the action — behavior-identical refactor, no condition changes
  yet; per-job checkout/setup/sync stay outside). Files:
  `.github/actions/quality/action.yml`, `ci.yml`. ~130 LOC (mostly moved).
  Gate: PR run green with the identical tool-step sequence; actionlint + zizmor
  clean.
- **W1-4 R3 fold + push-only quality + unit PR gate — ONE atomic commit** (§5.8,
  §5.3, §5.4): test-unit gains the composite call before pytest, sync gains
  `--extra embeddings`, `needs: [architecture, changes]`, and the combined `if`
  (nightly-gate ‖ dispatch ‖ PR-backend); `quality` job `if` → push-only AND
  code-gated (the sealed §5.3 `code` filter lands here); `test-integration` and
  `test-e2e` `needs: [quality, …]` → `[architecture, …]`; `changes.backend` +=
  `.gitleaks.toml`. Atomicity is the point: fold and narrowing land together, so
  there is never an interval where PRs or nightlies lack the tools. Files: `ci.yml`.
  ~90 LOC. Gate: backend PR runs tools+unit in ONE job; frontend-only PR skips both;
  docs-only push → 3 jobs; code push → push quality job with full tool set;
  dispatch = full matrix incl. tools; integration/e2e observed running (needs
  rewires verified).
- **W1-5 PR `types: [opened, synchronize, reopened, ready_for_review]`** (§5.5).
  Files: `ci.yml`. ~5 LOC. Gate: draft→ready transition on a test PR reruns
  Integration/Frontend.
- **W1-6 Fold frontend-standalone into frontend** (§5.6: move 4 steps post-Build,
  delete job). Files: `ci.yml`. ~80 LOC. Gate: frontend PR shows boot-smoke step green;
  job list has no standalone.
- **W1-7 Budget-report weekly cron** (§5.7: second schedule entry, schedule-string
  discriminators, gate `if` guard). Files: `ci.yml`. ~20 LOC. Gate: Sunday 03:07 run
  shows only gate-skip + budget-report.
- **W1-8 Sync gate-audit comment block in ci.yml** (lines 3–45): standalone row →
  "frontend Job (post-Build step)", budget-report cadence, nightly composition,
  ready_for_review note, E2E-on-PR row (§5.10 — `e2e_specs` PR path), **quality split
  row** (tools inside test-unit on PR/nightly; push-only quality job via
  `.github/actions/quality`); header SSOT reference fixed
  (see W1-9). Files: `ci.yml`. ~40 LOC. Gate: `check_gate_drift` green; audit table
  matches reality.
- **W1-9 Repair drift-check SSOT (STALE — flagged).** `.opencode/context/narrare-dev/
  processes/quality-gates.md` **does not exist anywhere in the repo** (verified), yet is
  the SSOT read by `scripts/gate_drift_checks.py` (`QUALITY_GATES_PATH`, which silently
  degrades to `""` — the mypy drift check passes vacuously) and referenced at ci.yml
  line 6 + docstrings in `check_gate_drift.py` (l.17) and `gate_drift_checks.py` (l.7).
  Fix: create `docs/development/quality-gates.md` as the committed SSOT (seed from the
  ci.yml audit table, plus the R1 process ruling §5.9 and the R3 job split §5.8 —
  the SSOT is where PO-enforced process lives), repoint `QUALITY_GATES_PATH`. Slice:
  **W1-9a** new SSOT file + `scripts/gate_drift_checks.py` (path + docstring, and make
  missing-file LOUD — fail the check instead of vacuous pass); **W1-9b** ci.yml header
  comment + docstring references in `check_gate_drift.py`. 2–3 files each. Gate:
  check_gate_drift green AND fails loudly with the file temporarily removed.
- **W1-10 Post-merge observation, 30 days of billable CI activity** (checklist doc
  only): nightly idle/code/probe behavior ×1 week, budget-report trend weekly (incl.
  the W1-11 PR-run count vs the ~50 target), one backend PR observed end-to-end
  through the folded tools+unit job, no red-run recurrence; feeds any R4 decision
  (§9.2). Files: notes. **Timing (3rd amendment, §15.2): "30 days post-merge" is
  re-based to 30 days of billable CI activity post-billing-return (November) — the
  first full nightly after return is the re-baseline, and the billing-dead period
  (0-minute fail-starts) contributes no observations.**
  Gate: 30-day budget-report total recorded.
- **W1-11 Budget-report PR-run count** (§5.9 monitoring: tally `event ==
  "pull_request"` runs in the existing inline script; append the count + ~50 target
  to the summary line; no change to the minute math). Files: `ci.yml`. ~15 LOC.
  Gate: next weekly report shows the PR-run count.
- **W1-12 E2E on PRs — `e2e_specs` filter + test-e2e PR branch** (§5.10): `changes`
  job gains the `e2e_specs` output (`tests/e2e/**` ONLY — decision + verified
  rationale in §5.10); `test-e2e`'s `if` gains the PR branch
  (`draft != true && needs.changes.outputs.e2e_specs == 'true'`) composed onto the
  W1-2 schedule branch (§5.4 pattern); `changes` added to test-e2e's `needs`. Lands
  with-or-after W1-5 (draft-skip safety, §5.10). Files: `ci.yml`. ~15 LOC. Gate: PR
  touching only `tests/e2e/**` runs test-e2e; the same PR as draft does not, and
  marking it ready reruns it (W1-5 interplay observed once); a backend-only PR does
  NOT run E2E on the PR path (nightly still covers it); actionlint + zizmor clean.

**Wave 2 — release-please split (order: add nightly orchestration FIRST (double
coverage), then narrow the push trigger — no release-PR gap at any point)**

- **W2-1 Add `release-orchestration` job to ci.yml** (§6.1: schedule + code-day gated,
  `skip-github-release: true`, job perms contents:write + pull-requests: write,
  timeout 10). Files: `ci.yml`. ~40 LOC. Gate: next code-night creates/updates the
  release PR; release-please.yml still per-push meanwhile (double coverage, ~1 mo of
  +1.7/code-day accepted temporarily).
- **W2-2 Narrow release-please.yml** (§6.2: push `paths:` manifest+config,
  `skip-github-pull-request: true`). Files: `release-please.yml`. ~15 LOC. Gate: code
  push to main does NOT trigger Release Please; next release-PR merge triggers
  release+publish same-day (observed end-to-end once).
- **W2-3 Document the split + verify semantics** in the workflow header comments (v5
  input semantics, the human-merge-triggers-workflows argument, the PO settings note
  re PR #231 approval). Files: `release-please.yml`, `ci.yml` (comments only).

**Wave 3 — caches (each independent; restore + gated explicit save, §7)**

- **W3-1 Playwright Chromium cache** (frontend + test-e2e). Files: `ci.yml`. ~50 LOC.
  Gate: cache hit observed; job time −≥40s on second run.
- **W3-2 spaCy model cache** (test-integration + test-e2e; confirm install path from
  justfile first — if a stable cache dir needs a justfile tweak, keep ≤3 files).
  Files: `ci.yml` (+ `justfile` at most). ~40 LOC. Gate: cache hit; step time drop.
- **W3-3 Export-toolchain cache** (test-unit + test-integration + test-e2e; keyed on
  `hashFiles('scripts/install_export_toolchain.sh')`; if the script installs to
  /usr/local/bin, add a cacheable target dir — `ci.yml` + script ≤3 files). Gate:
  cache hit; download step skipped on match.
- **W3-4 Record measured savings** (compare pre/post job times for the six affected
  jobs; append to W1-10 notes). Docs only. **Timing (3rd amendment, §15.2): "pre" =
  last pre-outage job times; "post" is measured inside W1-10's post-billing-return
  window — cache-hit effects are invisible while billing is dead.**

Task counts: **W0: 4 (W0-2 closed without code) · W1: 13 (incl. W1-9a/9b as one
numbered pair) · W2: 3 · W3: 4 — 24 tasks.**

---

## 11. Migration order & rollback safety

Order: **W0 → W1-1 → W1-2 → W1-3 → W1-4 → (W1-5 ‖ W1-6 ‖ W1-7 ‖ W1-11 ‖ W1-12) → W1-8 →
W1-9a → W1-9b → W2-1 → W2-2 → W2-3 → (W3-1 ‖ W3-2 ‖ W3-3) → W1-10/W3-4.**
(W1-3 → W1-4 strictly sequential: the composite must exist before the fold references
it; W1-4 needs W1-2's gate outputs for its combined `if`; W1-12 lands with-or-after
W1-5 — the E2E draft-skip is only safe once `ready_for_review` reruns exist, §5.10.)

Rollback: every task is a single logical commit (or a/b pair) — `git revert` restores
the prior behavior without cross-task coupling. Notable safety properties:

- W1-1 is additive (unused outputs) — reverting W1-2 alone restores today's nightly
  while the gate keeps measuring.
- W1-12 is independently revertible: dropping the PR branch + `e2e_specs` filter
  returns E2E to nightly+dispatch only; nightly coverage never depended on the PR
  path.
- W1-3 is a behavior-identical extraction — reverting it re-inlines the steps; there
  is no window without quality anywhere. W1-4 is one atomic commit (fold + push-only
  narrowing + needs rewires): no interval exists in which PRs or nightlies lack the
  quality tools, and reverting it restores the separate quality job on all events
  (W1-3's composite then simply goes unused by test-unit; the push job may keep it).
- W2 ordering guarantees no interval without release-PR orchestration (double coverage
  between W2-1 and W2-2, and prompt-publish behavior never changes).
- Gate fail-open rules mean any `nightly-gate` bug degrades to a FULL nightly (too
  many minutes for one night), never to a skipped one (missed verification). Only an
  explicit, correct `should_run: false` skips work.
- Worst-case rollback of the whole wave set = revert to current ci.yml; measured
  baseline 2,078/2,600 immediately reapplies; no data or infra migration involved.

---

## 12. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| `gh api` rate limits / 5xx in nightly-gate | gate fails → wrong skip/run decision | 2 calls/night is negligible quota; retry+backoff (budget-report pattern); on unresolved API failure → **fail-open** (run full nightly) |
| dorny `base` edge cases: force-push/rebase makes last-green SHA a non-ancestor or unreachable | wrong delta (empty or partial) | Verified dorny semantics: no common ancestor → all files added → full nightly (fail-open). Documented; no code needed. Nightly concurrency group keeps schedule runs uncancellable. |
| Path-filter false negatives on workflow-file changes | ci.yml change only exercises part of matrix | `workflows` filter wakes nightly AND forces frontend + zizmor + (via `e2e` derivation consideration) full-stack E2E; probe re-exercises everything weekly; PR-side `workflows == 'true'` conditions already self-exercise |
| Nightly fails repeatedly (post-W0 regression) | base never advances → nightly accumulates to full runs (cost creep) | This is deliberate self-healing; budget-report weekly surfaces the creep; Wave 0 removes the known streak |
| update-coverage-badge downloads missing artifact on unit-skip nights | red nightly | Fixed in W1-2 (`needs.test-unit.result == 'success'`); gated to unit-nights |
| zizmor unsound-ternary regression in new conditionals | CI red | Ternary rule pinned in §4 invariants; zizmor runs locally per task gate |
| release-orchestration job-level write perms in a PR-triggered workflow | token exposure surface | Job `if` restricts to schedule+code-day; skipped jobs get no token; zizmor audit per task; if zizmor still flags, document inline with justification, never widen workflow-level perms |
| Release-PR latency ≤1d missed if nightly fails | release PR stale ≤ failure duration | acceptable (release PR is not urgent); dispatch path (full matrix) + next green night recovers |
| Draft→ready cost higher than estimated | +minutes, no quality change | bounded by draft-transition count; visible in budget report; types list is independently revertible |
| Corridor not reached by sealed levers (§9.1) — amended: forecast lands above ~1,650 | quota pressure; PO expectation mismatch | R1 erosion is the dominant term (±10 PR runs ≈ ±100 min/mo) and is visible WEEKLY via W1-11; R4 probe drop (−~168, single-line revert) is the pre-agreed next cut (§9.2); bottom-up basis auditable per row (§9.1) |
| Missed `needs` rewires in W1-4 (test-integration/test-e2e keep `needs: [quality]`) | jobs silently skipped on every PR/nightly once quality is push-only | Edge list enumerated in §5.8; W1-4 gate requires a dispatch full-matrix run AND one backend-PR observation showing integration/e2e running |
| Composite-action drift (folded block vs push quality job) | tool parity erodes between paths | Structurally impossible: both call sites use the same local action (§5.8); W1-3 moves steps verbatim and is reviewed as a move, not a rewrite |
| R1 discipline erodes (creep back toward 84 PR runs/mo) | +~350 min/mo, silently | No CI enforcement possible (no branch protection); PO-enforced ruling (§5.9) + weekly PR-run-count metric (W1-11) makes drift measurable |
| No branch protection (GitHub Free) | nothing enforces PR gating at merge time | Pre-existing condition, unchanged by this spec; the ready_for_review fix (W1-5) removes the worst current hole |
| E2E-on-PR cost exceeds +18..36 (more E2E PRs, or ~9 min/run under-estimated; §5.10) | PR-block minute creep | Bounded and visible: E2E-PR count rides the weekly budget report (W1-11 run count); the PR branch + `e2e_specs` filter are a single-line revert to nightly-only E2E; PR-runner flake risk already reduced by the W0-4b/4c race fixes |

---

## 13. Docs to sync (check_gate_drift must stay green)

- `.github/workflows/ci.yml` lines 3–45 **gate-audit comment block** — the effective
  SSOT rendered in-repo; W1-8 updates it (standalone row, budget cadence, nightly
  composition, PR types, E2E PR path, quality split).
- `.github/actions/quality/action.yml` — **new file (W1-3, §5.8)**: single source of
  the quality tool steps for the folded test-unit block and the push-only quality
  job; referenced by the ci.yml audit table (W1-8) and the quality-gates SSOT (W1-9a).
- `scripts/gate_drift_checks.py` — reads ci.yml (coverage regex, streaming-compliance
  and locale-sync blocking checks — none of those steps move; verify per task),
  `pyproject.toml`, `scripts/gate-exceptions.json` (register any new accepted drift
  there), and `QUALITY_GATES_PATH` (stale — W1-9).
- `.opencode/context/narrare-dev/processes/quality-gates.md` — **STALE, flagged**: file
  absent; referenced at ci.yml l.6, `check_gate_drift.py` l.17, `gate_drift_checks.py`
  l.7/l.23–25. W1-9 relocates the SSOT to `docs/development/quality-gates.md` (which
  then also records the R1 process ruling §5.9 and the R3 job split §5.8) and makes
  a missing SSOT a loud failure instead of a vacuous pass.
- `docs/superpowers/specs/2026-09-29-ci-minutes-hardening-design.md` — add a
  supersession pointer note at its header (one-line doc edit, bundled with W1-8).
- Release-please split documentation lives in workflow headers (W2-3).

---

## 14. Open questions — both RESOLVED (2026-10-16)

1. **Corridor reconciliation — RESOLVED (PO ruling 2026-10-16, OQ1):** R1+R3+R5 are
   pulled INTO the sealed scope (R5 absorbed into R3 — §5.8; R1 codified as a process
   ruling — §5.9). Target re-based to **central ~1,500 min/mo (corridor ~1,400–1,650)**;
   the amended bottom-up confirms it (§9.1: ~1,420–1,600, central ~1,500).
   *(2nd amendment, same day: E2E-on-PR +18..36 re-bases the target to central
   ~1,520–1,540, corridor ~1,430–1,680 — §5.10, §9.1.)* The original
   950–1,150 corridor is retired as unreachable at current volumes under the standing
   rulings. R4 (drop Sunday probe, −~168) is pre-agreed as the remaining reserve lever
   if the 30-day W1-10 measurement lands high.
2. **Release-please ≤20 min/mo target — RESOLVED (PO ruling 2026-10-16, OQ2):**
   **~55–70 min/mo with ≤1d orchestration latency ACCEPTED** (§6 math unchanged;
   weekly-latency and conventional-commit-pre-gate variants rejected).

No open questions remain.

---

## 15. November billing mode (3rd amendment — 2026-10-18, PO directive)

**Context (binding, PO 2026-10-18).** GitHub Actions billing is dead until
**November 2026** — the third outage. Since 2026-10-17T07:00Z every job in every
workflow (push, nightly, PR) fail-starts with the account spending-limit annotation:
0 steps executed, 0 minutes billed (W0 round 2:
`docs/superpowers/notes/2026-10-18-w0-round2-nightly-diagnosis.md`; occurrence
history: 2026-10-01 zero-actions wave · W0-1's 2026-10-16 push cluster · this one).
Repo precedent: the 2026-10-01 wave substituted the full LOCAL gate for CI and used
`[skip ci]` pushes. PO directive: *"Es muss so weitergehen"* — the program continues
in **local-verification mode**. This section converts only the merge/observation
criteria; the Waves 1–3 design, forecasts, and all other rulings are unchanged.

### 15.1 Merge criterion for PR #259 converts to local-gate + review

PR #259 is the in-flight Wave-1 PR (branch head `8de4d5bf` at W0-round-2 diagnosis).
While GitHub-side PR checks are unavailable they **do not gate**. Merge criterion:

1. **Full local CI-matrix-equivalent gate GREEN on the branch tip** — exact matrix
   (one row per CI surface; commands are the standing local recipes):

   | CI surface | Local equivalent (exact) |
   |---|---|
   | architecture + gate scripts | `just check-architecture` (check_architecture `--prompt-integrity`, exception-baseline, prompt-surface-contract, empty-kb-vars, frontmatter-schema, test-coverage-gaps `--fail-on-missing`, frontend-file-size) **+** `uv run python scripts/check_gate_drift.py` |
   | quality: ruff/format | `just lint-check` (ruff check + ruff format `--check`) |
   | quality: pyright ×2 | `just typecheck` (strict, root config) **+** `just typecheck-tests` (basic, `tests/pyrightconfig.json`) |
   | test-unit | unit suite with coverage threshold parity: `--cov-fail-under=80` (as ci.yml) |
   | test-integration | `just test-integration` — **including** the schema-mutating (`-m schema_mutating`) and golden (`-m golden_pages`) markers |
   | frontend (full) | `just test-frontend` (Vitest incl. the VRT-contract preflight) + `just vrt` + production `build` + standalone boot smoke |
   | test-e2e | `just e2e` — CI-faithful live stack (services up, `ENVIRONMENT=test`, timeout 300) |
   | zizmor / actionlint | `zizmor --config .github/zizmor.yml .github/workflows/` + `actionlint` (already the per-task §10 discipline) |

   The wider standing local gate (`just verify`, `just security`) remains available
   practice but is NOT part of the sealed criterion — the table above is.

2. **Independent review APPROVED** — already held; not re-run.
3. **Squash-merge with `[skip ci]` in the merge-commit subject** — suppresses the
   otherwise-guaranteed fail-start push run on the merge commit (2026-10-01
   precedent: `[skip ci]` honored, run-list-verified).

### 15.2 Deferred-then-resumed formal gates — November re-entry is a designed re-baseline

The two observation-based formal gates **start when billing returns (November)**, not
at merge: W0-4's "3 consecutive green nightlies" and the W1-10/W3-4 30-day
measurement (task descriptions updated in §10). This is not an accident of timing —
the nightly-gate design is **self-healing through the outage**:

- Billing-failed nightlies never run jobs, so the "last *successful* schedule run"
  query (§5.1 step 1) keeps returning the **old green SHA** from before the outage
  for the entire dead period.
- The first post-billing nightly therefore compares the then-current HEAD against
  that old base → the accumulated delta spans the whole outage (or the base is
  unreachable → fail-open) → **FULL nightly, automatically.**

State it explicitly: **the first post-billing nightly is a designed full
re-baseline of main**, by construction of §5.1 — no manual `workflow_dispatch`, no
streak bookkeeping, no special case. (Until PR #259 merges, the pre-W1 nightly is
unconditionally full anyway — the property holds on both sides of the merge.) The
3-green streak and the 30-day measurement both count from that re-baseline;
W0-round-2's recommendation of one recovery `workflow_dispatch` remains available as
an optional pre-check but is not required by this spec.

### 15.3 Schedule noise — cosmetic red, no action

While billing is dead, the nightly cron (02:37; and the Sunday budget cron once
W1-7 merges) fires and fail-starts at 0 minutes billed — **cosmetic red only**.
Ruling: **do NOT disable the schedules.** Disabling and re-enabling would only
create a November re-entry task that someone can forget; leaving them running costs
exactly nothing (0 billed minutes) and preserves cadence discipline — the moment
billing returns, the schedules resume observing without any repo action.
