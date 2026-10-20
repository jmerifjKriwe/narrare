# Throughput T9 — Machine-pin the hook tiering

- **Date:** 2026-10-20
- **Branch:** `brave-egret`
- **Base commit:** `410626c2` (`chore(dev): close the verify-slice routing gap and the local-gate hole (T8 review round)`)
- **Status:** implemented, verified, **not committed** (no git writes per task constraints)
- **Files authored:**
  - `scripts/check_pre_commit_gate_tiers.py` (new gate, 149 lines)
  - `tests/unit/scripts/test_pre_commit_gate_tiers.py` (new, 6 tests)
  - `justfile` (one line + comment in `check-architecture`, immediately after the provider-catalog line)
  - this report

## 1. Why this ratchet

T8 moved five whole-project hooks to `pre-push` (`pyright`, `pyright-tests`,
`bandit`, `openapi-regenerate`, `typecheck-frontend`), parked `adoption-score` at
`manual` and kept `conventional-commits` at `commit-msg`. The decision lived in
YAML comments and a planning document only: nothing failed if a later edit moved
`typecheck-frontend` back into the commit path, and nothing failed if a slow hook
was simply deleted. T9 turns that prose into a gate wired into
`just check-architecture`.

## 2. RED evidence (tests written first)

`just test-file tests/unit/scripts/test_pre_commit_gate_tiers.py` before the
script existed:

```text
==================================== ERRORS ====================================
______ ERROR collecting tests/unit/scripts/test_pre_commit_gate_tiers.py _______
Traceback:
tests/unit/scripts/test_pre_commit_gate_tiers.py:18: in <module>
    from scripts.check_pre_commit_gate_tiers import find_tier_violations
E   ModuleNotFoundError: No module named 'scripts.check_pre_commit_gate_tiers'
=========================== short test summary info ============================
ERROR tests/unit/scripts/test_pre_commit_gate_tiers.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.30s ===============================
error: recipe `test-file` failed on line 366 with exit code 2
```

## 3. The pinned rule set

Constants (the T8 decision, as data):

```python
PUSH_ONLY = {"pyright", "pyright-tests", "bandit", "openapi-regenerate", "typecheck-frontend"}
MANUAL_ONLY = {"adoption-score"}
COMMIT_MSG_ONLY = {"conventional-commits"}
```

`find_tier_violations(config_text: str) -> list[str]` parses the config with
`yaml.safe_load` and applies six rules, one line per violation:

| # | Rule | Origin |
|---|---|---|
| 1 | Every `PUSH_ONLY` id must declare exactly `stages: [pre-push]` | brief |
| 2 | Every `MANUAL_ONLY` id must declare exactly `stages: [manual]` | brief |
| 3 | Every `COMMIT_MSG_ONLY` id must declare exactly `stages: [commit-msg]` | brief |
| 4 | No hook outside those three sets may declare `pre-push` | brief ("no other hook may") |
| 5 | A hook id may appear only **once** in the config | added (evasion path) |
| 6 | Every hook id in the three sets must **exist** in the config | added (evasion path) |

Rules 5 and 6 close the two ways to satisfy rules 1–4 while defeating the intent:

- **Duplicate id (5):** appending a second `- id: typecheck-frontend` with
  `stages: [pre-push]` leaves the original copy at `pre-commit`. Every stage rule
  passes (the duplicate has the right stage; the original is "the" pinned hook) but
  the hook still runs at commit time. Counting occurrences per id is the only
  check that sees it.
- **Missing hook (6):** deleting `pyright-tests` outright removes both the hook and
  any stage mismatch, so a "must declare pre-push" rule is vacuously true. The
  ratchet must require presence, not only correct staging.

Deliberately **not** a rule: a hook without a `stages:` key. Pre-commit then runs
it at its default stages (which include `pre-push` in practice), but many fast
hooks in this config intentionally omit the key (`ruff-lint`, `ruff-format`,
`biome-frontend`, `validate-i18n`, the remote hygiene hooks). Flagging them would
not be a ratchet on T8, it would be a config migration — recorded as a concern
below, not silently half-implemented.

Exact-set comparison (`declared != {stage}`) also catches `stages: [pre-push,
pre-commit]`, which is a legitimate pre-commit spelling but would put the hook back
in the commit path.

`main(argv)` takes an optional positional config path (default
`.pre-commit-config.yaml`) so the gate can be pointed at a copy; it exits 1 on
violations (one indented line each), 1 on an unreadable file or invalid YAML, and 0
when clean. The module does no I/O outside `main()`.

