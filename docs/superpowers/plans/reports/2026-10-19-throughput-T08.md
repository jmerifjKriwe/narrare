# Throughput T8 — Push-tier the two whole-project hooks, add `verify-slice`

- **Date:** 2026-10-20
- **Branch:** `brave-egret`
- **Base commit:** `d8a844c3` (`ci: gate the provider catalog at commit, local and CI surfaces (throughput T7)`)
- **Status:** implemented, verified, **not committed** (no git writes per task constraints)
- **Files authored:**
  - `.pre-commit-config.yaml` (two hooks moved to `pre-push`, comments updated)
  - `justfile` (new `verify-slice` recipe after `verify-quick`; `verify` / `verify-quick` untouched)
  - `docs/development/pre-commit-gate-tiers.md` (new tiering document)
  - this report

## 1. Baseline (bounded with `timeout 600`)

Both hooks were measured at the **pre-commit** stage with `--all-files`, exactly as
they behaved before the change (`/usr/bin/time`, wall clock).

| Hook | Command | Result | Wall clock |
|---|---|---|---|
| `openapi-regenerate` | `pre-commit run openapi-regenerate --hook-stage pre-commit --all-files` | Passed, exit 0 | **6.39 s** |
| `typecheck-frontend` | `pre-commit run typecheck-frontend --hook-stage pre-commit --all-files` | Passed, exit 0 | **1.47 s** (warm `tsconfig.tsbuildinfo`) |
| `typecheck-frontend` (cold) | same, after removing `packages/web/tsconfig.tsbuildinfo` | Passed, exit 0 | **4.23 s** |

Neither run hit the 600 s bound, so neither is reported as `>600s`. Raw:

```text
OpenAPI Spec (auto-regenerate)...........................................Passed
ELAPSED=6.39 s EXIT=0

TypeScript Check (Frontend)..............................................Passed
ELAPSED=1.47 s EXIT=0

TypeScript Check (Frontend)..............................................Passed
ELAPSED=4.23 s EXIT=0
```

Notes:

- The cold measurement removed and restored the git-ignored `tsconfig.tsbuildinfo`
  only (build artifact, no repository change). `packages/web/tsconfig.json` sets
  `"incremental": true`, which explains the warm/cold gap.
- The brief's premise ("minutes for a one-file change") did **not** reproduce on
  this machine for these two hooks. The justification that survives measurement is
  structural: both hooks inspect the whole project regardless of the changed file
  set, so their cost does not shrink with the change. The report states the numbers
  as measured rather than asserting a figure that was not observed.
- `openapi-regenerate` rewrites `docs/reference/openapi.json`; its SHA-256 was
  unchanged by the baseline and proof runs (`sha256sum -c` → OK).

## 2. Stage changes

`openapi-regenerate` previously had **no `stages` key** (unrestricted: all stages).
It now declares `stages: [pre-push]`. `typecheck-frontend` changed from
`stages: [pre-commit]` to `stages: [pre-push]`. No `entry`, `files`, `always_run`,
`types`, `types_or`, `id`, or `name` was touched.

The OpenAPI comment also corrected the stale artifact path (`docs/openapi.json` →
`docs/reference/openapi.json`, the path the exporter actually writes) while adding
the push-tier rationale and the CI authority. The TypeScript comment replaced
"consider moving … if slow" with the push-tier rationale and the CI authority.

