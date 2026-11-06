# GitHub Platform Follow-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the eleven still-open findings under index #607 (#596–#606,
#610) — four mechanical fixes, four coverage fixes, three records of what GitHub
does not offer this repository — and close #607 with its last child.

**Architecture:** No new architecture. The mechanical fixes edit the composite
setup action, three reusable workflows, `dependabot.yml` (no: already fixed) and
the map. The coverage gaps widen the nightly's existing audit (no new job) and
add one monthly advisory workflow (`pins.yml`) backed by a tested `scripts/`
helper. The record-only findings correct `docs/architecture/github.md` and close
with a named re-open trigger; #604 records four proofs.

**Tech Stack:** GitHub Actions YAML, `actionlint` 1.7.12, `zizmor` 1.32.0, `gh`,
`jq`, Python 3 stdlib (3.10-compatible, run by the runner's `python3`), `uv`,
`pnpm`, PostgreSQL + pgvector.

**Design:** `docs/superpowers/specs/2026-11-05-github-followups-design.md`.

## Global Constraints

- Branch `ci/607-github-followups` (rename before the first push —
  `follow-up/` is not a conventional type). Base `narrare/main` 673306b3; the
  remote is `narrare`, not `origin`. One PR, one merge commit.
- #601 is already fixed on `main` (673306b3, closed). No task touches it beyond
  the report line.
- Conventional commits (`ci`, `docs`); no `feat`/`fix`, so no `User-visible:`
  line. Agent commits end with `--trailer "Assisted-by: OpenCode (<model>)"`.
- Nothing is pushed and no PR is opened before the wave review is green. The
  per-task commits stay local; the reviewer reads the whole branch diff before
  the push and every finding lands in its own fix commit.
- No `--no-verify`, no force push.
- Every action stays pinned by full commit SHA with a trailing release comment.
  The only new workflow reuses `actions/checkout@3d3c42e…`; no new third-party
  action.
- Top-level `permissions: {}` in every workflow; each job grants only what it
  uses; every job has `timeout-minutes`.
- `scripts/check_pins.py` is stdlib + the `gh` CLI; parse functions never touch
  the network, so the test is hermetic. It must run on the runner's `python3`
  (3.10-compatible: no `match`, no `type` statement, no 3.11+ stdlib).
- Every task appends to `docs/superpowers/reports/2026-11-05-github-followups.md`
  before its commit (probe output, run URLs, numbers).
- Locate targets by semantic name (job name, step name, regex), never by line
  number; the tree moves under a fix round.
- Local probes run against the real tree: `docker run … rhysd/actionlint:1.7.12`,
  `uvx zizmor==1.32.0 …`, `uvx pip-audit==2.10.1 …`, `pnpm audit …`.

## Review Focus

1. **A setup composite that starves a job** — `python: "false"` on a job that
   still runs a Python step. Expect: `frontend`, `build` green with no `uv`/
   Python step in the log.
2. **A widened audit that lands red** — dev CVEs with no fix, or `pnpm audit`
   reading a different tree. Expect: the pre-commit probe green on today's lock.
3. **A checker that cannot see a pin** — a regex that finds nothing and exits 0.
   Expect: every pin read exactly once (or the run fails), and
   `test_reads_every_pin_from_the_tree` covers the live tree; actionlint checks
   comment **and** digest.
4. **A digest pin on the wrong digest** — the per-platform digest instead of the
   index digest. Expect `sha256:7d0a4146…` in all four sites; services start.
5. **A record that re-opens as a surprise** — a close comment without the
   trigger, or a map sentence that still claims a PATCH would fix #596.
6. **A doc table that survives the dedup** — `ci-required` verdicts in two
   places after Task 8. Expect one table (the job comment) and one pointer.

## File Structure

**Create**
- `.github/workflows/pins.yml`
- `scripts/check_pins.py`
- `app/kernel/tests/test_check_pins.py`
- `docs/superpowers/reports/2026-11-05-github-followups.md`

**Modify**
- `.github/actions/setup/action.yml`
- `.github/workflows/ci.yml`
- `.github/workflows/_test.yml`
- `.github/workflows/_e2e.yml`
- `.github/workflows/nightly.yml`
- `docker-compose.dev.yml`
- `docs/architecture/github.md`

**Not touched:** `.github/dependabot.yml` (fixed on `main`), `pyproject.toml`,
the ruleset, repository settings beyond the #596 PATCH probe.

---

## Phase 0 — baseline

### Task 0: Rebase onto `main`, rename the branch, capture the before-state

**Files:**
- Create: `docs/superpowers/reports/2026-11-05-github-followups.md`

- [ ] **Step 1: Rebase**

```bash
git fetch narrare main
git merge --ff-only narrare/main      # the branch has no commits of its own yet
git branch -m ci/607-github-followups
git status -sb
```

Expected: HEAD is 673306b3 (or newer), branch `ci/607-github-followups`.
Re-run the merge before the push if `narrare/main` moved again.

- [ ] **Step 2: Record the baseline**

Run and paste into the report:

```bash
git status --porcelain=v1
gh run list --workflow scorecard.yml --limit 5
gh run list --workflow nightly.yml --limit 5
gh api repos/jmerifjKriwe/narrare/code-scanning/analyses \
  --jq '.[] | select(.tool.name=="Scorecard") | {ref, category, created_at}'
gh api repos/jmerifjKriwe/narrare --jq '.security_and_analysis'
rg -c "zizmor: ignore\\[self-repository\\]" .github/workflows
rg -c "1\\.7\\.7" .github/workflows docs/architecture/github.md
```

Expected: three green Scorecard main runs; three SARIF categories; no completed
nightly; both secret-scanning features `disabled`; 14 suppressions; 16 `1.7.7`
mentions.

- [ ] **Step 3: Record the cost baseline**

From `main`'s latest CI run, record the `frontend` and `build` job durations.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/reports/2026-11-05-github-followups.md
git commit -m "docs(ci): open the follow-up wave's report" \
  --trailer "Assisted-by: OpenCode (<model>)"
```

---

## Phase 1 — the mechanical fixes

### Task 1: `python: false` for the web jobs (#606)

**Files:**
- Modify: `.github/actions/setup/action.yml`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/nightly.yml`
- Modify: `docs/architecture/github.md`
- Modify: `docs/superpowers/reports/2026-11-05-github-followups.md`

**Interfaces:**
- Produces: input `python` (default `"true"`) on the composite; `node` and
  `python` are independent switches. `frontend` and `build` pass
  `python: "false"` in both callers.
- `extractions/setup-just` stays ungated: `frontend`, `build`, `lint-types`,
  `tests` and `e2e` run `just` recipes (the nightly `audit` job does not, and
  pays ~1 s for the install — accepted, one composite for every job).

- [ ] **Step 1: Add the input**

In `action.yml`, after `node`, add a `python` input: "Install uv, Python and run
the locked uv sync. Set `false` for jobs that need only the JavaScript
toolchain." Default `"true"`.

- [ ] **Step 2: Gate the three Python steps**

`astral-sh/setup-uv`, `actions/setup-python` and the `uv sync --locked` step get
`if: inputs.python != 'false'`. Update the composite's `description:` to name
both switches.

- [ ] **Step 3: Set it at the four call sites**

`frontend` and `build` in `ci.yml`, and `frontend` and `build` in `nightly.yml`:

```yaml
      - uses: ./.github/actions/setup # zizmor: ignore[self-repository]
        with:
          python: "false"
```

- [ ] **Step 4: Verify**

Run: `docker run --rm -v "$PWD:/repo:ro" -w /repo rhysd/actionlint:1.7.12 -color`
and `uvx zizmor==1.32.0 .github/workflows .github/actions`
Expected: exit 0 each. On the PR run, `frontend` and `build` logs contain no
`Sync Python dependencies` step; record their durations against Task 0.

- [ ] **Step 5: Map and report**

The map's composite paragraph: it carries uv, Python, the locked sync, pnpm,
Node and just, "with `python: false` and `node: false` for the jobs that need
only the other half".

- [ ] **Step 6: Commit**

```bash
git add .github/actions/setup/action.yml .github/workflows/ci.yml \
        .github/workflows/nightly.yml docs/architecture/github.md \
        docs/superpowers/reports/2026-11-05-github-followups.md
git commit -m "ci(setup): the web jobs stop syncing Python" \
  --trailer "Assisted-by: OpenCode (<model>)"
```

Body: the four call sites, the measured durations, `Closes #606`.

### Task 2: The Playwright cache survives a Python bump (#599)

**Files:**
- Modify: `.github/workflows/_e2e.yml`
- Modify: `docs/superpowers/reports/2026-11-05-github-followups.md`

- [ ] **Step 1: Add the fallback**

```yaml
          key: ${{ runner.os }}-playwright-${{ hashFiles('uv.lock') }}
          restore-keys: ${{ runner.os }}-playwright-
```

- [ ] **Step 2: Correct the comment**

The current comment says a stale browser "can never match a new lock". With a
restore key that is false: a restore may hand back the previous browser, and
`uv run playwright install --with-deps chromium` then adds the browser the new
lock names. Say that, and why the key still turns: a Playwright bump writes a
fresh cache under a new key instead of overwriting the old one.

- [ ] **Step 3: Verify**

`docker run --rm -v "$PWD:/repo:ro" -w /repo rhysd/actionlint:1.7.12 -color` →
exit 0. On the PR's e2e run, read the cache step: exact-key miss,
`Cache restored from key: Linux-playwright-…`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/_e2e.yml docs/superpowers/reports/2026-11-05-github-followups.md
git commit -m "ci(e2e): a Python bump stops re-downloading chromium" \
  --trailer "Assisted-by: OpenCode (<model>)"
```

Body ends with `Closes #599`.

### Task 3: The Postgres image is a digest (#603)

**Files:**
- Modify: `.github/workflows/_test.yml`
- Modify: `.github/workflows/_e2e.yml`
- Modify: `docker-compose.dev.yml`
- Modify: `docs/architecture/github.md`
- Modify: `docs/superpowers/reports/2026-11-05-github-followups.md`

**Interfaces:**
- Produces: `pgvector/pgvector@sha256:7d0a41464797aeb9862dfdc0bbf1526b82cfd324cdd8036df19e3545f4a9ccb8`
  with `# pg17` in all four service blocks.

- [ ] **Step 1: Re-verify the digest**

`docker buildx imagetools inspect pgvector/pgvector:pg17` → `Digest:
sha256:7d0a4146…`. If it moved, record the new digest and use it; the comment
keeps `# pg17`.

- [ ] **Step 2: Pin the four sites**

`image: pgvector/pgvector@sha256:… # pg17 — a tag is a mutable ref; the digest is
the contract`. Keep `docker-compose.dev.yml` valid.

- [ ] **Step 3: Prove the service still starts**

`just dev-services` → both services healthy; then `just dev-services-stop`.

- [ ] **Step 4: Map and report**

The map's reusable-workflow sentence: "the Postgres service (pinned by digest,
`pg17`) and the Playwright cache live inside the reusables". Record the digest
and the tag's `last_updated` (2026-10-31).

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/_test.yml .github/workflows/_e2e.yml \
        docker-compose.dev.yml docs/architecture/github.md \
        docs/superpowers/reports/2026-11-05-github-followups.md
