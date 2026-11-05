# GitHub Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the three-in-one `ci.yml` with one workflow per concern, one required check, a security baseline, and a Dependabot configuration that stops fanning every bump out over every E2E suite.

**Architecture:** `ci.yml` is the PR/merge gate; `nightly.yml` is the scheduled sweep; `release-please.yml` only orchestrates releases; `publish.yml` is dormant until a `Dockerfile` exists; `codeql.yml` and `scorecard.yml` are advisory security signals. Shared gates live in three reusable workflows plus one composite setup action; `ci-required` is the only required status check. `affected.py` gains a `HARNESS` class; dependency bumps stay fully tested but are grouped weekly.

**Tech Stack:** GitHub Actions YAML, `actionlint`, `zizmor`, `gh` CLI, `just`, `uv`, `pnpm`, PostgreSQL + pgvector.

**Spec:** `docs/superpowers/specs/2026-11-05-github-platform-design.md`

## Global Constraints

- Every action is pinned by full commit SHA with a trailing release comment. Dependabot keeps the pins current.
- CI calls `just` recipes; no inline equivalents. The one inline pytest invocation in today's `ci.yml` becomes the `test-cov` recipe.
- Versions: Python 3.14, Node 22, pnpm 11.5.2, just 1.58.0, PostgreSQL `pgvector/pgvector:pg17` on host port 5433.
- Top-level `permissions: {}` in every workflow; each job grants only what it uses.
- Every job has `timeout-minutes`.
- Conventional commits. `feat`/`fix` carry a real `User-visible:` line; this plan uses `ci`, `docs`, `test` and `chore`. Agent commits end with `Assisted-by: OpenCode (DeepSeek V4.1 Flash)`.
- No `--no-verify`, no force push.
- Every new gate gets a bidirectional proof: make it fail deliberately, read the red output, revert, read the green output.
- Nothing is committed before its review is green. In subagent-driven execution the implementer leaves the tree dirty; the coordinator commits after the reviewer reports. Implementers never commit or push.
- Operational `gh api` writes — the ruleset, repository settings, the CodeQL default-setup switch — are coordinator actions. The implementer prepares the payload and the read-back commands; the coordinator applies them and records the result.
- The ruleset update replaces the whole rules array. The submission carries every rule in the spec's inventory, and the API diff is read back afterwards.
- `main` is a public repository: Actions minutes are free; the currency is wall-clock and review noise.
- The uncommitted screenshot work on the original `main` checkout is out of scope; this worktree is isolated from it.

## Review Focus

1. **A required check that never reports** — a path-filtered required workflow, a renamed job, or a `ci-required` that skips itself. Expect: a PR never sits on "Expected — Waiting for status report".
2. **A ruleset replacement that drops a rule or bypass** — Copilot review, code quality, thread resolution, non-fast-forward, deletion, admin bypass. Expect: only the named changes differ from the captured before-JSON.
3. **A reusable workflow that loses a capability** — Postgres service, `CODECOV_TOKEN`, `security-events: write`, or the caller's permissions. Expect: the gate runs with the same capability as the inline version it replaced.
4. **A broken lockfile contract** — `uv sync --locked` and `pnpm install --frozen-lockfile` after Dependabot changes. Expect: a stale lock fails loudly, never silently resolves.
5. **An `affected.py` misclassification** — a workflow change that owes every suite, or a capability change that owes none. Expect: the reason line names the class.

## File Structure

**Create**
- `.github/workflows/nightly.yml`
- `.github/workflows/_lint.yml`
- `.github/workflows/_test.yml`
- `.github/workflows/_e2e.yml`
- `.github/workflows/codeql.yml`
- `.github/workflows/scorecard.yml`
- `.github/actions/setup/action.yml`
- `docs/architecture/github.md`

**Modify**
- `.github/workflows/ci.yml`
- `.github/workflows/release-please.yml`
- `.github/dependabot.yml`
- `scripts/affected.py`
- `app/kernel/tests/test_affected.py`
- `justfile`
- `README.md`
- `docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md` (§6 recipe count)

**Delete**
- `.coderabbit.yaml`

**Dormant**
- `.github/workflows/publish.yml` — not created in this plan; it returns with a `Dockerfile`.

---

## Phase 1 — the nightly is its own workflow

### Task 1: Split `nightly.yml` out of `ci.yml`

**Files:**
- Create: `.github/workflows/nightly.yml`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: `nightly.yml` with job `gate` (outputs `proceed`, `capabilities`), the inline gates `lint-types`, `tests`, `frontend`, `build`, the `e2e-suites` matrix and `nightly-result`; `ci.yml` without `schedule`, `nightly-guard`, or any `needs.nightly-guard` condition.
- Later tasks replace the inline gates with reusable workflows; this task keeps them inline so the split is one reviewable change.

- [ ] **Step 1: Capture the baseline**

Run: `gh run list --workflow ci.yml --limit 5`
Expected: the current runs include `schedule` and `pull_request` events. Record the latest successful `schedule` run's `head_sha` in the task report.

