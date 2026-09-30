# CI Minutes Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut GitHub Actions quota usage (~2850 → ~1900 min/month) and close the workflow supply-chain gaps, per spec `docs/superpowers/specs/2026-09-29-ci-minutes-hardening-design.md`.

**Architecture:** Single-workflow re-gating (PR = full gate, push = smoke, nightly = full), mechanical hardening (SHA pinning, zizmor, timeouts, token hygiene), plus a nightly quota guardrail. No source-code changes outside `.github/`.

**Tech Stack:** GitHub Actions YAML, zizmor (PyPI), GitHub REST API, Python 3 stdlib (urllib for the budget report).

## Global Constraints

- Repo language is **English** — all comments/messages in changed files must be English.
- **NEVER** `git commit --no-verify` / `-n`. If pre-commit hooks fail, fix the root cause or report `BLOCKED`.
- Conventional commits, one per task, prefix `ci(workflows):` (or `chore(ci):` for pure config adds).
- Every task's verification MUST include: `uv run --no-sync python scripts/check_gate_drift.py` (docs↔CI sync) and YAML validation via the commit hooks (`check yaml` runs on staged workflow files).
- Do NOT "fix" pre-existing doc-drift warnings (ADR-087 INDEX, I-Copy-001 refs) — out of scope.
- Fresh worktree? Bootstrap first: `uv sync --frozen --all-packages --group dev && pnpm install --frozen-lockfile` (hooks need `narrare_core` + `tsc`).
- Nightly cron: `30 2 * * *` UTC. Schedule/workflow_dispatch full runs use the default-branch workflow file.
- Branch: work on `kinetic-falcon` (current worktree branch). Do not push; the coordinator handles handoff.
- Action refs stay TAG-pinned until Task 4 pins them to SHAs — do not mix pinning into Tasks 1–3.

---

### Task 1: Trigger model — PR gate, push smoke, nightly full

**Files:**
- Modify: `.github/workflows/ci.yml` (blocks: `on:`, `concurrency:`, `test-unit`, `test-integration`, `frontend`, `test-e2e`, `warnings-summary`; add `timeout-minutes` to 11 jobs)

**Interfaces:**
- Consumes: existing `changes` outputs (`backend`, `frontend`, `workflows`).
- Produces: event-gating pattern every later task reuses:
  `github.event_name == 'schedule' || github.event_name == 'workflow_dispatch' || (github.event_name == 'pull_request' && <path/draft condition>)`

- [ ] **Step 1: Write the failing validation check**

Create `/tmp/opencode/check_triggers.py` (throwaway, not committed):

```python
"""Asserts the new trigger contract in ci.yml. Run AFTER each edit."""
import re, sys

text = open(".github/workflows/ci.yml").read()
errors = []

# 1. nightly schedule present
if "schedule:" not in text or "30 2 * * *" not in text:
    errors.append("nightly schedule (30 2 * * *) missing")

# 2. push-override removed from expensive jobs
if re.search(r"github\.event_name == 'push' \|\|", text):
    errors.append("push-override still present somewhere")

# 3. expensive jobs carry schedule/dispatch/PR gating
for job in ("test-unit:", "test-integration:", "frontend:", "test-e2e:"):
    m = re.search(rf"^  {re.escape(job)}\n(?:.*\n)*?    if: >-\n      (.*\n(?: {10}.*\n)*)",
                  text, re.M)
    if not m or "github.event_name == 'schedule'" not in m.group(1):
        errors.append(f"{job} lacks schedule/dispatch/PR gating")

# 4. job-level timeouts everywhere
for job in ("changes:", "architecture:", "lint:", "typecheck:", "security:",
            "test-unit:", "test-integration:", "update-coverage-badge:",
            "frontend:", "test-e2e:", "warnings-summary:"):
    m = re.search(rf"^  {re.escape(job)}\n(?:.*\n)*?    timeout-minutes: \d+",
                  text, re.M)
    if not m:
        errors.append(f"{job} lacks job-level timeout-minutes")

# 5. concurrency includes event_name (nightly must survive a push)
if "group: ${{ github.workflow }}-${{ github.event_name }}-${{ github.ref }}" not in text:
    errors.append("concurrency group must include github.event_name")

print("\n".join(errors) if errors else "OK")
sys.exit(1 if errors else 0)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 /tmp/opencode/check_triggers.py`
Expected: FAIL — lists missing schedule, push-overrides still present, missing timeouts.