## 4. Two-sided proof of the ratchet against the real config

Clean config:

```text
$ uv run --all-packages python scripts/check_pre_commit_gate_tiers.py
✅ pre-commit hook tiering matches the pinned tiers (.pre-commit-config.yaml)
exit=0
```

Mutated **copy** (`/tmp/opencode/pre-commit-mutated.yaml`, `typecheck-frontend`
moved back to `stages: [pre-commit]`; the real file never edited):

```text
$ uv run --all-packages python scripts/check_pre_commit_gate_tiers.py \
    /tmp/opencode/pre-commit-mutated.yaml
❌ pre-commit hook tiering: 1 violation(s) in /tmp/opencode/pre-commit-mutated.yaml
  - 'typecheck-frontend': declares [pre-commit], the pre-push tier requires [pre-push]
exit=1
```

The working tree is untouched:

```text
$ git diff --stat .pre-commit-config.yaml
(empty)
```

## 5. Gate output (raw tails)

`just test-file tests/unit/scripts/test_pre_commit_gate_tiers.py`:

```text
tests/unit/scripts/test_pre_commit_gate_tiers.py::test_violation_when_a_hook_id_is_declared_twice PASSED [ 16%]
tests/unit/scripts/test_pre_commit_gate_tiers.py::test_violation_when_a_tiered_hook_is_deleted PASSED [ 33%]
tests/unit/scripts/test_pre_commit_gate_tiers.py::test_violation_when_a_moved_hook_returns_to_commit PASSED [ 50%]
tests/unit/scripts/test_pre_commit_gate_tiers.py::test_real_config_is_clean PASSED [ 66%]
tests/unit/scripts/test_pre_commit_gate_tiers.py::test_violation_when_a_moved_hook_disappears_from_push PASSED [ 83%]
tests/unit/scripts/test_pre_commit_gate_tiers.py::test_violation_when_a_new_hook_claims_pre_push PASSED [100%]

============================== 6 passed in 2.37s ===============================
```

`just check-architecture` (now includes the new line; `EXIT=0`):

```text
# Hook-tiering ratchet (throughput T8/T9) — machine-pins which hooks run at
# pre-push / manual / commit-msg so a whole-project hook cannot drift back
# into the commit path (or be deleted) unnoticed.
uv run --all-packages python scripts/check_pre_commit_gate_tiers.py
✅ pre-commit hook tiering matches the pinned tiers (.pre-commit-config.yaml)
...
Summary: 45 services checked, 0 missing test files, 0 low coverage
...
✅ All TS/TSX files are within hard limits
Frontend file-size ratchet: 0 current, 0 baseline, 0 new, 0 resolved
RESULT: Frontend file-size debt did not grow
EXIT=0
```

`just lint-check`:

```text
uv run --all-packages ruff check apps/ packages/ scripts/ tests/ evals/
All checks passed!
uv run --all-packages ruff format --check apps/ packages/ scripts/ tests/ evals/
3376 files already formatted
EXIT=0
```

`pyright` (strict, `scripts/` is in `include`) on the new module:

```text
$ uv run --all-packages pyright scripts/check_pre_commit_gate_tiers.py
0 errors, 0 warnings, 0 informations
```

## 6. Concerns

1. **Hooks without a `stages:` key are not tiered.** An existing hook that deletes
   its `stages: [pre-commit]` line gains pre-push execution without tripping this
   gate (rule 4 only sees explicit declarations). Migrating the config to always
   declare a stage would close it, but that is a separate, larger change; the
   staged ratchet covers the hooks T8 actually moved, plus the two evasion paths.
2. **The tier sets are duplicated** in the script and in the planning document.
   The script is the SSOT for the gate; a tier change now requires editing
   `PUSH_ONLY`/`MANUAL_ONLY`/`COMMIT_MSG_ONLY` and the test's `BASE` fixture is
   unaffected (it asserts one tier per test only), so the change is deliberate,
   not silent — but it is a two-place edit by design (the gate can't read the
   documented intent from prose).
3. **Same-file duplicate detection is global, not per-repo.** A hook id reused in a
   second repo block is flagged even if the two repos are distinct (pre-commit
   actually allows repeated ids across repos; they are addressed as `repo:id`).
   That is intentional for a governed single-repo config, but a future multi-repo
   split would have to relax rule 5 to `repo + id`.
4. The report itself is docs-only and not gated.

## Commit

Committed as `f011ee28` — `feat(scripts): pin pre-commit hook tiering`.

Status correction: the "not committed" line above describes the report at the time
it was written; this section records the commit that landed it.