```diff
-      # OpenAPI spec auto-regeneration — mutates docs/openapi.json when API surface changes
-      # Uses --no-sync to rely on the already-synced venv (deterministic-venv contract;
-      # see ci.yml architecture job). Run from repo root so the script path is canonical.
+      # OpenAPI spec auto-regeneration — mutates docs/reference/openapi.json when
+      # the API surface changes. PUSH-TIERED (throughput T8): the export rewrites
+      # the whole spec regardless of which files changed, so at commit time a
+      # one-file edit paid for a whole-project export. CI remains the authority:
+      # the architecture job runs `scripts/export_openapi.py --check` and fails on
+      # drift. Uses --no-sync to rely on the already-synced venv (deterministic-venv
+      # contract; see ci.yml architecture job). Run from repo root so the script
+      # path is canonical.
       - id: openapi-regenerate
         name: OpenAPI Spec (auto-regenerate)
         entry: uv run --no-sync python scripts/export_openapi.py
         language: system
         pass_filenames: false
         files: ^(apps/api/|packages/core/)
+        stages: [pre-push]

-      # TypeScript type check — consider moving to stages: [pre-push] or CI-only if slow
+      # TypeScript type check — PUSH-TIERED (throughput T8): `tsc --noEmit` checks
+      # the whole packages/web project on every run, so at commit time a one-file
+      # change paid for a whole-project typecheck. CI remains the authority: the
+      # frontend job runs the project's TypeScript step on every push/PR. The
+      # scoped, commit-cheap frontend check (Biome) is `just verify-slice`.
       - id: typecheck-frontend
         name: TypeScript Check (Frontend)
         entry: bash -c 'cd packages/web && npx tsc --noEmit'
         language: system
         types: [tsx]
         pass_filenames: false
         always_run: true
-        stages: [pre-commit]
+        stages: [pre-push]
```

## 3. Hook-stage proofs (both directions)

Pre-commit stage — the hooks are gone:

```text
$ pre-commit run typecheck-frontend --hook-stage pre-commit --all-files
No hook with id `typecheck-frontend` in stage `pre-commit`
EXIT=1

$ pre-commit run openapi-regenerate --hook-stage pre-commit --all-files
No hook with id `openapi-regenerate` in stage `pre-commit`
EXIT=1
```

Pre-push stage — the hooks run (bounded with `timeout 900`):

```text
$ pre-commit run typecheck-frontend --hook-stage pre-push --all-files
TypeScript Check (Frontend)..............................................Passed
ELAPSED=2.34 s EXIT=0

$ pre-commit run openapi-regenerate --hook-stage pre-push --all-files
OpenAPI Spec (auto-regenerate)...........................................Passed
ELAPSED=6.88 s EXIT=0
```

The move is proven in both directions.

## 4. Stage census (derived, not copied)

Method (also recorded in the document):

- Parse `.pre-commit-config.yaml`; count each hook once per **explicitly declared**
  stage.
- A hook with no `stages` key inherits `default_stages`. This config sets no
  `default_stages`, and pre-commit's built-in default (verified in the installed
  pre-commit 4.6.0 source: `StagesMigration('default_stages', STAGES)` in
  `clientlib.py`, and `if not ret['stages']: ret['stages'] =
  root_config['default_stages']` in `repository.py`) is **all stages**. Such hooks
  are therefore counted as **unrestricted**, not assigned to one stage.
- "Reach" rows = explicit stage hooks + unrestricted hooks, i.e. what actually
  runs on `git commit` / `git push`.
- Before = `git show HEAD:.pre-commit-config.yaml`; after = working tree.

| Effective stage | Before | After |
|---|---:|---:|
| `pre-commit` (explicit) | 22 | 21 |
| `pre-push` (explicit) | 3 | 5 |
| `manual` (explicit) | 1 | 1 |
| `commit-msg` (explicit) | 1 | 1 |
| unrestricted (no `stages` key) | 15 | 14 |
| **hooks defined** | **42** | **42** |
| runs at `git commit` (explicit + unrestricted) | 37 | 35 |
| runs at `git push` (explicit + unrestricted) | 18 | 19 |

Unrestricted hook ids **before** (15): `version-consistency`, `openapi-regenerate`,
`adr-naming`, `doc-drift`, `ruff-lint`, `ruff-format`, `biome-frontend`,
`validate-i18n`, `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`,
`check-toml`, `check-json`, `check-merge-conflict`, `check-added-large-files`.
**After** (14): the same list without `openapi-regenerate`.