- [ ] **Step 2: Write `nightly.yml`**

`on:` is `schedule` (`17 3 * * *`) and `workflow_dispatch`. `concurrency` is `nightly`, `cancel-in-progress: false`. Top-level `permissions: {}`.

Job `gate`:
- `permissions: actions: read, contents: read`
- steps: checkout; the existing guard from `ci.yml`, but querying
  `repos/$GH_REPO/actions/workflows/nightly.yml/runs?event=schedule&status=success&per_page=1`;
  on `proceed=true`, run `python3 scripts/affected.py --all --json` and write
  the JSON to `capabilities` output.
- outputs: `proceed`, `capabilities`.

Jobs `lint-types`, `tests`, `frontend`, `build`: copy the current `ci.yml`
definitions verbatim, with one exception: the nightly's `tests` runs plain
`just test` and carries no coverage/Codecov steps — coverage stays a
`main`-push concern and the nightly reports through its issue. Add
`timeout-minutes` (15/20/10/15). Each job's `if:` is
`needs.gate.outputs.proceed == 'true'`.

Job `e2e-suites`: matrix `capability: ${{ fromJSON(needs.gate.outputs.capabilities) }}`,
`fail-fast: false`, `needs: [gate]`, `if: needs.gate.outputs.proceed == 'true'`;
copy the current E2E job body.

Job `nightly-result`:
- `needs: [gate, lint-types, tests, frontend, build, e2e-suites]`
- `if: always() && needs.gate.outputs.proceed == 'true'`
- `permissions: issues: write, contents: read`
- On failure: create or update one open issue labeled `ci/nightly` with the
  failed run URL and the failed job names. On success: close an open
  `ci/nightly` issue if one exists. Use `gh` with `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}`.
- `timeout-minutes: 5`.

- [ ] **Step 3: Remove the schedule and the guard from `ci.yml`**

Delete the `schedule:` trigger, the `nightly-guard` job, and every
`needs: nightly-guard` / `if: needs.nightly-guard.outputs.proceed == 'true'`
condition. `changes` loses its `schedule` branch: the modes are now
`pull_request` (`--base origin/main`), `push` (`--none`) and
`workflow_dispatch` (`--all`). Keep the `--release-pr` detection exactly as
it is: the release branch still owes no E2E. Keep the `e2e` aggregator for
now; Task 4 replaces it.

Add `workflow_dispatch:` to `ci.yml`.

- [ ] **Step 4: Add timeouts, least privilege and the per-SHA main group**

Set top-level `permissions: {}`; each job grants what it uses
(`contents: read` for build/lint/tests, `actions: read` only where the guard
used it, `issues: write` only in `nightly-result`).

Add `timeout-minutes`: `lint-types` 15, `tests` 20, `build` 15, `e2e-suites`
30, `e2e` 5, `changes` 10.

Replace the concurrency block with:
`group: ci-${{ github.ref }}${{ github.event_name == 'push' && format('-{0}', github.sha) || '' }}`
and `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`.

- [ ] **Step 5: Lint the workflows**

Run: `zizmor .github/workflows/ci.yml .github/workflows/nightly.yml`
Run: `docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.7 -color`
Expected: both exit 0. If zizmor reports a finding, fix it; a suppression
needs a comment naming the concrete false positive.

- [ ] **Step 6: Verify the event split (local, then coordinator)**

Run: `gh workflow view nightly.yml --ref ci/github-platform` and
`gh workflow view ci.yml --ref ci/github-platform` once the coordinator has
pushed the branch.
Expected: `nightly.yml` lists `schedule` and `workflow_dispatch`; `ci.yml`
lists `pull_request`, `push` and `workflow_dispatch`, no `schedule`.

The coordinator then runs:
`gh workflow run nightly.yml --ref ci/github-platform`
`gh run list --workflow nightly.yml --limit 1`
Expected: the dispatch run appears and the `gate` job proceeds (manual
dispatch never skips). The implementer records this as a pending remote
check in the report; it is not a local step.

- [ ] **Step 7: Commit after review**

```bash
git add .github/workflows/ci.yml .github/workflows/nightly.yml
git commit -m "ci(gates): the nightly is its own workflow, not a branch of the PR gate" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

---

## Phase 2 — one required check, and the workflows linted

### Task 2: `just test-cov`

**Files:**
- Modify: `justfile`
- Modify: `.github/workflows/ci.yml` (the `tests` job)
- Modify: `docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md` (§6)

**Interfaces:**
- Produces: `just test-cov` — the coverage invocation, callable locally and by CI. `just test` stays unchanged.

- [ ] **Step 1: Add the recipe**

In `justfile`, after `test-file`:

```make
# Every integration test with coverage, for the main-push report.
test-cov:
    uv run pytest app --cov --cov-branch --cov-report=xml --junitxml=junit.xml -o junit_family=legacy