git commit -m "ci(deps): the Postgres image is a digest, not a tag" \
  --trailer "Assisted-by: OpenCode (<model>)"
```

Body ends with `Closes #603`.

### Task 4: The PGDG key fetch survives a transient TLS EOF (#610)

**Files:**
- Modify: `.github/workflows/_test.yml`
- Modify: `docs/superpowers/reports/2026-11-05-github-followups.md`

- [ ] **Step 1: Verify the codename premise**

```bash
for c in noble resolute plucky questing; do
  printf '%s ' "$c"
  curl -s -o /dev/null -w '%{http_code}\n' \
    "https://apt.postgresql.org/pub/repos/apt/dists/${c}-pgdg/Release"
done
```

Expected (probed 2026-11-05): noble 200, resolute 200, plucky 404, questing 404.
Record it: `ubuntu-26.04` is `resolute`, and the repo exists — the failure was
transport, not a missing distribution.

- [ ] **Step 2: Add the retry**

On the `curl -o …/apt.postgresql.org.asc --fail …` line add
`--retry 5 --retry-all-errors --retry-delay 2`. Keep `--fail` (a 404 must still
fail). Say in the comment why: run 42088177589 died on
`curl: (55) OpenSSL SSL_read: unexpected eof while reading` and passed on rerun.