The brief's `36 / 3 / 1 / 1` was not copied; the derived numbers are above. The
difference is **not** the treatment of the no-`stages` hooks — both counts use
explicit + unrestricted identically. The brief's `36` is the commit-reach of the
tree the brief was written against (`6ea06114`): 41 hooks, 21 explicit `pre-commit`
+ 15 unrestricted = 36. The "before" column above is `d8a844c3`, i.e. **after T7
added `provider-catalog-check`**: 42 hooks, 22 + 15 = 37. The delta is T7's hook,
and the review round that produced this paragraph is what corrected the
attribution (review finding F5).

## 5. `verify-slice`

Added to the `justfile` immediately after `verify-quick`, variadic `+paths`,
bash shebang script. Final implementation:

```make
verify-slice +paths:
    #!/usr/bin/env bash
    set -euo pipefail
    py=()
    tests=()
    web=()
    for p in {{paths}}; do
        case "$p" in
            packages/web|packages/web/) web+=("packages/web/.") ;;
            packages/web/*) web+=("$p") ;;
            tests|tests/*|./tests|./tests/*) py+=("$p"); tests+=("$p") ;;
            *) py+=("$p") ;;
        esac
    done
    if [ "${#py[@]}" -gt 0 ]; then
        just lint-file "${py[@]}"
        just typecheck-file "${py[@]}"
    fi
    if [ "${#tests[@]}" -gt 0 ]; then
        just test-file "${tests[@]}"
    fi
    if [ "${#web[@]}" -gt 0 ]; then
        cd packages/web && npx biome check "${web[@]/#packages\/web\//}"
    fi
```

### Deviation from the brief's literal block — and why

The brief's literal block calls `lint-file`, `typecheck-file`, and `test-file` on
**every** path. That cannot satisfy the brief's own Step 6 for either example:

- `just lint-file packages/web/lib/providers.ts` → ruff parses TypeScript as Python:
  `Found 61 errors` / recipe exit 1.
- `just typecheck-file packages/web/lib/providers.ts` → pyright parses it as Python:
  `49 errors, 0 warnings, 0 informations` / exit 1.
- `just test-file packages/core/narrare_core/llm/model_listing.py` → pytest collects
  a source module: `collected 0 items` / `no tests ran in 2.25s` / exit 5.

So the recipe routes by path kind: Python paths get `lint-file` → `typecheck-file`;
only paths under `tests/` additionally go to `test-file`; paths under
`packages/web/` get scoped Biome instead of the Python tools. The lint/typecheck/
biome ordering is preserved; "matching pytest files" means the test paths in the
slice (a source module has no pytest target). `lint-file`, `typecheck-file`, and
`test-file` are all variadic and accept multiple paths — verified by the mixed run.

### Runs

Python source path (GREEN):

```text
$ just verify-slice packages/core/narrare_core/llm/model_listing.py
uv run --all-packages ruff check packages/core/narrare_core/llm/model_listing.py
All checks passed!
uv run --all-packages ruff format --check packages/core/narrare_core/llm/model_listing.py
1 file already formatted
0 errors, 0 warnings, 0 informations
```

`typecheck-file` produced no findings (pyright summary `0 errors, 0 warnings, 0
informations`). Pytest is correctly skipped for a source path.

Web path (GREEN, scoped biome line):

```text
$ just verify-slice packages/web/lib/providers.ts
Checked 1 file in 5ms. No fixes applied.
```

Mixed multi-path run (GREEN), proving variadic handling and test routing:

```text
$ just verify-slice tests/unit/core/llm/test_model_listing.py packages/web/lib/providers.ts
...
============================== 21 passed in 2.74s ==============================
Checked 1 file in 5ms. No fixes applied.
```

## 6. Gates

### `just check-architecture` — GREEN (exit 0)

```text
Frontend RULE-04 file-size check
====================================
✅ All TS/TSX files are within hard limits
Frontend file-size ratchet: 0 current, 0 baseline, 0 new, 0 resolved
RESULT: Frontend file-size debt did not grow
```

(Full log: 45 services checked, 0 missing test files, 0 low coverage.)

### `just verify-quick` — GREEN (exit 0, 393.77 s total)

