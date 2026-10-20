# Throughput T15 — Intent parity gate on commit, local and CI surfaces

- **Date:** 2026-10-20
- **Branch:** `brave-egret`
- **Base commit:** `79b78e61` (T13)
- **Status:** implemented, verified, **not committed** (no git writes per task constraints;
  the three authored files are staged only so `pre-commit` accepts the config —
  `pre-commit` refuses an unstaged `.pre-commit-config.yaml`)
- **Flywheel:** `.superpowers/sdd/2026-10-19-dev-throughput-program/task-15-brief.md`
  (plus coordinator corrections CR: `--with-intent` now needs `--category`/`--mode`;
  no `pre-commit run --all-files`)
- **Slice:** T15 of the P2 wave — wire the T14 gate into the three governed surfaces
  and close the P5→P2 dependency with the T12b scaffolder.
- **Files authored:**
  - `.pre-commit-config.yaml` (hook `intent-parity`, after `provider-catalog-check`)
  - `justfile` (one line in `check-architecture`, after the review-policy line)
  - `.github/workflows/ci.yml` (one step in the `architecture` job, after the
    provider-catalog step)
  - this report

## 1. Surfaces as wired

`.pre-commit-config.yaml`:

```yaml
      # Intent contract parity — ADR-025/037/038. Compares the eight intent
      # declaration surfaces against one another (enum, category map, profiles,
      # route table + intents, prompt directories, manifest, adoption registry).
      # Comparison only: it moves no authority out of the manifest or the registry.
      - id: intent-parity
        name: Intent Contract Parity (ADR-025/037/038)
        entry: uv run --no-sync python scripts/check_intent_parity.py
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]
```

`justfile` (`check-architecture`):

```make
    uv run --all-packages python scripts/check_review_policy_consistency.py
    # Intent contract parity (throughput T15) — the commit hook, this recipe and
    # the CI architecture job run the same gate against the same surfaces.
    uv run --all-packages python scripts/check_intent_parity.py
    uv run --all-packages python scripts/check_empty_kb_vars.py
```

`.github/workflows/ci.yml` (`architecture` job):

```yaml
      - name: Check provider catalog (ADR-099)
        run: uv run --no-sync python scripts/generate_provider_catalog.py --check

      - name: Check intent contract parity (ADR-025/037/038)
        run: uv run --no-sync python scripts/check_intent_parity.py
```

## 2. Hook proof — both directions

Clean tree:

```text
$ pre-commit run intent-parity --hook-stage pre-commit
Intent Contract Parity (ADR-025/037/038).................................Passed
exit=0
```

Scratch root `/tmp/opencode/parity-mut` (`cp -a` of `scripts/` and
`packages/core/`), one `INTENT_TO_MODE` value mutated in
`route_table_intents.py`; the real tree was verified unchanged by sha256 and
`git status`:

```text
$ uv run --all-packages python scripts/check_intent_parity.py /tmp/opencode/parity-mut
30 intents, 24 routed, 1 disagreements
KB_CONSISTENCY: mode disagreement between 'route_intents' ('parity_probe_mismatch') and 'route_configs' ('consistency')
exit=1

$ sha256sum -c /tmp/opencode/real-before.sha
packages/core/narrare_core/prompts/route_table_intents.py: OK
```

**Concern — removal is silently accepted.** The brief's literal mutation
(*delete* one `INTENT_TO_MODE` entry) was tried first and the gate returned
exit 0:

```text
# scratch copy: LLMIntent.KB_CONSISTENCY: "consistency" removed from INTENT_TO_MODE only
$ uv run --all-packages python scripts/check_intent_parity.py /tmp/opencode/parity-mut
30 intents, 24 routed, 0 disagreements
exit=0
```

Root cause: `route_intents` facts are built from
`set(route_categories) | set(route_modes)`, so a key still present in
`INTENT_TO_CATEGORY` keeps the intent in the surface, and `_agreement` skips a
fact whose field is `None`. A *changed* value is caught; a *deleted* mode entry
is not. The hook is therefore proven to fail via the value mutation above, but
T14's key-set family has this gap. Not fixed here (out of T15's authored-file
scope); flagged for a follow-up on `scripts/check_intent_parity.py`.

## 3. P5→P2 closure (throwaway worktree)

```text
$ git worktree add /tmp/opencode/t15 HEAD
Preparing worktree (detached HEAD 79b78e61)

$ just new-feature SCAFFOLD-002 core --with-intent parity_probe --category kb --mode parity_probe_mode
created packages/core/narrare_core/scaffold_002/...
created packages/core/narrare_core/prompts/_bundled/kb/en/parity_probe_mode/system.md
created packages/core/narrare_core/prompts/_bundled/kb/de/parity_probe_mode/system.md
created packages/core/narrare_core/prompts/_bundled/kb/fr/parity_probe_mode/system.md
created docs/features/SCAFFOLD-002.md
exit=0

$ uv run --all-packages python scripts/check_intent_parity.py
31 intents, 25 routed, 0 disagreements
exit=0

$ uv run --all-packages python scripts/check_prompt_structure.py
PASS: 55/57 system prompts valid (2 with warnings)
Prompt warning ratchet: 8 current, 8 baseline, 0 new, 0 resolved
RESULT: 8 WARN(s) (non-blocking)
exit=0

$ git worktree remove --force /tmp/opencode/t15
exit=0
```

No manual edit in the throwaway tree. Scaffold did not exit 2, so the
dependency is closed.

## 4. Gates

`just check-architecture` — exit 0; the four required lines in order:

```text
uv run --all-packages python scripts/generate_provider_catalog.py --check
provider catalog check: packages/core/narrare_core/llm/_providers/catalog_generated.py is up to date
provider catalog check: packages/web/lib/providers.generated.ts is up to date
uv run --all-packages python scripts/check_pre_commit_gate_tiers.py
✅ pre-commit hook tiering matches the pinned tiers (.pre-commit-config.yaml)
uv run --all-packages python scripts/check_review_policy_consistency.py
✅ review/report policy marker, normative block and pointers agree
uv run --all-packages python scripts/check_intent_parity.py
30 intents, 24 routed, 0 disagreements
```

`pre-commit run --files .pre-commit-config.yaml justfile .github/workflows/ci.yml`
(exit 0; excerpt):

```text
Provider Catalog (ADR-099, generated + parity).......................................Passed
Intent Contract Parity (ADR-025/037/038).............................................Passed
check yaml...........................................................................Passed
```

`uv run --all-packages python scripts/check_doc_drift.py`:

```text
⚠️  57 doc drift warnings

✅ Doc drift check passed (with warnings)
exit=0
```

`just verify-quick` (exit 0):

```text
================= 14177 passed, 3 skipped in 152.06s (0:02:32) =================
 Test Files  461 passed (461)
      Tests  3932 passed (3932)
```

CI YAML parse:

```text
$ uv run --all-packages python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text())"
YAML OK
exit=0
```

## 5. Deviations

- **No `--all-files` run.** Per the coordinator correction, the whole-project
  pre-commit run was replaced by `--files` on the three changed files plus the
  hook-stage proof in §2; `--all-files` does not finish in this repository.
- **Scratch proof uses a value mutation.** See §2: deleting the entry is not
  detected by the current gate, so the report records both the deletion result
  (exit 0) and the value-mutation result (exit 1, naming intent and both
  surfaces) rather than claiming a failure that did not occur.
- **Index staging.** `.pre-commit-config.yaml` had to be staged because
  pre-commit refuses to run with an unstaged config. No commit/branch/tag
  operation was performed in this worktree.