```

- [ ] **Step 2: Run it**

Run: `just test-cov`
Expected: PASS; `coverage.xml` and `junit.xml` exist at the repo root.

- [ ] **Step 3: Point `ci.yml` at it**

The `tests` job's `main`-push branch runs `just test-cov`; every other event
runs `just test`. Delete the inline `uv run pytest app --cov ...` command.

- [ ] **Step 4: Correct the spec count**

In `docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md`,
the §6 recipe list and count say 21 while `just --list` already carries 23.
Add `test-cov` to the list and state 24. Do not renumber anything else.

- [ ] **Step 5: Verify**

Run: `just --list | grep -c '^    [a-z]'`
Expected: `24`.
Run: `zizmor .github/workflows/ci.yml` and `docker run ... actionlint`
Expected: exit 0.

- [ ] **Step 6: Commit after review**

```bash
git add justfile .github/workflows/ci.yml docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md
git commit -m "ci(gates): coverage runs through a recipe, not an inline pytest call" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

### Task 3: `workflow-lint`

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create (only if a suppression is unavoidable): `.github/zizmor.yml`

**Interfaces:**
- Produces: job `workflow-lint` in `ci.yml`, `runs-on: ubuntu-latest`, `timeout-minutes: 10`, `permissions: contents: read`. Runs on every event, no path filter.

- [ ] **Step 1: Establish the baseline**

Run: `zizmor .github/workflows .github/actions`
Run: `docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.7 -color`
Record every finding in the task report. Fix each one; the likely classes are
persisted checkout credentials (`persist-credentials: false`), overly broad
permissions, and template injection through `run:` expressions. A suppression
goes into `.github/zizmor.yml` with a comment naming the concrete false
positive; silent suppressions are forbidden.

- [ ] **Step 2: Add the job**

`workflow-lint` checks out the repo, runs `actionlint` and `zizmor` with the
pinned versions the baseline used, and fails on any finding. Add it to the
`ci-required` needs in Task 4; in this task it is a plain job.

- [ ] **Step 3: Prove it bites**

Introduce a deliberate `actionlint` error in a scratch copy of a workflow
(e.g., `if: ${{ github.event_name == }}`), run the job locally, read the red
output, revert. Do the same for zizmor with an unpinned `uses:` line.

- [ ] **Step 4: Verify**

Run: `zizmor .github/workflows` and `actionlint`
Expected: exit 0 on the reverted tree.

- [ ] **Step 5: Commit after review**

```bash
git add .github/workflows/ci.yml .github/zizmor.yml
git commit -m "ci(gates): the workflows are linted like the code" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

### Task 4: `ci-required`

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: job `ci-required`, `if: always()`, `needs: [changes, lint-types, tests, frontend, build, workflow-lint, e2e-suites]`; one step reads `needs.*.result` and `needs.changes.outputs.capabilities`.
- Removes: the `e2e` aggregator job.

- [ ] **Step 1: Write the aggregator**

The step's contract, in the same explicit style as today's `e2e` aggregator:
- `changes` must be `success`; a broken handover is red.
- `changes.outputs.capabilities` must be non-empty; an empty string is red.
- `capabilities == '[]'`: green, with a notice that no suite was owed.
- `e2e-suites` must be `success` when capabilities is non-empty; any other
  result is red.
- `lint-types`, `tests`, `frontend`, `build`, `workflow-lint` must each be
  `success`; a `skipped` result is red (these jobs have no legitimate skip).
- `dependency-review` joins the list in Task 12 with `skipped` allowed on
  non-PR events.

**Keep the `e2e` job for now.** The ruleset still requires it until Task 5;
removing it here would leave a required context that never reports and block
every PR. `ci-required` is added alongside it; both aggregators are green
during the switch. Task 5 removes `e2e` after the ruleset no longer names it.

- [ ] **Step 2: Prove the skip hole is closed**

Locally, run the aggregator script with `CAPABILITIES='[]'` (green),
`CAPABILITIES=''` (red), `SUITES=skipped` with a non-empty list (red), and a
failing `lint-types` (red). Record each output in the task report.

- [ ] **Step 3: Verify on a draft PR**

Open a draft PR with a docs-only change. Expected: `ci-required` is green,
`e2e-suites` is skipped, the notice says no suite was owed. Push a code
change to the same PR. Expected: the affected suites run and `ci-required`
waits on them. `e2e` also runs and is green, because the ruleset still
requires it.

- [ ] **Step 4: Commit after review**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(gates): one required check judges every gate" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

### Task 5: Switch the ruleset to `ci-required`

**Coordinator task.** The implementer prepares the before/after JSON and the read-back commands; the coordinator applies the `PUT` and records the result. The ruleset is a shared branch's gate; an implementer does not write it.

**Files:**
- Modify: `.github/workflows/ci.yml` (remove the `e2e` job after the switch)

**Interfaces:**
- Consumes: a green `ci-required` run on `main` (Task 4 merged) and the `e2e` job still present.
- Produces: ruleset id `18702224` requiring only `ci-required`; every other rule carried verbatim; the Dependabot integration bypass removed; the admin bypass kept; the `e2e` job removed only after the read-back proves the ruleset no longer names it.

- [ ] **Step 1: Capture the before state**

```bash
gh api repos/jmerifjKriwe/narrare/rulesets/18702224 > /tmp/opencode/ruleset-before.json
```

Read the file. The rules array must contain `required_status_checks`,
`pull_request`, `copilot_code_review`, `code_quality`, `non_fast_forward`,
`deletion`. The bypass actors are the admin role (5) and the Dependabot
integration (29110).

- [ ] **Step 2: Build the after state with `jq`**

Replace the `required_status_checks` parameters with
`{"strict_required_status_checks_policy": true, "do_not_enforce_on_create": false,
"required_status_checks": [{"context": "ci-required", "integration_id": 15368}]}`.
Change `allowed_merge_methods` to `["merge"]`. Drop the bypass actor whose
`actor_id` is `29110`. Keep every other rule and the admin bypass. Write the
result to `/tmp/opencode/ruleset-after.json`.

- [ ] **Step 3: Diff before and after**

Run: `diff -u /tmp/opencode/ruleset-before.json /tmp/opencode/ruleset-after.json`
Expected: exactly the three changes above, nothing else. Read the diff in the
task report.

- [ ] **Step 4: Apply**

```bash
gh api -X PUT repos/jmerifjKriwe/narrare/rulesets/18702224 --input /tmp/opencode/ruleset-after.json
```

- [ ] **Step 5: Read back**

```bash
gh api repos/jmerifjKriwe/narrare/rulesets/18702224 > /tmp/opencode/ruleset-readback.json
diff -u /tmp/opencode/ruleset-after.json /tmp/opencode/ruleset-readback.json
```
Expected: only server-added fields (`id`, `node_id`, timestamps, links)
differ. The required check is `ci-required` alone; the bypass list has the
admin role only.

- [ ] **Step 6: Prove the gate still bites**

Open a PR with a deliberate `ruff` failure. Expected: `ci-required` is red
and the PR cannot merge without the admin bypass. Revert.

- [ ] **Step 7: Retire the old aggregator**

Only after Step 5's read-back proves the ruleset names `ci-required` alone,
remove the `e2e` job from `ci.yml`. Commit it. The old check is no longer
required, so its disappearance cannot block a PR.

```bash
git add .github/workflows/ci.yml
git commit -m "ci(gates): the old e2e aggregator retires after the ruleset switch" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

