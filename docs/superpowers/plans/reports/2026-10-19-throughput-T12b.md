# Throughput T12b — `--with-intent` surfaces

- **Date:** 2026-10-20
- **Branch:** `brave-egret` (base `15f79cae`)
- **Status:** `STATUS: NEEDS_SLICING` — behaviour complete and verified, allocation
  blocked by the RULE-04 script limit; no git writes.
- **Files authored:** `scripts/scaffold_feature.py` (679 lines),
  `tests/unit/scripts/test_scaffold_feature.py` (176 lines), this report.

## 1. Implemented and verified

`--with-intent NAME --category C --mode M` writes all eight surfaces; the committed
parity oracle returns **0 disagreements** on the result.

- Enum member before the embeddings anchor, with the category-derived docstring.
- `INTENT_CATEGORY_MAP`, `INTENT_PROFILES`, `ROUTE_CONFIGS` and
  `INTENT_TO_CATEGORY`/`INTENT_TO_MODE` inserted after the first routed sibling.
- Manifest block cloned from that sibling (routeable, category, mode, template,
  security, fallback policy) and registry `prompt_path_compliance` key.
- `_bundled/{category}/{en,de,fr}/{mode}/system.md` with full frontmatter,
  `## System Prompt`, a real scope sentence and the generated marker.
- The prompt-route category comes from the sibling route (`KB_IMPROVE` → `kb`),
  never from `--category`: model category and prompt category are distinct facts
  (`CHAT` is `chat`/`writing`, `SUMMARIZE` is `planning`/`analysis`).

CR-4: missing `--category` or `--mode` exits 2 naming both flags, before any read
or write. A duplicate in any surface exits 1 and writes nothing. Writes stay atomic
through `_write_all` (restore on `OSError`).

### Evidence

```text
tests/unit/scripts/test_scaffold_feature.py ................. 10 passed in 2.69s
tests/unit/scripts/ ......................................... 1476 passed in 26.95s
just lint-check ............................................. ruff check + format green
just check-architecture ..................................... 1 violation (RULE-04 size only)
```

Throwaway worktree at `15f79cae`, script copied in, recipe run through `just`:

```text
$ just new-feature SCAFFOLD-003 core --with-intent parity_probe --category kb --mode parity_mode
created .../llm/intent_categories.py … .../_bundled/kb/{en,de,fr}/parity_mode/system.md
$ python scripts/check_intent_parity.py
31 intents, 25 routed, 0 disagreements
$ ruff format --check <eight files> → 8 formatted; ruff check <same> → All checks passed!
$ <same intent, new id>                                → exit 1, `git status` hash unchanged
```

Two probe-found root causes were fixed: `_refuse_existing` treated the seven edited
surfaces as forbidden targets (only new prompt files are targets), and `_call` now
wraps generated entries at 100 columns exactly where `ruff format` would.

## 2. Blocking gate

```text
scripts/scaffold_feature.py:679  [RULE-04]  File has 679 lines (hard limit: 600). Split required.
```

## 3. Proposed split (needs authorization — third authored file)

- `scripts/scaffold_intent.py` (~360 lines): exit codes, intent regexes, surface
  paths, `_ENUM_ANCHOR`, `_PROMPT_SENTENCES`, `_fail`, the parity-parser adapters
  (`_read`, `_tree`, `_yaml`, `_entries`, `_insert_after/_before`, `_keyword`,
  `_call`), `_validate_intent`, `_sibling`, the manifest/registry renderers,
  `_prompt_path`, `_prompt_text` and a public `plan_intent(name, category, mode,
  root) -> dict[Path, str]`.
- `scripts/scaffold_feature.py` (~350 lines): feature document, per-layer test
  skeletons, contract stub, report stub, target refusal, atomic write, orchestration
  and CLI; imports `EXISTING_ID_EXIT`, `GATE_FAILURE_EXIT` and `plan_intent` (the
  test keeps importing the exit codes from this module).
- Test file unchanged; both files sit well under 600 — RULE-04's "hard limits → new
  module" instead of compressing prose.

## 4. Concerns

- Review policy caps a unit at ≤250 new production LOC; this slice adds ~344 either
  way, so the coordinator may re-slice T12b/T12c or share the budget.
- Pre-existing T12a observation: the feature document's `paths:` lists only itself,
  because it is rendered before the other planned paths exist.

## Coordinator ruling CR-8 (extraction)

The coordinator authorized the §3 split as a pure move (T12b2): no behaviour
change, no renamed public entry points, test file untouched.