```text
================= 14132 passed, 3 skipped in 196.53s (0:03:16) =================
 Test Files  461 passed (461)
      Tests  3932 passed (3932)
   Duration  193.61s (environment 38%, setup 27%, tests 15%, import 15%, transform 4%, worker 1%)
ELAPSED=393.77 s EXIT=0
```

### `just --show verify` — unchanged

```text
$ just --show verify
# `verify-quick` (below) is the fast variant: unit + frontend tests only.
verify: check test-all
```

The recipe line is exactly `verify: check test-all`. (`just --show` also prints the
attached doc-comment line; the recipe itself was not edited.)

### `pre-commit run --files .pre-commit-config.yaml justfile docs/development/pre-commit-gate-tiers.md` — GREEN (exit 0, 11.31 s)

```text
Architecture Constraints.............................................................Passed
...
Documentation Drift (just commands + ADR + spec + agent names).......................Passed
...
trim trailing whitespace.............................................................Passed
fix end of files.....................................................................Passed
check yaml...........................................................................Passed
check for merge conflicts............................................................Passed
check for added large files..........................................................Passed
ELAPSED=11.31 s EXIT=0
```

Notably, neither moved hook appears in the commit-stage list any more; the push-only
hooks (`pyright`, `pyright-tests`, `bandit`) remain absent from the commit run by
design.

### `pre-commit run --all-files`

Withdrawn per coordinator correction, replaced by the two stage proofs above, the
`--files` run, `check-architecture`, and `verify-quick`.

## 7. Doc-drift / `just` references

`docs/development/pre-commit-gate-tiers.md` references `just verify-slice`,
`just verify`, `just verify-quick`, `just lint-file`, `just typecheck-file`, and
`just test-file`; all exist. `check_doc_drift.py --governance-only` (the `doc-drift`
hook) **Passed** in the `--files` run, so no extra registration was needed.

## Concerns

1. **Measured baseline is small.** 6.39 s (OpenAPI) and 1.47 s warm / 4.23 s cold
   (TypeScript) are far below the brief's "minutes" framing. The move still removes
   a change-size-independent cost from every commit, but the local wall-clock saving
   is modest; CI remains the authority for both checks.
2. **`openapi-regenerate` semantics widened in one direction.** It had no `stages`
   key before, so it ran in *all* stages (including `manual`). Explicit
   `stages: [pre-push]` is the intended tier but is a slightly larger behavioral
   change than "pre-commit → pre-push"; noted so reviewers see it.
3. **`verify-slice` is not the brief's literal block.** Routing is required for the
   brief's own Step 6 to pass (evidence in §5). Source paths skip pytest; pass the
   test file alongside a source file to run its tests.
4. **`just verify` proof format.** `just --show verify` prints the doc comment plus
   `verify: check test-all`; the recipe line itself is unchanged.
5. **No commit.** Per task constraints, all changes remain in the working tree.

## Review round (T8b)

An independent review of `d8a844c3` (T7) and `c4ec637a` (T8) raised three defects in
the committed work. This round closes exactly those three. Files touched: `justfile`,
`scripts/_check_steps.py`, `docs/development/pre-commit-gate-tiers.md`, and this
section — nothing else. No gate was relaxed, nothing was suppressed, and no git write
happened.

### F3 — `verify-slice` misrouted prefixed and absolute web paths

**Defect (reproduced before the fix).** `./packages/web/lib/providers.ts` and any
absolute path under `packages/web/` matched none of the web arms and fell into
`*) py+=("$p")`, so ruff and pyright parsed TypeScript as Python:

```text
$ just verify-slice ./packages/web/lib/providers.ts
uv run --all-packages ruff check ./packages/web/lib/providers.ts
...
Found 61 errors.
error: recipe `lint-file` failed on line 516 with exit code 1
error: recipe `verify-slice` failed with exit code 1
```

**Root cause.** The `case` matched on the caller's *spelling* of the path, and only
some arms enumerated a `./` variant (`tests` did, `packages/web` did not). The
asymmetry was the defect: any arm added later could repeat it, and adding a
`./packages/web/*` arm would have been the workaround the brief forbids.