- [ ] **Step 8: Record**

The task report carries the before/after/read-back JSON paths and the
test-PR numbers; Task 18 copies the final state into
`docs/architecture/github.md`.

---

## Phase 3 — one definition per gate

### Task 6: The setup composite

**Files:**
- Create: `.github/actions/setup/action.yml`

**Interfaces:**
- Produces: `uses: ./.github/actions/setup` with inputs `python-version` (3.14), `node-version` (22), `pnpm-version` (11.5.2), `just-version` (1.58.0), `node` (`"true"`/`"false"`, default `"true"`).
- The action runs `uv sync --locked`; when `node` is true it also installs pnpm, Node with the pnpm cache, and runs `pnpm install --frozen-lockfile`. Checkout stays with the caller.

- [ ] **Step 1: Write the composite**

`runs: using: composite`; steps in this order: `astral-sh/setup-uv`
(`enable-cache: true`), `actions/setup-python`, `uv sync --locked`,
`pnpm/action-setup`, `actions/setup-node` (`cache: pnpm`),
`pnpm install --frozen-lockfile`, `extractions/setup-just`. Copy the SHAs
from the current workflows. Every `run:` step sets `shell: bash`.

- [ ] **Step 2: Lint**

Run: `zizmor .github/actions/setup/action.yml`.
Run: `docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.7 -color`
for the workflows that use it. Expected: exit 0. (actionlint lints
workflows; zizmor lints composite actions.)

- [ ] **Step 3: Prove the lockfile contract**

Temporarily edit `uv.lock`'s project version (or run `uv lock --upgrade-package`
without syncing) so the lock is stale, run the composite's `uv sync --locked`
command locally. Expected: it fails with a stale-lock message. Revert.

- [ ] **Step 4: Commit after review**

```bash
git add .github/actions/setup/action.yml
git commit -m "ci(gates): one setup action owns the toolchain versions" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

### Task 7: `_lint.yml`

**Files:**
- Create: `.github/workflows/_lint.yml`
- Modify: `.github/workflows/ci.yml`, `.github/workflows/nightly.yml`

**Interfaces:**
- Produces: `uses: ./.github/workflows/_lint.yml` with the same inputs as the composite; job name `lint-types`.
- Consumes: the composite from Task 6.

- [ ] **Step 1: Write the reusable workflow**

`on: workflow_call` with the version inputs. One job `lint-types`:
`runs-on: ubuntu-latest`, `timeout-minutes: 15`, `permissions: contents: read`;
checkout with `fetch-depth: 0` and `persist-credentials: false`; the
composite; `just lint`; `just typecheck`; `gitleaks/gitleaks-action` with
`GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}`.

- [ ] **Step 2: Switch both callers**

Replace the inline `lint-types` job in `ci.yml` and `nightly.yml` with the
`uses:` form, passing the inputs and `permissions: contents: read`.

- [ ] **Step 3: Verify the check still reports**

Push a PR. Expected: a check named `lint-types / lint-types` appears and
`ci-required` waits on it; the ruleset does not need a change because it
requires only `ci-required`.

- [ ] **Step 4: Commit after review**

```bash
git add .github/workflows/_lint.yml .github/workflows/ci.yml .github/workflows/nightly.yml
git commit -m "ci(gates): lint and typecheck have one definition" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

