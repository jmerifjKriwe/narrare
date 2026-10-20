# Throughput T12a — Feature scaffolder core

- **Date:** 2026-10-20
- **Branch:** `brave-egret`
- **Base commit:** `232f0dc3`
- **Status:** implemented, verified, **not committed** (no git writes per task constraints)
- **Flywheel:** `.superpowers/sdd/2026-10-19-dev-throughput-program/task-12-brief.md`
- **Slice:** T12a of 3 — core scaffolder only; `--with-intent` (T12b) and the
  post-condition gate (T12c) are deliberately out of scope.
- **Files authored:**
  - `scripts/scaffold_feature.py` (new, 335 lines / 239 non-blank non-comment)
  - `tests/unit/scripts/test_scaffold_feature.py` (new, 6 tests)
  - `justfile` (recipe `new-feature`, after `verify-slice`)
  - this report

## 1. RED evidence

The brief's four tests plus the two slice-specific cases were written first. The
first run failed at collection:

```text
tests/unit/scripts/test_scaffold_feature.py:5: in <module>
    from scripts.scaffold_feature import EXISTING_ID_EXIT, scaffold_feature
E   ModuleNotFoundError: No module named 'scripts.scaffold_feature'
=========================== short test summary info ============================
ERROR tests/unit/scripts/test_scaffold_feature.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.29s ===============================
```

After implementation: `6 passed in 2.50s`.

## 2. What the scaffolder writes

`scaffold_feature(feature_id, layers, root, *, with_intent=None)` writes only
declaration artifacts, with deterministic naming for `FIND-099`:

| Artifact | Path |
|---|---|
| feature document | `docs/features/FIND-099.md` |
| test skeleton (per layer) | `tests/unit/<layer>/test_find_099.py` |
| contract stub (core only) | `packages/core/narrare_core/find_099/contracts.py` |
| package initialiser (core only) | `packages/core/narrare_core/find_099/__init__.py` |
| report stub | `docs/superpowers/plans/reports/<UTC date>-find_099.md` |

- The document frontmatter `paths:` list is filtered against `Path.exists()`
  (the document's own path counts as created by this run), so it contains only
  paths that were created or already existed.
- The document, skeletons and report are English prose; no `TODO`, `FIXME` or
  `XXX` marker appears anywhere. The unresolved-design section is
  `## Open questions`.
- No `service.py`, `router.py`, `repository.py` or component is ever written —
  the layer inputs gate test/doc/contract output only (RULE-20).
- Every target path is pre-checked before the first write. If any exists, the
  call exits `EXISTING_ID_EXIT` (`1`) and writes nothing.
- `with_intent` is accepted by the signature and raises `NotImplementedError`
  before any planning or write; it is never silently ignored.

CLI: `python scripts/scaffold_feature.py <id> <layer...> [--with-intent NAME] [--root PATH]`.
Exit `0` written, `1` existing target, `2` invalid input or unwired surface.

## 3. Tests (6)

Brief's four, verbatim bodies:

1. `test_scaffolds_feature_doc_tests_contract_and_report_stub`
2. `test_never_generates_service_router_or_component_files`
3. `test_project_language_is_english`
4. `test_refuses_a_feature_id_that_already_exists`

Slice-specific additions:

5. `test_core_only_layer_writes_no_api_or_web_skeleton` — `("core",)` writes
   `tests/unit/core/` and no `tests/unit/api/` or `tests/unit/web/` file.
6. `test_api_only_layer_writes_no_contract_stub` — `("api",)` writes no
   `contracts.py` and nothing under `packages/core/`.

## 4. Dry run outside the repository

```text
$ uv run --all-packages python scripts/scaffold_feature.py SCAFFOLD-001 core api web --root /tmp/opencode/scaffold-probe-12b
created .../packages/core/narrare_core/scaffold_001/__init__.py
created .../packages/core/narrare_core/scaffold_001/contracts.py
created .../tests/unit/core/test_scaffold_001.py
created .../tests/unit/api/test_scaffold_001.py
created .../tests/unit/web/test_scaffold_001.py
created .../docs/superpowers/plans/reports/2026-10-20-scaffold_001.md
created .../docs/features/SCAFFOLD-001.md
exit=0
```

`find` showed exactly those 7 files. Frontmatter:

```yaml
paths:
  - docs/features/SCAFFOLD-001.md
  - tests/unit/core/test_scaffold_001.py
  - tests/unit/api/test_scaffold_001.py
  - tests/unit/web/test_scaffold_001.py
  - packages/core/narrare_core/scaffold_001/__init__.py
  - packages/core/narrare_core/scaffold_001/contracts.py
  - docs/superpowers/plans/reports/2026-10-20-scaffold_001.md
```

Programmatic re-check: `7 declared paths, missing=[]`. The generated core
skeleton also passed on its own (`1 passed`). A second run of the same command
printed the seven existing paths and exited `1`. The probe tree was removed.

`--with-intent` probe:

```text
scaffold_feature: scaffold_feature(with_intent=...) lands with T12b; no intent surface was written
with_intent_exit=2
nothing written
```

## 5. Gate tails

`just test-file tests/unit/scripts/test_scaffold_feature.py`:

```text
============================== 6 passed in 2.50s ===============================
```

`just test-file tests/unit/scripts/`:

```text
============================ 1453 passed in 24.20s =============================
```

`just lint-check` (`exit=0`):

```text
All checks passed!
3380 files already formatted
```

`just typecheck-file scripts/scaffold_feature.py tests/unit/scripts/test_scaffold_feature.py`:

```text
0 errors, 0 warnings, 0 informations
```

`just check-architecture` (`exit=0`) key lines:

```text
✅ Architecture constraints OK (3368 files checked, 13 approved exception(s))
✅ All Python files are within hard limits
✅ Prompt Surface Contract OK
✅ pre-commit hook tiering matches the pinned tiers (.pre-commit-config.yaml)
✅ review/report policy marker, normative block and pointers agree
✅ mutation_inert convention check passed
Summary: 45 services checked, 0 missing test files, 0 low coverage
✅ All TS/TSX files are within hard limits
```

## 6. Concerns

- `with_intent` raises `NotImplementedError` by design; the brief's fifth test
  (`test_with_intent_creates_three_locale_prompt_directories`) is intentionally
  absent and belongs to T12b. No intent surface exists yet.
- T12c's post-condition gate is not wired. `GATE_FAILURE_EXIT` is used today for
  invalid ids/layers and the unwired intent flag; no scoped architecture run
  happens after writing.
- The generated `contracts.py` is an empty `Protocol`. It is valid, pyright-clean
  and green on arrival, but it carries no method signatures until the feature's
  contract is designed — which is the point of a RULE-03 stub.
- The `paths:` frontmatter key is new for feature documents; existing docs use
  the singular `service`/`contract`/`router`/`prompt` fields. The checker
  `check_feature_path_accuracy.py` ignores unknown fields, so scaffolded docs
  pass it; the singular fields stay empty until implementation.
- Generated files outside the repository are not exercised by this repo's
  gates during the unit test; the dry run above is the end-to-end evidence.

## Commit

Committed as `db48bbe3` — `feat(scripts): feature scaffolder core, emitting only gate-green declarations`.

Status correction: the "not committed" line above describes the report at the time
it was written; this section records the commit that landed it.