- [ ] **Step 3: Verify**

`docker run --rm -v "$PWD:/repo:ro" -w /repo rhysd/actionlint:1.7.12 -color` →
exit 0. The PR's `tests / tests` job green.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/_test.yml docs/superpowers/reports/2026-11-05-github-followups.md
git commit -m "ci(tests): retry the PGDG key fetch instead of reddening on an EOF" \
  --trailer "Assisted-by: OpenCode (<model>)"
```

Body ends with `Closes #610`.

---

## Phase 2 — the coverage gaps

### Task 5: The nightly audits dev dependencies too (#597)

**Files:**
- Modify: `.github/workflows/nightly.yml`
- Modify: `.github/workflows/ci.yml` (the `dependency-review` comment only)
- Modify: `docs/architecture/github.md`
- Modify: `docs/superpowers/reports/2026-11-05-github-followups.md`

**Interfaces:**
- Produces: the `audit` job exporting the full locked set (`uv export --locked …`
  without `--no-dev`) and `pnpm audit --audit-level high` without `--prod`; no
  second job.

- [ ] **Step 1: Prove the widening green on today's lock**

```bash
uv export --locked --format requirements-txt --output-file /tmp/req-all.txt
uvx pip-audit==2.10.1 --strict -r /tmp/req-all.txt
pnpm audit --audit-level high
```