### Task 8: `_test.yml`

**Files:**
- Create: `.github/workflows/_test.yml`
- Modify: `.github/workflows/ci.yml`, `.github/workflows/nightly.yml`

**Interfaces:**
- Produces: `uses: ./.github/workflows/_test.yml` with input `coverage` (boolean, default false) and secret `CODECOV_TOKEN` (required false); job name `tests`; the `pgvector/pgvector:pg17` service on 5433.
- `coverage: true` runs `just test-cov` and, on a `main` push only, uploads `coverage.xml` and `junit.xml` to Codecov with `fail_ci_if_error: true` for coverage and the default for JUnit.

- [ ] **Step 1: Write the reusable workflow**

Declare the Postgres service exactly as today (health command, 5433:5432).
`permissions: contents: read`. Steps: checkout, composite with `node: "false"`,
`just test` or `just test-cov`, then the two Codecov uploads guarded by
`inputs.coverage && github.event_name == 'push' && github.ref == 'refs/heads/main'`
and `!cancelled()`.

- [ ] **Step 2: Switch both callers**

`ci.yml`: `with: coverage: ${{ github.event_name == 'push' && github.ref == 'refs/heads/main' }}`,
`secrets: CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}`.
`nightly.yml`: `coverage: false`.

- [ ] **Step 3: Verify both paths**

A PR run: `just test`, no Codecov step. A `main` push: `just test-cov`, both
uploads, `coverage.xml` and `junit.xml` produced. Record the run URLs.

- [ ] **Step 4: Commit after review**

```bash
git add .github/workflows/_test.yml .github/workflows/ci.yml .github/workflows/nightly.yml
git commit -m "ci(gates): the test job has one definition and one coverage recipe" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

### Task 9: `_e2e.yml` and the Playwright cache

**Files:**
- Create: `.github/workflows/_e2e.yml`
- Modify: `.github/workflows/ci.yml`, `.github/workflows/nightly.yml`

**Interfaces:**
- Produces: `uses: ./.github/workflows/_e2e.yml` with input `capability` (string, required); job `e2e (${{ inputs.capability }})`; the Postgres service; Playwright chromium.
- The caller's matrix supplies one capability per entry; no string surgery on the JSON list.

- [ ] **Step 1: Write the reusable workflow**

`permissions: contents: read`, `timeout-minutes: 30`, the Postgres service.
Steps: checkout, composite, `uv run playwright install --with-deps chromium`,
`just test-e2e ${{ inputs.capability }}`.

Add an `actions/cache` step for `~/.cache/ms-playwright`, keyed on
`${{ runner.os }}-playwright-${{ hashFiles('uv.lock') }}` (the Playwright
version lives there); the install step then becomes a no-op on a hit.

- [ ] **Step 2: Switch both callers**

`ci.yml` `e2e-suites`: `needs: [lint-types, changes]`,
`if: needs.changes.outputs.capabilities != '[]'`,
`strategy: {fail-fast: false, matrix: {capability: "${{ fromJSON(needs.changes.outputs.capabilities) }}"}}`,
`uses: ./.github/workflows/_e2e.yml`, `with: {capability: "${{ matrix.capability }}"}`,
`permissions: {contents: read}`.

`nightly.yml`: same, with `needs: [gate]` and
`matrix.capability: ${{ fromJSON(needs.gate.outputs.capabilities) }}`.

- [ ] **Step 3: Verify the cache and the matrix**

A code PR touching one capability: exactly one `e2e (<name>) / e2e (<name>)`
check. A second run of the same PR: the cache step reports a hit and the
chromium download is skipped. Record both log lines.

- [ ] **Step 4: Commit after review**

```bash
git add .github/workflows/_e2e.yml .github/workflows/ci.yml .github/workflows/nightly.yml
git commit -m "ci(gates): the E2E matrix calls one workflow per capability" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

### Task 10: `affected.py` HARNESS and the smoke suite

**Files:**
- Modify: `scripts/affected.py`
- Test: `app/kernel/tests/test_affected.py`

**Interfaces:**
- Produces: `SMOKE = "setup"`; `HARNESS: tuple[str, ...] = (".github/workflows/", ".github/actions/")`; `resolve([".github/workflows/ci.yml"]).capabilities == ["setup"]`; if `SMOKE` is not a known capability, the answer fails open to `None` with a reason.
- Removes: `.github/workflows/ci.yml` from `SHARED`; `.github/` stays `INERT` for everything else.
- No `--dependabot` flag and no `DEPENDENCY` class: dependency paths stay `SHARED`.