**Fix (root cause, not an arm).** Each path is normalised **once**, before the
`case`, so every arm matches one canonical repo-relative form:

- a leading `./` is stripped (`./` alone stays `.`);
- `"$PWD"` itself becomes `.`;
- an absolute path under the repository root becomes repo-relative;
- a path that cannot be normalised (absolute and outside the repository root) aborts
  the recipe with a message and exit 2 — it is never handed to a tool that cannot
  parse it.

Biome receives paths already relative to `packages/web`, so the prefix-stripping is
unchanged in effect, including the `packages/web` → `.` case (whole-project check).

**Evidence, both directions (after the fix).**

```text
$ just verify-slice ./packages/web/lib/providers.ts        # was 61 ruff errors
Checked 1 file in 4ms. No fixes applied.
EXIT=0

$ just verify-slice packages/web/lib/providers.ts          # no regression
Checked 1 file in 4ms. No fixes applied.
EXIT=0

$ just verify-slice packages/core/narrare_core/llm/model_listing.py
uv run --all-packages ruff check packages/core/narrare_core/llm/model_listing.py
All checks passed!
uv run --all-packages ruff format --check packages/core/narrare_core/llm/model_listing.py
1 file already formatted
0 errors, 0 warnings, 0 informations
EXIT=0

$ just verify-slice tests/unit/core/llm/test_model_listing.py packages/web/lib/providers.ts
...
============================== 21 passed in 2.26s ==============================
Checked 1 file in 5ms. No fixes applied.
EXIT=0
```

No ruff and no pyright line appears in either web run — only the Biome line, which is
the routing contract. Additional directions:

```text
$ just verify-slice "$PWD/packages/web/lib/providers.ts"
Checked 1 file in 4ms. No fixes applied.
EXIT=0

$ just verify-slice packages/web                          # biome target `.`
Checked 1313 files in 1797ms. No fixes applied.
Found 1 warning.
Found 1 info.
EXIT=0

$ just verify-slice /etc/hosts
verify-slice: cannot route '/etc/hosts' — absolute and outside the repository root (<repo>)
error: recipe `verify-slice` failed with exit code 2
EXIT=2
```

The two Biome observations on the whole-project run (config schema 2.5.8 vs CLI
2.5.14, one unused suppression) are pre-existing and exit 0; they are not produced by
this change.

### F2 — the documented local gate did not reach the catalog check

**Duplication found: yes.** `just check-architecture` (justfile) and the
`_check_steps.py` Architecture step were two parallel lists of the same family of
checks, overlapping on 5 of 8 scripts, each holding entries the other lacked:

- only in the recipe at `c4ec637a`: `check_architecture.py --prompt-integrity`,
  `generate_provider_catalog.py --check`, `check_frontend_file_size.py`;
- only in `_check_steps.py`: `check_python_file_size.py`,
  `checks/check_mutation_inert_assets.py`.

That is drift, not different scope — and it had already produced two instances of the
same defect: `generate_provider_catalog.py --check` (T7) was reachable from the commit
hook and CI but not from `just check` / `just verify`, and
`check_architecture.py --prompt-integrity` was in the recipe and CI but not in the
`just check` step (the commit hook is deliberately flag-free for latency, which does
not excuse the pre-merge gate).

**Root-cause choice (dedup, not a 32nd line).** The `just check-architecture` recipe
is now the single source of the architecture surface; the `_check_steps.py` step is
one command, `["just", "check-architecture"]`. So that delegating cannot drop a
check, the two scripts that lived only in the step moved into the recipe. Net effect
on the gate:

- `just check` / `just verify` now run every check they ran before, plus
  `check_architecture.py --prompt-integrity` — a strictness increase, and exactly
  what CI's architecture job runs;
- a future architecture check is added in one place (the recipe) and reaches both
  surfaces;
- `check_frontend_file_size.py` now runs twice per gate — once inside the delegated
  recipe, once in its own numbered `Frontend Size` step, which is kept because it is
  what gives size drift its labeled summary line (cost: one extra run of that
  script). This is duplicated *execution* of one script, not a duplicated list;