Expected (probed 2026-11-05): 1030 requirements; "No known vulnerabilities
found" twice. Paste both into the report. A red here stops the task.

- [ ] **Step 2: Widen the job**

Drop `--no-dev` from the export and `--prod` from the audit. Rewrite the job
comment: runtime and dev are both judged, a CVE published after merge is the
reason the job exists, and the package name in the report says which side a
finding is on. Update the `uv export` step name/comment accordingly.

- [ ] **Step 3: Fix the comment that now lies**

`ci.yml`'s `dependency-review` step comment says dev deps are "otherwise
uncovered: the nightly audit skips dev deps". Replace with: the nightly covers
the whole lockfile after merge; the review judges a change earlier, before it
lands. Keep `fail-on-scopes: runtime, development`.

- [ ] **Step 4: Verify**

The two commands from Step 1 (same output) plus actionlint → exit 0.

- [ ] **Step 5: Map**

The audit paragraph: dev dependencies *are* covered now; delete "Dev
dependencies are not covered here" and the claim that neither surface is
unjudged, and keep the "reddens the nightly but blocks no PR" sentence.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/nightly.yml .github/workflows/ci.yml \
        docs/architecture/github.md docs/superpowers/reports/2026-11-05-github-followups.md
git commit -m "ci(security): the nightly audits dev dependencies too" \
  --trailer "Assisted-by: OpenCode (<model>)"
```

Body ends with `Closes #597`.