- [ ] **Step 1: Write the failing tests**

In `app/kernel/tests/test_affected.py`, add `"setup"` to
`FIXTURE_CAPABILITIES` and update the two all-suite expectations that count
the fixture's capabilities. Add:

```python
def test_a_workflow_change_owes_only_the_smoke_suite():
    for path in (
        ".github/workflows/ci.yml",
        ".github/workflows/nightly.yml",
        ".github/workflows/_e2e.yml",
        ".github/actions/setup/action.yml",
    ):
        assert resolve([path]).capabilities == ["setup"], path


def test_a_harness_change_without_a_known_smoke_suite_fails_open():
    # known={"chat"} has no setup suite
    assert resolve([".github/workflows/ci.yml"], known={"chat"}).capabilities is None
```

Remove `.github/workflows/ci.yml` from the `test_a_shared_surface_owes_every_suite`
tuple.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file app/kernel/tests/test_affected.py`
Expected: the new tests fail; the workflow path currently answers `None`.

- [ ] **Step 3: Implement the class**

In `resolve`, before the `SHARED` check:
if any `_matches(path, entry)` for `HARNESS`, collect the path; after the
loop, if a harness path was seen and no shared/capability path was, return
`Resolution([SMOKE], "harness change: smoke suite only")` when `SMOKE in names`,
else `Resolution(None, "harness change: smoke suite not found — all suites")`.
If a harness path and a product path are both present, the product path wins
(fail toward more suites).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `just test-file app/kernel/tests/test_affected.py`
Expected: PASS, including the existing six-suite discovery test.

- [ ] **Step 5: Measure the smoke suite**

Run `just test-e2e <each capability>` on the current tree and record the wall
clock. If `setup` is not the fastest, change `SMOKE` to the fastest and
update the tests. Record the measurement in the task report.

- [ ] **Step 6: Commit after review**

```bash
git add scripts/affected.py app/kernel/tests/test_affected.py
git commit -m "ci(gates): a workflow change owes the harness smoke, not every suite" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

### Task 11: Post-extraction verification

**Files:** none.

- [ ] **Step 1: Run the local gates**

Run: `just check`, `just test`, `just build`.
Expected: all pass.

- [ ] **Step 2: Exercise every path on a draft PR**

One PR each: docs-only (no E2E), one capability (one suite), a workflow-only
change (smoke suite), a lockfile change (all suites). Record the check lists.

- [ ] **Step 3: Confirm the required check is the only required one**

Run: `gh api repos/jmerifjKriwe/narrare/rulesets/18702224 --jq '.rules[] | select(.type=="required_status_checks")'`
Expected: `ci-required` alone.

---

## Phase 4 — the security baseline

### Task 12: Dependency review

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: job `dependency-review`, `if: github.event_name == 'pull_request'`, `permissions: contents: read, pull-requests: read`, `uses: actions/dependency-review-action@<sha>` with `fail-on-severity: high` and `deny-licenses: AGPL-1.0, AGPL-3.0, GPL-2.0, GPL-3.0`; added to `ci-required` needs with `skipped` allowed on non-PR events.

- [ ] **Step 1: Add the job**

Pin the action by SHA. Do not grant `pull-requests: write`; the summary goes
to the job log, not a PR comment.

- [ ] **Step 2: Prove it bites**

On a scratch branch, add a dependency with a denied license (or a
known-vulnerable version) and open a PR. Expected: the job fails and
`ci-required` is red. Revert.

- [ ] **Step 3: Commit after review**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(security): dependency review blocks high severity and viral licenses" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

### Task 13: CodeQL advanced setup

**Files:**
- Create: `.github/workflows/codeql.yml`

**Interfaces:**
- Produces: `codeql.yml` on `pull_request` and `push: main` for
  `app/**`, `web/**`, `scripts/**`, `.github/workflows/**`, `.github/actions/**`
  (excluding `app/generated/**`, `web/lib/api/**`, `web/dist/**`, `assets/**`),
  plus a weekly schedule; matrix `python`, `javascript-typescript`, `actions`;
  `permissions: security-events: write, contents: read, actions: read`;
  `timeout-minutes: 30`.
- Consumes: the default-setup disable below; the two must land as one operation.

- [ ] **Step 1: Disable the default setup (coordinator)**

```bash
gh api repos/jmerifjKriwe/narrare/code-scanning/default-setup
gh api -X PATCH repos/jmerifjKriwe/narrare/code-scanning/default-setup -f state=not-configured
gh api repos/jmerifjKriwe/narrare/code-scanning/default-setup
```
Expected: the first says `configured`; the last says `not-configured`.
The implementer prepares this; the coordinator runs it.

- [ ] **Step 2: Write the workflow**

`github/codeql-action/init` with `languages: ${{ matrix.language }}`,
`build-mode: none`, `queries: default`; `github/codeql-action/analyze` with
`category: /language:${{ matrix.language }}`. Pin both by SHA. The `actions`
language needs `build-mode: none`; keep the matrix entries explicit.

- [ ] **Step 3: Verify the first run**