- [ ] **Step 3: Edit `.github/workflows/ci.yml`**

3a. `on:` block — add schedule after `workflow_dispatch:`:

```yaml
on:
  workflow_dispatch:
  schedule:
    # Nightly FULL run (default branch): PRs are the gate; this is the
    # post-merge safety net (spec 2026-09-29 §3). 02:30 UTC.
    - cron: "30 2 * * *"
```

3b. `concurrency:` — nightly must not be cancelled by a same-ref push:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.event_name }}-${{ github.ref }}
  cancel-in-progress: true
```

3c. `changes` job — dorny/paths-filter has no diff base on `schedule`; the JOB must keep running on all events (a skipped `needs` dependency force-skips dependents and would gut the nightly run), so gate only the filter STEP:

```yaml
  changes:
    name: Detect Changes
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v7
      - uses: dorny/paths-filter@v4
        id: filter
        # schedule runs have no diff base — skip the filter there; outputs
        # stay empty and are only consulted on PRs (expensive jobs gate on
        # `github.event_name == 'schedule' ||` first, so nightly runs full).
        if: github.event_name != 'schedule'
        with:
          ...
```

3d. Add `timeout-minutes` (job level, right after `runs-on:`): `architecture: 10`, `lint: 10`, `typecheck: 15`, `security: 15`, `test-unit: 20`, `test-integration: 30`, `update-coverage-badge: 5`, `frontend: 20`, `test-e2e: 30`, `warnings-summary: 5`. (`frontend-standalone` already has `timeout-minutes: 10`.)

3e. `test-unit` — currently has NO `if:`; add (before `permissions:`):

```yaml
    # PR-gated full suite; nightly/dispatch run everything (spec §3).
    if: >-
      github.event_name == 'schedule' ||
      github.event_name == 'workflow_dispatch' ||
      github.event_name == 'pull_request'
```

3f. `test-integration` — replace the existing `if:` block:

```yaml
    if: >-
      github.event_name == 'schedule' ||
      github.event_name == 'workflow_dispatch' ||
      (github.event_name == 'pull_request' &&
       needs.changes.outputs.backend == 'true' &&
       github.event.pull_request.draft != true)
```

3g. `frontend` — same pattern with `frontend`/`workflows` outputs:

```yaml
    if: >-
      github.event_name == 'schedule' ||
      github.event_name == 'workflow_dispatch' ||
      (github.event_name == 'pull_request' &&
       (needs.changes.outputs.frontend == 'true' ||
        needs.changes.outputs.workflows == 'true') &&
       github.event.pull_request.draft != true)
```

3h. `test-e2e` — replace `if: github.event_name == 'push' && github.ref == 'refs/heads/main'`:

```yaml
    # Full-stack E2E moved from every main-push to nightly + manual
    # dispatch (spec §3; was 192 min of the Sept 1-14 burn).
    if: >-
      github.event_name == 'schedule' ||
      github.event_name == 'workflow_dispatch'
```

3i. `warnings-summary` — skip when both warning producers are skipped (push-smoke runs):

```yaml
    if: >-
      always() && !cancelled() &&
      (needs.test-unit.result != 'skipped' ||
       needs.frontend.result != 'skipped')