### Task 6: The two stale pins, landed green

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/nightly.yml`
- Modify: `.github/workflows/_lint.yml`
- Modify: `.github/workflows/_test.yml`
- Modify: `.github/workflows/_e2e.yml`
- Modify: `docs/architecture/github.md`
- Modify: `docs/superpowers/reports/2026-11-05-github-followups.md`

**Interfaces:**
- Produces: actionlint pinned at 1.7.12 by index digest
  (`sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667`,
  re-verified at implementation time) and zizmor `version: 1.32.0`; all 16
  `1.7.7` mentions become `1.7.12`; the 14 `zizmor:
  ignore[self-repository]` comments stay (no release supports `$/`).

- [ ] **Step 1: Re-verify the digest and both runs**

```bash
docker buildx imagetools inspect rhysd/actionlint:1.7.12   # Digest: sha256:b1934ee5…
curl -s https://registry.hub.docker.com/v2/repositories/rhysd/actionlint/tags/1.7.12 | jq .digest
docker run --rm -v "$PWD:/repo:ro" -w /repo rhysd/actionlint:1.7.12 -color
uvx zizmor==1.32.0 .github/workflows .github/actions
```

Expected (probed 2026-11-05): both digests agree; both probes exit 0, no
findings.

- [ ] **Step 2: Bump both pins**

In `workflow-lint`: the actionlint `docker run` digest and its trailing
`# rhysd/actionlint:1.7.12`; zizmor's `version: 1.32.0`. Update the two "the bump
is manual" comments to name the monthly check that now reports them.

- [ ] **Step 3: Update every version mention**

`rg -l "1\.7\.7" .github/workflows docs/architecture/github.md` — 16 mentions in
five workflow files and the map. All become `1.7.12`, wording intact. Do not
touch the 14 `zizmor: ignore[self-repository]` comments themselves.

- [ ] **Step 4: Map**

Pin hygiene: actionlint 1.7.12 and zizmor 1.32.0, both followed by the monthly
check. The `$`/ shape sentence: "actionlint 1.7.12, the current release
(2026-11-05), still rejects `$/`; rhysd/actionlint#732 is open."

- [ ] **Step 5: Verify**

The two probes from Step 1 plus `rg -c "1\.7\.7" …` → no match.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml .github/workflows/nightly.yml \
        .github/workflows/_lint.yml .github/workflows/_test.yml \
        .github/workflows/_e2e.yml docs/architecture/github.md \
        docs/superpowers/reports/2026-11-05-github-followups.md
git commit -m "ci(security): actionlint 1.7.12 and zizmor 1.32.0" \
  --trailer "Assisted-by: OpenCode (<model>)"