Merge, then:
```bash
gh run list --workflow codeql.yml --limit 1
gh api repos/jmerifjKriwe/narrare/code-scanning/analyses?per_page=10
```
Expected: analyses for `python`, `javascript-typescript` and `actions` on the
new head. Record the analysis IDs.

- [ ] **Step 4: Commit after review**

```bash
git add .github/workflows/codeql.yml
git commit -m "ci(security): CodeQL is an explicit workflow with path filters" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

### Task 14: Scorecard

**Files:**
- Create: `.github/workflows/scorecard.yml`

**Interfaces:**
- Produces: weekly, `push: main`, `branch_protection_rule`;
  `permissions: security-events: write, id-token: write, contents: read, actions: read`;
  `ossf/scorecard-action` with `results_format: sarif`, `publish_results: true`;
  `github/codeql-action/upload-sarif`; `timeout-minutes: 15`.

- [ ] **Step 1: Write the workflow**

Pin both actions by SHA. `publish_results: true` is valid because the
repository is public.

- [ ] **Step 2: Verify**

```bash
gh workflow run scorecard.yml
gh run list --workflow scorecard.yml --limit 1
gh api repos/jmerifjKriwe/narrare/code-scanning/analyses?per_page=5
```
Expected: a green run and a SARIF analysis from Scorecard.

- [ ] **Step 3: Commit after review**

```bash
git add .github/workflows/scorecard.yml
git commit -m "ci(security): Scorecard publishes the supply-chain posture weekly" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

### Task 15: Repository settings and the nightly audit

**Files:**
- Modify: `.github/workflows/nightly.yml`

**Interfaces:**
- Produces: `sha_pinning_required: true`; `allowed_actions: selected` with
  GitHub-owned + verified + the third-party allowlist; secret scanning
  non-provider patterns and validity checks on; an `audit` job in
  `nightly.yml` running `pip-audit` and `pnpm audit --prod`.

- [ ] **Step 1: Apply the Actions settings (coordinator)**

```bash
gh api -X PUT repos/jmerifjKriwe/narrare/actions/permissions \
  -F enabled=true -f allowed_actions=selected -F sha_pinning_required=true
gh api -X PUT repos/jmerifjKriwe/narrare/actions/permissions/selected-actions \
  -F github_owned_allowed=true -F verified_allowed=true \
  -f 'patterns_allowed[]=astral-sh/*' -f 'patterns_allowed[]=pnpm/*' \
  -f 'patterns_allowed[]=extractions/*' -f 'patterns_allowed[]=gitleaks/*' \
  -f 'patterns_allowed[]=codecov/*' -f 'patterns_allowed[]=googleapis/*' \
  -f 'patterns_allowed[]=softprops/*' -f 'patterns_allowed[]=docker/*' \
  -f 'patterns_allowed[]=sigstore/*' -f 'patterns_allowed[]=ossf/*' \
  -f 'patterns_allowed[]=zizmorcore/*'
```
Read both back. If a used action is not covered, add its pattern; do not
switch back to `all`. The implementer prepares the payload; the coordinator
applies it.

- [ ] **Step 2: Enable the secret-scanning extras**

```bash
cat > /tmp/opencode/security.json <<'JSON'
{"security_and_analysis":{"secret_scanning_non_provider_patterns":{"status":"enabled"},"secret_scanning_validity_checks":{"status":"enabled"}}}
JSON
gh api -X PATCH repos/jmerifjKriwe/narrare --input /tmp/opencode/security.json
```
Read back `security_and_analysis`.

- [ ] **Step 3: Add the audit job**

In `nightly.yml`, `audit` runs after `gate` with `if: needs.gate.outputs.proceed == 'true'`:
`uv export --format requirements-txt --no-dev --output-file /tmp/requirements.txt`
then `uvx pip-audit -r /tmp/requirements.txt`; and `pnpm audit --prod --audit-level high`.
`timeout-minutes: 15`, `permissions: contents: read`. It reddens the nightly
but blocks nothing on the PR path.

- [ ] **Step 4: Commit after review**

```bash
git add .github/workflows/nightly.yml
git commit -m "ci(security): the nightly audits the lockfiles" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

---

## Phase 5 — cleanup and the map

### Task 16: `release-please.yml` only orchestrates releases

**Files:**
- Modify: `.github/workflows/release-please.yml`

- [ ] **Step 1: Delete the `publish` job**

Remove `publish:` and everything under it, from its `needs:` line to the end
of the job. Do not leave `if: false`.

- [ ] **Step 2: Fix the two stale comments**

- "the three `extra-files` entries" → four entries, naming `uv.lock`.
- Delete the "known, accepted drift" paragraph: `release-please-config.json`
  updates `uv.lock`'s project version.

- [ ] **Step 3: Verify**

Run: `zizmor .github/workflows/release-please.yml` and actionlint.
Expected: exit 0. `gh workflow view release-please.yml` shows one job.
A push to `main` still opens or updates the release PR and tags a merged one.

- [ ] **Step 4: Commit after review**

```bash
git add .github/workflows/release-please.yml
git commit -m "ci(release): release-please only orchestrates releases" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

