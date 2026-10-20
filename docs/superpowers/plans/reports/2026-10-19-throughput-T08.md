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
difference is the treatment of the no-`stages` hooks and of `openapi-regenerate`,
which had no stage restriction before this change.

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