- `just` is the documented entry point for the runner (`just check` →
  `uv run --all-packages python scripts/run_checks.py`), and no CI job invokes
  `run_checks.py` directly, so the subprocess adds no new runtime requirement.

No test or document asserted the old step list (checked: no `build_steps` /
`_check_steps` references under `tests/` or in `docs/`; `just check-architecture` is
referenced only as a command name).

**Evidence — the gate fails on a stale catalog.** Mutation: one provider's
`label_key` suffix (`zai` → `zai_stale`), exactly one occurrence asserted before
editing, file backed up to `/tmp/opencode/` and restored with `cp` afterwards.

```text
$ grep -c '^    label_key: settings-ai\.providers\.zai$' .../catalog.yaml
1
$ sed -i 's/^    label_key: settings-ai\.providers\.zai$/    label_key: settings-ai.providers.zai_stale/' ...
$ grep -n zai_stale .../catalog.yaml
71:    label_key: settings-ai.providers.zai_stale
```

Baseline first (same tree, unmutated), so the failure below is attributable:

```text
$ just check
  [1/11] Architecture       ✓  3362 files, 13 exception(s)
  ...
  [3/11] Typecheck          ✗  5 error(s)          <- pre-existing, see below
  ...
  ✗ 1 check(s) failed
EXIT=1
```

(The Typecheck red is this worktree's pre-existing state — 5 errors in
`packages/core/narrare_core/embeddings/rerank.py` because the
`sentence_transformers` extra is not installed; recorded in the T5 ledger. It is
unrelated to this round and was not touched.)

With the stale catalog:

```text
$ just check
  [1/11] Architecture       ✗  issues found
  [2/11] Lint & Format      ✓  clean
  [3/11] Typecheck          ✗  5 error(s)
  ...
  ✗ 2 check(s) failed

  ── Architecture ──────────────────────────────────────
    ...
    +++ packages/core/narrare_core/llm/_providers/catalog_generated.py (fresh render)
    -    AIProvider.ZAI: "settings-ai.providers.zai",
    +    AIProvider.ZAI: "settings-ai.providers.zai_stale",
    provider catalog check FAILED: .../catalog_generated.py is stale — regenerate with
    `uv run --all-packages python scripts/generate_provider_catalog.py`
    +++ packages/web/lib/providers.generated.ts (fresh render)
    -  zai: "settings-ai.providers.zai",
    +  zai: "settings-ai.providers.zai_stale",
    provider catalog check FAILED: .../providers.generated.ts is stale — regenerate with
    `uv run --all-packages python scripts/generate_provider_catalog.py`
    labels.locales: zai: settings-ai.providers.zai_stale missing in .../de/settings-ai.json
    labels.locales: zai: settings-ai.providers.zai_stale missing in .../en/settings-ai.json
    labels.locales: zai: settings-ai.providers.zai_stale missing in .../fr/settings-ai.json
    error: recipe `check-architecture` failed on line 518 with exit code 1
EXIT=1
```

The pre-fix step could not have caught this: `git show HEAD:scripts/_check_steps.py`
contains zero `generate_provider_catalog` references, while `git show
HEAD:justfile` contains one. The second failing step is therefore the only delta
between the two runs.

```text
$ git show HEAD:scripts/_check_steps.py | grep -c generate_provider_catalog
0
$ git show HEAD:justfile | grep -c generate_provider_catalog
1
```

Restore verified:

```text
$ cp /tmp/opencode/catalog.yaml.bak packages/core/narrare_core/llm/_providers/catalog.yaml
$ git diff --stat -- packages/core/narrare_core/llm/_providers/catalog.yaml
(no output)
$ git diff -- packages/core/narrare_core/llm/_providers/catalog.yaml | wc -l
0
$ grep -c '^    label_key: settings-ai\.providers\.zai$' .../catalog.yaml
1
```

### F4 — the tiering document overstated `verify-slice`