### Task 17: Dependabot groups and cools down

**Files:**
- Modify: `.github/dependabot.yml`

**Interfaces:**
- Produces: `uv` and `npm` monthly with `minor-patch` and `major-updates`
  groups, `cooldown` `default-days: 7`, `semver-major-days: 30`,
  `open-pull-requests-limit: 5`; `github-actions` weekly with
  `actions-minor-patch` and `actions-major` groups, `cooldown`
  `default-days: 3`, `semver-major-days: 14`; no `docker` entry; no
  `rebase-strategy: disabled`; `chore` + scope commit prefixes and the
  existing labels unchanged.

- [ ] **Step 1: Remove the dead entry**

Delete the `package-ecosystem: "docker"` block whose `directory` is
`/.devcontainer`. The directory does not exist. A `devcontainers` entry
returns only with a devcontainer; a `docker` entry at `/` returns only with a
`Dockerfile`.

- [ ] **Step 2: Set the cadence and the cooldown**

`uv`/`npm`: monthly, groups as above, `cooldown: {default-days: 7,
semver-major-days: 30}`, limit 5. `github-actions`: weekly, groups as above,
`cooldown: {default-days: 3, semver-major-days: 14}`, limit 5. Delete every
`rebase-strategy: disabled` line; the default `auto` is the chosen behavior.

- [ ] **Step 3: Verify the schema**

The PR carries GitHub's `.github/dependabot.yml` validation check; it must be
green. Parse the file locally:
`python3 -c "import yaml; d=yaml.safe_load(open('.github/dependabot.yml')); print([u['package-ecosystem'] for u in d['updates']])"`
Expected: `['uv', 'npm', 'github-actions']`.

- [ ] **Step 4: Record the next scheduled behavior**

After merge, note the first Dependabot run date and the PR titles in the task
report. Expected: one grouped action PR per week, grouped code PRs monthly,
no `/web` or `/apps/api` branches.

- [ ] **Step 5: Commit after review**

```bash
git add .github/dependabot.yml
git commit -m "ci(deps): Dependabot groups and cools down instead of fanning out" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

### Task 18: Sourcery, the map, and the badges

**Files:**
- Delete: `.coderabbit.yaml`
- Create: `docs/architecture/github.md`
- Modify: `README.md`

- [ ] **Step 1: Delete the dead config**

```bash
git rm .coderabbit.yaml
```

- [ ] **Step 2: Write `docs/architecture/github.md`**

It carries: the workflow map (file → triggers → jobs → blocks merge); the
`ci-required` result table; the `affected.py` classes; the ruleset inventory
and the two bypass actors (admin kept, Dependabot removed); the repository
settings; the Sourcery dashboard state (ignore `chore: release`, path filters
`app/generated/**`, `web/lib/api/**`, `web/dist/**`, `assets/**`, `**/*.lock`,
`uv.lock`, `pnpm-lock.yaml`; drafts off; profile Balanced; base `main`;
labels empty; approval off); the CodeQL migration and its fork-PR caveat; the
`publish.yml` trigger condition.

- [ ] **Step 3: Update the README badges**

Replace the single CI badge with CI, Nightly, CodeQL and Scorecard badges,
each linked to its workflow file. Keep the existing Codecov badge.

- [ ] **Step 4: Verify**

Run: `rg -n -i "coderabbit" .github README.md docs/architecture/github.md`
Expected: no match in live config; historical mentions in
`docs/architecture/decisions/`, `docs/superpowers/plans/` and
`docs/superpowers/reports/` are out of scope and stay.
Run: `just check`.
Expected: PASS.

- [ ] **Step 5: Commit after review**

```bash
git add .coderabbit.yaml docs/architecture/github.md README.md
git commit -m "docs(ci): the GitHub surface has one map and no dead review config" \
  --trailer "Assisted-by: OpenCode (DeepSeek V4.1 Flash)"
```

---

## Final verification

- [ ] `just check`, `just test`, `just build` pass on the branch.
- [ ] `just verify` passes for the touched scope; the E2E suite that
      `affected.py` names for this branch is green.
- [ ] `zizmor .github/workflows` and actionlint exit 0.
- [ ] A draft PR shows `ci-required` as the only required check; a
      docs-only change owes no E2E; a workflow-only change owes `setup`.
- [ ] `gh api .../rulesets/18702224` read-back matches the after-JSON except
      server fields; the Dependabot bypass is gone; the admin bypass remains.
- [ ] CodeQL analyses all three languages; Scorecard SARIF arrives;
      dependency review has a red proof and a green proof.
- [ ] `.coderabbit.yaml` is gone; `docs/architecture/github.md` names the
      Sourcery dashboard state and the CodeQL fork caveat.
- [ ] `.github/dependabot.yml` lists `uv`, `npm` and `github-actions` only;
      no `docker` entry, no `rebase-strategy: disabled`, and the groups and
      cooldowns match the spec.
- [ ] The branch merges as a merge commit; every commit carries the
      `Assisted-by` trailer.