```

### Task 7: A monthly check for the pins Dependabot cannot follow (#598)

**Files:**
- Create: `scripts/check_pins.py`
- Create: `app/kernel/tests/test_check_pins.py`
- Create: `.github/workflows/pins.yml`
- Modify: `docs/architecture/github.md`
- Modify: `docs/superpowers/reports/2026-11-05-github-followups.md`

**Interfaces:**
- Produces: `check_pins.read_pins(root) -> list[PinState]`,
  `check_pins.latest(pin) -> str`, `check_pins.behind(state, latest) -> bool`,
  `check_pins.report(states, latest) -> str`; CLI `--json` (prints
  `{"behind": [names], "report": "<markdown>"}`), `--tree` (no network: read
  every pin or exit 2), `--markdown` (network, human output).
- Five pins: `actionlint` (version comment **and** Docker Hub digest in
  `ci.yml`), `zizmor` (version input in `ci.yml`), `pip-audit` (`nightly.yml`),
  `codecov-cli` (`_test.yml`, two occurrences that must agree), `pgvector`
  (digest in `_test.yml`, `_e2e.yml`, `docker-compose.dev.yml` ×2, all equal).

- [ ] **Step 1: Write the failing test first**

`app/kernel/tests/test_check_pins.py`, importing `from scripts import check_pins`
the way `test_affected.py` does. Five tests, no network:
1. `test_reads_every_pin_from_the_tree` — exactly the five names, each with a
   non-empty current value; the two Codecov occurrences and the four pgvector
   digests agree.
2. `test_missing_pin_is_an_error` — a text without the pattern raises
   `check_pins.PinError` naming file and pin.
3. `test_behind_ignores_the_v_prefix` — `1.30.1`/`v1.32.0` behind;
   `v11.3.2`/`11.3.2` not.
4. `test_tag_moved` — a digest state whose latest digest differs is behind, with
   the tag-moved wording.
5. `test_report_names_only_the_behind_pins` — a mixed set reports the one stale
   pin and "current" for the rest.

Run: `just test-file app/kernel/tests/test_check_pins.py`
Expected: FAIL — no module named `scripts.check_pins`.

- [ ] **Step 2: Write the reader**

`scripts/check_pins.py`, stdlib only (`argparse`, `dataclasses`, `json`,
`pathlib`, `re`, `subprocess`, `urllib.request`), 3.10-compatible. Module
docstring: why it exists, and that a pin it cannot read is an error, never a
pass. A `Pin` dataclass carries `name`, `file`, `pattern`, `occurrences`
(1 or "all equal"), `upstream` (`("github", "rhysd/actionlint")` or
`("docker", "pgvector/pgvector", "pg17")`). `read_pins` uses `Path(root)` and
`re.findall`; a count mismatch raises `PinError` naming file, pin and
expected/actual counts. For actionlint, capture both the digest and the version
comment and treat a divergence between them as a finding.

- [ ] **Step 3: Write the lookups and the report**

`latest()` shells out to `gh api repos/<repo>/releases/latest --jq .tag_name`
(fixed argv, `subprocess.run`, no shell) and `urllib.request.urlopen` for
`https://registry.hub.docker.com/v2/repositories/<image>/tags/<tag>` → `.digest`.
`compare` splits on `.` and compares integer tuples after stripping `v`; a
digest compares by equality. The markdown report is one table:
`| pin | current | latest | state | file |`. `--json` prints
`{"behind": [...], "report": "..."}`; `--tree` skips the network and exits 0
when every pin parses; a lookup or parse failure exits 2 with the reason on
stderr.

- [ ] **Step 4: Prove the reader red and green**

```bash
uv run python -m scripts.check_pins --tree        # exit 0
uv run python -m scripts.check_pins --markdown    # all current after Task 6
```

Red proof: temporarily set `version: 1.30.1` in `ci.yml`, run `--markdown`,
expect "zizmor … behind"; revert. Record both outputs.

- [ ] **Step 5: Write the workflow**

`.github/workflows/pins.yml`: `name: Tool pins`; `on:` `schedule`
(`23 8 1 * *`, monthly) and `workflow_dispatch`; `permissions: {}`;
`concurrency: {group: tool-pins, cancel-in-progress: false}`; one job `check`
(`permissions: {contents: read, issues: write}`, `timeout-minutes: 10`):
checkout pinned (`persist-credentials: false`), then
`python3 scripts/check_pins.py --json > /tmp/pins.json` under
`GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` and `GH_REPO: ${{ github.repository }}`,
then a step mirroring `nightly-result`'s issue handling: ensure the
`ci/tool-pins` label exists (description "A CI tool pin is behind its upstream",
colour `D93F0B`); read `jq -r '.behind | length' /tmp/pins.json`; when non-zero,
create the issue or comment the report on the one open one; when zero, close the
open issue with a one-line "all pins current" comment. `set -euo pipefail`: a
failed check reddens the run and never opens a green-looking issue.

- [ ] **Step 6: Verify**

`just test-file app/kernel/tests/test_check_pins.py` → PASS.
`uv run pyright scripts/check_pins.py` → 0 errors (explicit path; the config's
`include` stays `["app"]`).
`uv run ruff check scripts app` → clean.
actionlint + zizmor → exit 0.
Dispatch on the branch (`gh workflow run pins.yml --ref <branch>`) → green, no
issue opened (Task 6 already bumped both pins).