| File | Lines | Contents |
|---|---:|---|
| `scripts/scaffold_intent.py` | 386 | intent regexes, surface paths, parity-parser adapters, manifest/registry renderers, prompt renderers, `plan_intent` |
| `scripts/scaffold_feature.py` | 326 | feature document, test skeletons, contract/report stubs, target refusal, atomic write, orchestration, CLI |

`scaffold_feature.py` no longer holds intent logic; it imports `plan_intent`,
`fail` and both exit codes (re-exported through `__all__`, so
`from scripts.scaffold_feature import EXISTING_ID_EXIT, GATE_FAILURE_EXIT`
still works unchanged). `_plan_intent` became `plan_intent` (public entry point,
per §3). One further declared rename: `_fail` → `fail`, required because the
helper is now consumed across modules (a private import would be the only new
pyright-strict `reportPrivateUsage` finding). Semantics of both are identical,
including the `scaffold_feature:` stderr prefix and the generated marker text
`Generated by scripts/scaffold_feature.py` that the test asserts.

### Evidence (re-run after the split)

```text
just test-file tests/unit/scripts/test_scaffold_feature.py ... 10 passed in 2.62s
just test-file tests/unit/scripts/ ........................... 1476 passed in 27.36s
just lint-check ............................................. All checks passed! / 3383 files already formatted
just check-architecture ..................................... exit 0
  ✅ All Python files are within hard limits
  Python file-size ratchet: 0 current, 0 baseline, 0 new, 0 resolved
  RESULT: Python file-size debt did not grow

# parity oracle on a fresh mirror (same path the unit test uses)
scaffold SCAFFOLD-004 core --with-intent parity_probe2 --category kb --mode parity_mode2
31 intents, 25 routed, 0 disagreements          (exit 0)
ruff format --check / ruff check on the generated tree: 82 formatted / All checks passed!
second run with the same intent: exit 1, all nine surfaces listed, bytes untouched
```

The real-worktree replay was not executable here: the shell call containing
`git worktree add` was permission-denied, so the mirror path the test itself
uses was replayed instead (same eight surfaces plus `_bundled` tree, same
committed gate binary). No git writes were made.

Concern for review: `pyright` strict reports 20 findings on these two files,
all inherited unchanged from the T12b intent code (private use of
`check_intent_parity` helpers and two `ast.expr` narrowing gaps at
`profile.args`). The extraction adds none; fixing them would be a typing edit,
not a move, so it is left to a follow-up.

## Coordinator ruling CR-9 (shared surface reader)

The 20 pyright findings above were **not** accepted as a follow-up. They split
into two defects, and both were fixed at the root (T12b3).

**Defect 1 — one module's internals were another module's API.**
`scaffold_intent.py` imported eight private helpers from
`check_intent_parity.py` (`reportPrivateUsage` was correct). The reading layer
moved to `scripts/_intent_surface_reader.py` (underscore-module convention as
`_check_steps.py`): `parse_module`, `module_assignments`, `class_members`,
`attribute_name`, `string_value`, `attribute_dict`, `string_dict`,
`route_config`, `allowed_context_modes`, `load_yaml`, `mapping_entries`. Both
consumers import that module; neither imports the other.

**Defect 2 — `fail()` was typed `-> None` although it always exits.**
That single annotation caused all three narrowing findings: `mode` stayed
`str | None` at `re.fullmatch`, the return tuple widened to
`tuple[str, str, str | None]`, and `profile`/`call` never narrowed before
`.args`. `fail()` is now `-> NoReturn`; the guards narrow from the existing
refusals, with no cast and no new suppression. The two `cast()` calls kept in
the reader are the pre-existing, documented YAML boundary narrowing
(`safe_load` is untyped) moved verbatim from the gate.

| File | Lines | Category limit |
|---|---:|---:|
| `scripts/scaffold_intent.py` | 396 | script, 600 — OK |
| `scripts/scaffold_feature.py` | 326 | script, 600 — OK |
| `scripts/check_intent_parity.py` | 407 | script, 600 — OK |
| `scripts/_intent_surface_reader.py` | 157 | script, 600 — OK |

### Evidence

```text
pyright (4 files) ............................................ 0 errors, 0 warnings
just test-file tests/unit/scripts/test_scaffold_feature.py ... 10 passed
just test-file .../test_check_intent_parity.py ............... 19 passed
python scripts/check_intent_parity.py ........................ 30 intents, 24 routed, 0 disagreements (exit 0)
just check-architecture ...................................... exit 0, Python file-size debt did not grow
just lint-check ............................................. All checks passed! / 3384 files already formatted
```

No behaviour change: refusals, exit codes, rendered output and prompt text are
unchanged; the scaffolder test still asserts the generated tree is gate-green.