**Defect.** "Integration and E2E tests never run here." The `tests|tests/*` arm sends
any named `tests/integration/…` or `tests/e2e/…` path to `just test-file` → plain
`pytest <paths> -v`: no `-m e2e` selection and no service boot, but the file does
run. The sentence was true only for implicit runs, i.e. slices that name no `tests/`
path.

**Fix (document and recipe comment aligned, no guard).** In
`docs/development/pre-commit-gate-tiers.md` the claim was replaced by the actual
contract:

- tests reach pytest only through `tests/` paths the caller names; nothing else does;
- a source-only slice runs no tests at all;
- `just test-file` is `pytest <paths> -v` — plain pytest, no `-m` selection, no
  service or container boot; a named `tests/integration/…` or `tests/e2e/…` path
  therefore does run, with nothing provisioned by the recipe;
- a path-normalisation bullet was added for F3 (one canonical form before routing;
  non-normalisable paths abort).

The `justfile` comment above `verify-slice` carried the same overstatement and now
carries the same correction. **Deviation from the brief: none** — no guard was added;
named paths still run as named.

### Gates re-run in this round

```text
$ just check-architecture
...
✅ All TS/TSX files are within hard limits
Frontend file-size ratchet: 0 current, 0 baseline, 0 new, 0 resolved
RESULT: Frontend file-size debt did not grow
EXIT=0 ELAPSED=21s
```

```text
$ just verify-quick
================= 14132 passed, 3 skipped in 153.44s (0:02:33) =================
 Test Files  461 passed (461)
      Tests  3932 passed (3932)
EXIT=0 ELAPSED=337s
```

```text
$ pre-commit run --files justfile scripts/_check_steps.py \
    docs/development/pre-commit-gate-tiers.md \
    docs/superpowers/plans/reports/2026-10-19-throughput-T08.md
...
Provider Catalog (ADR-099, generated + parity).......................................Passed
Documentation Drift (just commands + ADR + spec + agent names).......................Passed
Ruff Lint............................................................................Passed
Ruff Format..........................................................................Passed
Pyrefly Type Check (staged)..........................................................Passed
trim trailing whitespace.............................................................Passed
fix end of files.....................................................................Passed
EXIT=0 ELAPSED=11s
```

`just check` itself was run twice for the F2 proof above (baseline and stale
catalog); both runs are recorded there, including the pre-existing Typecheck red.

### Concerns (this round)

1. **`just check` is red in this worktree for a pre-existing reason.** The 5
   `rerank.py` pyright errors (missing `sentence_transformers` extra) are unchanged
   by this round and were already recorded in the T5 ledger. The F2 proof isolates
   the delta by comparing the same gate before and after the catalog mutation.
2. **The runner now depends on `just` being on PATH.** `scripts/run_checks.py`
   invoked *directly* (not through `just check`) would fail the Architecture step
   with `not found: just`. `just check` / `just verify` are the documented entry
   points and no CI job calls the runner directly, so this is declared rather than
   hidden; the step comment states it.
3. **Failure output is noisier.** The Architecture step now prints the recipe's
   echoed command lines in the compact failure block (just's normal echo). Only
   cosmetic; success output is unchanged and the compact summary still reads
   `N files, N exception(s)`.
4. **One script runs twice per gate** (`check_frontend_file_size.py`, see F2).
5. **Observation, not changed:** repo-wide `ruff format --check .` is red in this
   worktree — 116 `docs/**.md` files with embedded Python would be reformatted by
   the pinned ruff 0.16.9. The runner's Lint step scans only `apps/ packages/
   scripts/ tests/ evals/` (3374 files, clean), so `just check` does not hit it; a
   slice that names a whole-tree path (e.g. `just verify-slice "$PWD"`) does. Out
   of scope for these three findings, recorded so the next reviewer does not
   rediscover it as fallout from this round.

## Commit

Committed as `c4ec637a` — `chore(dev): push-tier the two whole-project hooks, add verify-slice`.

Status correction: the "not committed" line above describes the report at the time
it was written; this section records the commit that landed it.