- [ ] **Step 7: Map and report**

Workflow map: add the `pins.yml` row (`schedule` monthly, `workflow_dispatch`;
`check`; blocks nothing). Pin hygiene: the five pins are read by
`scripts/check_pins.py` and reported monthly, so the manual list is no longer
silent; Dependabot still follows the action SHAs.

- [ ] **Step 8: Commit**

```bash
git add scripts/check_pins.py app/kernel/tests/test_check_pins.py \
        .github/workflows/pins.yml docs/architecture/github.md \
        docs/superpowers/reports/2026-11-05-github-followups.md
git commit -m "ci(deps): a monthly check for the pins Dependabot cannot follow" \
  --trailer "Assisted-by: OpenCode (<model>)"
```

Body ends with `Closes #598`.

---

## Phase 3 — the records

### Task 8: One copy of the `ci-required` verdicts (#605)

**Files:**
- Modify: `docs/architecture/github.md`
- Modify: `docs/superpowers/reports/2026-11-05-github-followups.md`

- [ ] **Step 1: Replace the table with a pointer**

Delete the ten-row table under "`ci-required` — the required-check aggregator".
Keep the paragraph above it and end with: "The verdicts — which skip is owed,
which result is red — are stated once, in the `ci-required` job comment in
`ci.yml`; this page does not repeat them."

- [ ] **Step 2: Check the survivor is complete**

The job comment must still say: a skipped required check passes; `changes` red
or an empty handoff is red; `[]` with a skipped matrix is green; `[]` with
anything else is red; non-empty with anything but success is red; the five
blocking jobs have no legitimate skip; dependency-review is owed on a PR and may
skip elsewhere. Add nothing new: if a verdict is missing, the code is wrong, not
the doc.

- [ ] **Step 3: Verify**

`rg -n "legitimate skip|owed skip" docs/architecture/github.md
.github/workflows/ci.yml` → matches only in `ci.yml` after the pointer sentence.

- [ ] **Step 4: Commit**

```bash
git add docs/architecture/github.md docs/superpowers/reports/2026-11-05-github-followups.md
git commit -m "docs(ci): the required-check verdicts have one copy" \
  --trailer "Assisted-by: OpenCode (<model>)"
```

Body ends with `Closes #605`.

### Task 9: Record the three gaps GitHub still owns (#596, #600, #602)

**Files:**
- Modify: `docs/architecture/github.md`
- Modify: `docs/superpowers/reports/2026-11-05-github-followups.md`

- [ ] **Step 1: Probe the settings PATCH (coordinator)**

```bash
gh api -X PATCH repos/jmerifjKriwe/narrare --input - <<'JSON'
{"security_and_analysis":{"secret_scanning_non_provider_patterns":{"status":"enabled"},"secret_scanning_validity_checks":{"status":"enabled"}}}
JSON
gh api repos/jmerifjKriwe/narrare --jq '.security_and_analysis'
```

Expected: both still `disabled`. Record the response verbatim. If they turn on,
#596 is fixed instead of recorded: keep the row truthful, close #596 as fixed
with the read-back, and skip Step 2.

- [ ] **Step 2: Rewrite the settings row**

Replace "the settings PATCH that turns these on did not take … Re-applying the
settings PATCH is the fix" with: the repository is public and user-owned;
non-provider patterns and validity checks are Secret Protection features GitHub
offers to organisation-owned repositories on Team/Enterprise, so no repository
PATCH can enable them here. Trigger: the repository moves under an organisation
with Secret Protection, or GitHub makes the features repository-scoped.

- [ ] **Step 3: Add the scorecard trigger**

Scorecard blind spot: end with "Re-open the finding when GitHub adds a ruleset
event, or when `main` moves back to classic protection." The `$`/ sentence was
already brought to 1.7.12 in Task 6 — do not add a second version line.