```

- [ ] **Step 4: Run validation — must pass**

Run: `python3 /tmp/opencode/check_triggers.py`
Expected: `OK`

- [ ] **Step 5: Docs gate**

Run: `uv run --no-sync python scripts/check_gate_drift.py`
If it reports drift for changed triggers (e.g. "runs-on/push documented"): update the gate table in the doc file it names (expected: `.opencode/context/narrare-dev/processes/quality-gates.md`) so triggers match. Keep the edit minimal (trigger columns only).

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(workflows): PR-gate trigger model, push smoke, nightly full run

Remove push-trigger full-CI override: expensive jobs now run on PR
(path-gated) + nightly schedule + workflow_dispatch only; push keeps
the smoke set (architecture/lint/typecheck/security). Adds job-level
timeouts and nightly-safe concurrency grouping."
```

---

### Task 2: Badge `[skip ci]` + `persist-credentials: false`

**Files:**
- Modify: `.github/workflows/ci.yml` (blocks: `update-coverage-badge`, all `actions/checkout` steps except the badge job's)

**Interfaces:**
- Consumes: Task 1 gating (badge needs `test-unit`, which no longer runs on push — see Step 3 note).
- Produces: none (leaf hardening).

- [ ] **Step 1: Failing check** — extend `/tmp/opencode/check_triggers.py` or verify by grep:

```bash
! grep -n "persist-credentials: false" .github/workflows/ci.yml && echo "FAIL: not set yet"
grep -c "persist-credentials: false" .github/workflows/ci.yml  # expect 0 before, ≥9 after
```

Expected now: FAIL (0 occurrences).

- [ ] **Step 2: Badge job — gate + skip-ci commit**

In `update-coverage-badge`: badge must still update on merge-to-main pushes AND nightly, but its commit must never re-trigger CI:

```yaml
    if: >-
      (github.event_name == 'push' && github.ref == 'refs/heads/main') ||
      github.event_name == 'schedule'
```

In the `Commit changes` step:

```yaml
      - name: Commit changes
        uses: stefanzweifel/git-auto-commit-action@v7
        with:
          # [skip ci] prevents the badge commit from re-triggering a full
          # push CI run (spec §4.1 — the amplifier loop).
          commit_message: "docs: update coverage badge [skip ci]"
          file_pattern: README.md
```

**Note:** on `schedule`, `test-unit` runs (Task 1) so the artifact exists; on push-to-main `test-unit` is now SKIPPED — the badge would find no artifact. Therefore change the badge's own `if` to schedule-only, and add a nightly-independent fallback is NOT wanted (keep it simple):

```yaml
    if: github.event_name == 'schedule'
```

The README badge then updates once daily from the nightly full run — acceptable per spec §4.1 ("runs on push-to-main + schedule" collapses to schedule because push no longer produces coverage artifacts).

- [ ] **Step 3: `persist-credentials: false`**

Add to EVERY `actions/checkout@v7` step in jobs that execute PR-supplied code: `changes` (harmless, skip), `architecture`, `lint`, `typecheck`, `security`, `test-unit`, `test-integration`, `frontend`, `frontend-standalone`, `test-e2e`, `warnings-summary` (has no checkout), `zizmor` (Task 5 adds it itself). Exact edit per checkout:

```yaml
      - uses: actions/checkout@v7
        with:
          # Jobs below execute PR-supplied scripts — do not leave the
          # repo token persisted in the workspace (spec §5.4).
          persist-credentials: false
```

EXCEPTION: `update-coverage-badge`'s checkout keeps default (git-auto-commit needs the token). Count: 10 checkouts get the flag.

- [ ] **Step 4: Verify**

```bash
grep -c "persist-credentials: false" .github/workflows/ci.yml  # expect 10
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo YAML-OK
uv run --no-sync python scripts/check_gate_drift.py
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(workflows): badge updates via nightly only, [skip ci] commit; persist-credentials off

Badge job no longer runs on push (no coverage artifact exists there
after Task 1); nightly owns the README badge. Its auto-commit carries
[skip ci] so badge pushes never re-trigger CI. Checkouts in jobs that
run PR code no longer persist the repo token."
```

---

### Task 3: Nightly quota budget report

**Files:**
- Modify: `.github/workflows/ci.yml` (new job `budget-report`, placed after `warnings-summary`)

**Interfaces:**
- Consumes: `github.token` with `actions: read`.
- Produces: `::warning::` annotation + step summary (no outputs).

- [ ] **Step 1: Add the job**

```yaml
  # -------------------------------------------------------------------------
  # Quota guardrail (spec §4.3): month-to-date Actions minutes vs the
  # 2000-min GitHub Free quota. Run-duration approximation — undercounts
  # parallel-job billing by roughly 10-20%, so treat 80% as "act now".
  # -------------------------------------------------------------------------
  budget-report:
    name: Quota Budget Report
    if: github.event_name == 'schedule'
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      actions: read
    steps:
      - name: Sum month-to-date workflow minutes
        env:
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
        run: |
          python3 - <<'EOF'
          import json, os, urllib.request
          from datetime import datetime, timezone

          quota = 2000
          warn_at = 0.80
          first = datetime.now(timezone.utc).strftime("%Y-%m-01T00:00:00Z")

          def fetch(page):
              url = (f"https://api.github.com/repos/{os.environ['REPO']}/actions/runs"
                     f"?per_page=100&page={page}&created=>={first}")
              req = urllib.request.Request(url, headers={
                  "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
                  "Accept": "application/vnd.github+json"})
              with urllib.request.urlopen(req) as r:
                  return json.load(r)

          total = 0.0
          for page in range(1, 11):  # 10 x 100 runs/month is ample
              data = fetch(page)
              runs = data.get("workflow_runs", [])
              for run in runs:
                  if run["event"] == "dynamic":   # Dependabot runs are free
                      continue
                  started, updated = run.get("run_started_at"), run.get("updated_at")
                  if started and updated and run.get("status") == "completed":
                      s = datetime.fromisoformat(started.replace("Z", "+00:00"))
                      u = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                      total += (u - s).total_seconds() / 60
              if len(runs) < 100 or data.get("incomplete_results"):
                  break
          pct = total / quota
          summary = (f"Month-to-date CI usage: {total:.0f} min of {quota} "
                     f"({pct:.0%}, run-duration approximation).")
          print(summary)
          with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
              fh.write(summary + "\n")
          if pct >= warn_at:
              print(f"::warning title=Actions quota::Quota at {pct:.0%} — "
                    "activate reserve levers (spec §8: Phase 2 consolidation, "
                    "weekly nightly).")
          EOF
```

- [ ] **Step 2: Verify locally (syntax + smoke)**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo YAML-OK
# extract and run the embedded python against the live repo (read-only):
gh auth status >/dev/null && sed -n '/<<.EOF./,/^          EOF$/p' .github/workflows/ci.yml \
  | sed '1d;$d' | REPO=jmerifjKriwe/narrare GH_TOKEN=$(gh auth token) python3 -
```
Expected: prints a `Month-to-date CI usage: … min` line (approx. 1500–1900 for September).

- [ ] **Step 3: Gate check + Commit**

```bash
uv run --no-sync python scripts/check_gate_drift.py
git add .github/workflows/ci.yml
git commit -m "ci(workflows): nightly quota budget report with 80% warning

Aggregates month-to-date workflow-run minutes via the Actions API
(actions: read), excludes free Dependabot dynamic runs, warns at 80%
of the 2000-min quota so exhaustion is seen days early."
```

---

### Task 4a: SHA-pin actions (ci.yml, eval-nightly, mutation)

**Files:**
- Modify: `.github/workflows/ci.yml`, `.github/workflows/eval-nightly.yml`, `.github/workflows/mutation-testing-monthly.yml`

**Interfaces:**
- Produces: SHA-pinned `uses:` refs — Task 5's zizmor config requires ALL refs pinned (`unpinned-uses` promoted to blocking).

- [ ] **Step 0: Missing timeout (spec §4.2 — this file's job has none)**

`mutation-testing-monthly.yml`'s single job gets `timeout-minutes: 120` right after `runs-on: ubuntu-latest` (job measured ~20 min; 120 leaves headroom for monthly growth):

```yaml
    runs-on: ubuntu-latest
    timeout-minutes: 120
```

- [ ] **Step 1: Resolve SHAs for every distinct ref**

For each `owner/repo@tag` in the three files (expect: actions/checkout@v7, dorny/paths-filter@v4, astral-sh/setup-uv@v7, actions/cache@v6, actions/cache/restore@v6, actions/cache/save@v6, actions/upload-artifact@v7, actions/download-artifact@v8, extractions/setup-just@v4, pnpm/action-setup@v6, actions/setup-node@v7, stefanzweifel/git-auto-commit-action@v7, MishaKav/pytest-coverage-comment@v1.12.2, actions/github-script@v9 — verify by grep, resolve what's actually present):

```bash
gh api repos/actions/checkout/commits/v7 --jq .sha
```

Record tag AND sha. Verify each sha resolves back: `gh api repos/actions/checkout/git/commits/<sha> --jq .sha`.

- [ ] **Step 2: Rewrite every `uses:` line**

Format (40-char sha + version comment):

```yaml
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v7.0.1
```

Use `sed` per file or edit manually — every `uses:` in the three files must match `@[0-9a-f]{40} # v`.

- [ ] **Step 3: Verify**

```bash
grep -rn "uses:" .github/workflows/ci.yml .github/workflows/eval-nightly.yml \
  .github/workflows/mutation-testing-monthly.yml \
  | grep -v "@[0-9a-f]\{40\} # v" && echo "FAIL: unpinned ref remains" || echo "OK: all pinned"
python3 -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]" && echo YAML-OK
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml .github/workflows/eval-nightly.yml .github/workflows/mutation-testing-monthly.yml
git commit -m "ci(workflows): pin actions to commit SHAs (ci, eval-nightly, mutation)

Tag refs are mutable (tag-poisoning vector, cf. TanStack incident
followup). Dependabot github_actions keeps SHA-pinned refs updated."
```

---

### Task 4b: SHA-pin actions (vrt-update-baselines, release-please)

**Files:**
- Modify: `.github/workflows/vrt-update-baselines.yml`, `.github/workflows/release-please.yml`

**Interfaces:** identical procedure to Task 4a (expect googleapis/release-please-action@v5 + shared actions).

- [ ] **Step 1: Resolve SHAs** — same `gh api repos/OWNER/REPO/commits/TAG --jq .sha` loop for refs found via `grep -n "uses:"` in both files.
- [ ] **Step 2: Rewrite** — same `@<40-sha> # vX.Y.Z` format.
- [ ] **Step 3: Verify** — same grep (both files) + YAML parse.
- [ ] **Step 4: Commit**

```bash
git add .github/workflows/vrt-update-baselines.yml .github/workflows/release-please.yml
git commit -m "ci(workflows): pin actions to commit SHAs (vrt, release-please)"
```

---

### Task 5: zizmor as blocking workflow-security check

**Files:**
- Create: `.github/zizmor.yml`
- Modify: `.github/workflows/ci.yml` (new job `zizmor` after `security`)

**Interfaces:**
- Consumes: Task 1's `changes.workflows` output; Task 4a/4b pinning (job passes only when everything is SHA-pinned).
- Produces: none (leaf check). Note: `.github/zizmor.yml` lives under `.github/` → CODEOWNERS coverage from Task 6 applies.

- [ ] **Step 1: Determine exact zizmor version (locally)**

```bash
uvx zizmor --version   # note X.Y.Z — used to pin below
```

- [ ] **Step 2: Write `.github/zizmor.yml`**

```yaml
# zizmor config — GitHub Actions security auditing (spec §5.2).
# Plain CLI in CI, blocking; no SARIF (private repo, Free plan: no GHAS).
# Docs: https://docs.zizmor.sh/usage/
rules:
  unpinned-uses:
    # pedantic by default; promoted to blocking — every `uses:` must be
    # SHA-pinned (Tasks 4a/4b). Dependabot keeps the pins fresh.
    level: high
```

- [ ] **Step 3: Add the job to `ci.yml`** (insert after the `security` job)

```yaml
  # -------------------------------------------------------------------------
  # Workflow security audit (zizmor) — blocking PR check when workflows
  # change + nightly (spec §5.2). Catches: dangerous triggers, template
  # injection, impostor commits, vulnerable action versions, unpinned uses.
  # -------------------------------------------------------------------------
  zizmor:
    name: Workflow Security (zizmor)
    runs-on: ubuntu-latest
    timeout-minutes: 5
    needs: [changes]
    if: >-
      github.event_name == 'schedule' ||
      github.event_name == 'workflow_dispatch' ||
      (github.event_name == 'pull_request' &&
       needs.changes.outputs.workflows == 'true')
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@<RESOLVED_SHA_FROM_TASK_4a> # vX.Y.Z
        with:
          persist-credentials: false

      - name: Run zizmor
        env:
          # GITHUB_TOKEN enables zizmor's online audits (impostor-commit,
          # known-vulnerable-actions) against this private repo.
          GITHUB_TOKEN: ${{ github.token }}
        run: |
          pipx install "zizmor==X.Y.Z"   # literal from Step 1
          zizmor --config .github/zizmor.yml .github/workflows/
```

- [ ] **Step 4: Local verification (this is the real test)**

```bash
uvx zizmor --config .github/zizmor.yml .github/workflows/
```
Expected: exit 0, no findings above informational. If `unpinned-uses` fires: a pin from Task 4a/4b is missing — fix that pin, not the config.

- [ ] **Step 5: Gate check + Commit**

```bash
uv run --no-sync python scripts/check_gate_drift.py
git add .github/zizmor.yml .github/workflows/ci.yml
git commit -m "ci(workflows): add blocking zizmor workflow-security check

Runs when .github/** changes (paths-filter output) plus nightly;
unpinned-uses promoted to high severity. Plain CLI, no SARIF (no GHAS
on private Free-plan repos). zizmor version pinned via pipx."
```

---

### Task 6: CODEOWNERS for `.github/`

**Files:**
- Create: `.github/CODEOWNERS`

**Interfaces:** none (leaf). Pairs with zizmor (Task 5) for human review of workflow changes.

- [ ] **Step 1: Create `.github/CODEOWNERS`**

```
# CODEOWNERS — review ownership for CI/supply-chain surfaces (spec §5.3).
# zizmor catches mechanical issues; this routes workflow changes through
# human review.
.github/              @jmerifjKriwe
.github/zizmor.yml    @jmerifjKriwe
```

- [ ] **Step 2: Verify file is picked up**

```bash
test -f .github/CODEOWNERS && echo OK
python3 -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]" && echo YAML-OK
```

- [ ] **Step 3: Commit**

```bash
git add .github/CODEOWNERS
git commit -m "chore(ci): CODEOWNERS review gate for .github/"
```

---

## Post-implementation (coordinator-owned, not a task here)

1. `just verify` + `scripts/check_architecture.py --prompt-integrity` full pass.
2. Merge `kinetic-falcon` → PR → `main` (PR-gate model is now live for its own change).
3. Observe per spec §7: smoke push (4 jobs), backend-only PR (frontend skips), nightly (full + budget report).
4. Update `docs/_shared/CURRENT_STATE.md`; persist memory entries (worktree bootstrap, PR-batching discipline).