- [ ] **Step 4: Verify**

`rg -n "Re-applying the settings PATCH|semver-major|not covered here"
docs/architecture/github.md` → no match.
`rg -n "organization-owned|Organization-owned|ruleset event"
docs/architecture/github.md` → the two sentences.

- [ ] **Step 5: Commit**

```bash
git add docs/architecture/github.md docs/superpowers/reports/2026-11-05-github-followups.md
git commit -m "docs(ci): record the three gaps GitHub still owns" \
  --trailer "Assisted-by: OpenCode (<model>)"
```

Body ends with `Closes #596`, `Closes #600`, `Closes #602`, quoting each trigger.

- [ ] **Step 6: Close the three issues with their triggers**

`gh issue close <n> --comment "<the trigger sentence from the map>"` for #596,
#600, #602.

---

## Phase 4 — the proofs

### Task 10: The four proofs (#604)

**Files:**
- None. This task produces run URLs and issue comments, not a diff.

- [ ] **Step 1: Scorecard (already proved)**

Record: three green `main` pushes (42080606005, 42086972305, 42088177236);
code scanning holds three `Scorecard` analyses on `refs/heads/main`
(`supply-chain/local`, `supply-chain/branch-protection`,
`supply-chain/online-scm`).

- [ ] **Step 2: HARNESS-only PR**

Branch off `main`, change one comment line under `.github/workflows/_test.yml`,
open a PR. Expected: the `changes` notice says `capabilities=["settings"]` and
`e2e-suites` runs exactly `settings`. Record the URL; close the PR unmerged and
delete the branch.

- [ ] **Step 3: Dependency-review PR**

Branch off `main`, `pnpm add -w lodash@4.17.20` (GHSA-35jh-r3h4-6jhm,
CVE-2021-23337, high), open a PR. Expected: `dependency-review` fails on the
high advisory, `ci-required` red. Record the URL and the failing line; close the
PR, delete the branch. Confirm no lockfile change reaches `main`.

- [ ] **Step 4: Manual nightly dispatch (coordinator, after merge)**

`gh workflow run nightly.yml --ref main`; read the run: `gate` proceeds without
a skip, jobs green, no `ci/nightly` issue opened. Record the URL.

- [ ] **Step 5: Record and close**

Append all four to the report (the dispatch may be recorded in #604 after
merge). Comment on #604 with the four URLs, then `gh issue close 604`.

---

## Final verification

- [ ] `just check` green.
- [ ] `just test` green, including `app/kernel/tests/test_check_pins.py`.
- [ ] `just test-frontend` and `just build` green.
- [ ] `uv run python -m scripts.check_pins --tree` exit 0; `--markdown` all
      current.
- [ ] `uv run pyright scripts/check_pins.py` 0 errors; `uv run ruff check app
      scripts` clean.
- [ ] `docker run … rhysd/actionlint:1.7.12 -color` and
      `uvx zizmor==1.32.0 .github/workflows .github/actions` both exit 0.
- [ ] The PR's `changes` job resolves every suite (the kernel test is a `SHARED`
      surface) and `ci-required` is green; record the matrix.
- [ ] The HARNESS PR owed `settings` alone; the dependency-review PR reddened
      `dependency-review` and `ci-required`.
- [ ] `docs/architecture/github.md` has one copy of the verdicts, the real
      reason for #596, both re-open triggers, and no "inert" cooldown clause.
- [ ] `docs/superpowers/follow-ups.md` still lists #607 as the wave's index; no
      row is added or removed.
- [ ] Every commit carries the `Assisted-by` trailer; the branch merges as a
      merge commit.
- [ ] `gh issue list --label follow-up --state open --limit 300` shows no
      `#596|#597|#598|#599|#600|#602|#603|#604|#605|#606|#610`; then
      `gh issue close 607 --comment "All children closed."` with the merge
      commit.
