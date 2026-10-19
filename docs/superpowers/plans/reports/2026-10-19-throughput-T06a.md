# Throughput T06a — Provider-catalog parity gate (Core slice)

**Date:** 2026-10-19
**Branch:** `brave-egret` (base `3334a888`)
**Scope:** Task 6, slice A — the generator, the six Core invariants, `--check`
wiring, and the carried-forward test/validation gaps in the same files.
Slice B (API/i18n surfaces) is explicitly **not** implemented here.

## Files changed

- `scripts/generate_provider_catalog.py` — `ParityViolation`, `check_parity`,
  six Core checks, `--check` wiring, `newline="\n"` writers, empty-catalog
  rejection, `isidentifier` guard comment.
- `tests/unit/scripts/test_generate_provider_catalog.py` — T1-M2, T3-M1,
  T3-M2, T1-M5, `--check` parity-wiring test.
- `tests/unit/scripts/test_generate_provider_catalog_parity.py` — new, one
  mutation test per invariant plus pristine-tree and wildcard-shadow tests.

No production surface was modified. No git writes were performed.

## Invariants implemented (6)

All parsing is AST-only (`ast.parse` on the file text); no surface is imported.
`check_parity` is a pure function of `(specs, repo_root)` and returns
`list[ParityViolation]`, sorted by `(surface, detail)`. Every provider-specific
`detail` starts with the provider id, which gives the required stable
surface-then-provider ordering.

| Surface | File | How it is parsed | Assertion |
|---|---|---|---|
| `pricing.keys` | `llm/model_pricing.py` | module-level `DEFAULT_RATES` assignment evaluated with `ast.literal_eval` (still AST, no import) | catalog ids == key set; missing id → one violation, extra key → one violation |
| `pricing.values` | same | the evaluated per-provider mapping | `input`/`output` equal `pricing_default`; missing/mismatched rate produces one violation naming both values (`catalog input 0.5 != DEFAULT_RATES 0.7`) |
| `cache.arms` | `llm/_providers/cache_settings.py` | first `ast.Match` inside `build_model_settings`; `MatchValue` and `MatchOr` literals; `MatchAs(pattern=None)` as wildcard | each catalog id occurs exactly once; any id arm after the first wildcard is reported as shadowed |
| `cache.bodies` | same | `ast.Return` value of each case, evaluated with `ast.literal_eval` | `anthropic_cache_control` → `{"cache_control": True}`; `automatic`/`none` → `{}`; detail prints catalog policy, expected body and actual body |
| `mem0.keys` | `memory/mem0_client.py` | module-level `_PROVIDER_DEFAULT_MODELS` assignment evaluated with `ast.literal_eval` | non-empty and keys ⊆ catalog ids; extra key names the key |
| `prefixes.cover` | `llm/_providers/registry.py` | module-level `_PROVIDER_PREFIXES` assignment evaluated with `ast.literal_eval`; provider is the second tuple element | every catalog id appears as a provider value; missing id names the provider |

`--check` now renders both artifacts, keeps the byte comparisons (ADR-099 §6),
then calls `check_parity(specs, REPO_ROOT)`. Each violation is printed as
`<surface>: <detail>`; any violation or byte drift exits 1. `_check`'s
signature changed from `_check(rendered_python, rendered_typescript)` to
`_check(specs, repo_root)` and `main` is its only caller.

## RED evidence (before implementation)

Authentic RED was captured by temporarily restoring
`git show HEAD:scripts/generate_provider_catalog.py` (the implementation was
backed up to `/tmp/opencode/t6a-implemented.py`, restored afterwards, SHA-256
verified identical). The new parity test module cannot even collect:

```
collecting ... collected 0 items / 1 error

==================================== ERRORS ====================================
_ ERROR collecting tests/unit/scripts/test_generate_provider_catalog_parity.py _
ImportError while importing test module '.../tests/unit/scripts/test_generate_provider_catalog_parity.py'.
tests/unit/scripts/test_generate_provider_catalog_parity.py:14: in <module>
    from scripts.generate_provider_catalog import CATALOG_PATH, check_parity, load_catalog
E   ImportError: cannot import name 'check_parity' from 'scripts.generate_provider_catalog'
=========================== short test summary info ============================
ERROR tests/unit/scripts/test_generate_provider_catalog_parity.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.31s ===============================
```

Because the module import fails, every one of the six invariant tests is RED
for the pre-implementation tree.

## Mutation tests and “mutation applied” proof

`_sandbox` copies the four Core surface files into `tmp_path`; each test then
rewrites exactly one fact. `_mutate` asserts three things:

```python
assert old in before, f"mutation string not found in {relative}: {old!r}"
after = before.replace(old, new)
assert after != before, f"mutation did not change {relative}"
```

A stale mutation string therefore fails loudly instead of leaving a vacuous
green test. The old strings were checked against the real files; each occurs
exactly once:

```
pricing.keys   occurrences=1  '    "groq": {"input": 0.5, "output": 1.0},'
pricing.values occurrences=1  '"groq": {"input": 0.5, "output": 1.0}'
cache.arms     occurrences=1  '        case "ollama":'
cache.wildcard occurrences=1  '    match provider_name:'
cache.bodies   occurrences=1  '            return {"cache_control": True}'
mem0.keys      occurrences=1  '"ollama": "llama3.2:3b",'
mem0.empty     occurrences=1  '    "anthropic": "claude-haiku-4-20250414",'
prefixes.1     occurrences=1  '    ("ollama/", "ollama"),'
prefixes.2     occurrences=1  '    ("llama", "ollama"),'
```

| Test | Mutation | Assertion |
|---|---|---|
| `test_missing_pricing_key_is_reported` | removes the `"groq"` line from `DEFAULT_RATES` | `pricing.keys` + `groq` |
| `test_disagreeing_pricing_value_is_reported` | groq input `0.5` → `0.7` | one `pricing.values` + `groq` + both `0.5` and `0.7` |
| `test_duplicate_cache_arm_is_reported` | `case "ollama"` → `case "groq"` | `cache.arms` + `groq` + `2 match arms` |
| `test_wildcard_before_provider_arms_shadows_them` | inserts `case _: return {}` before all provider arms | `cache.arms` + `anthropic` + `shadowed` |
| `test_cache_body_disagreeing_with_policy_is_reported` | anthropic body `True` → `False` | one `cache.bodies` + `anthropic` + `True`/`False` |
| `test_unknown_mem0_key_is_reported` | `"ollama"` → `"ollamax"` | `mem0.keys` + `ollamax` |
| `test_empty_mem0_map_is_reported` | removes all four `_PROVIDER_DEFAULT_MODELS` entries | `mem0.keys` + `empty` |
| `test_provider_without_prefix_is_reported` | both `("ollama/", "ollama")` and `("llama", "ollama")` → `ollama_local` | `prefixes.cover` + `ollama` |
| `test_pristine_tree_has_no_violations` | none | `check_parity(...) == []` |

The empty-map test covers the `non-empty` half of `mem0.keys`; the extra-key
test covers the `⊆ ids` half.

## Byte comparison and drift path (T3-M1 / T1-M2)

`test_check_reports_drifted_artifact` points `PY_OUTPUT`/`TS_OUTPUT` at
`tmp_path`, writes a drifted Python artifact and a correct TypeScript artifact,
and asserts `main(["--check"]) == 1` plus the drifted file's full path and
`is stale` in stdout.

`test_check_compares_artifact_bytes_not_decoded_text` writes the Python
artifact with CRLF line endings and proves the distinction in the same test:

```python
assert python_artifact.read_text(encoding="utf-8") == rendered_python   # text view is blind
assert python_artifact.read_bytes() != rendered_python.encode("utf-8")   # bytes differ
assert generator.main(["--check"]) == 1
```

That the second assertion does not merely decorate the test was verified by
temporarily regressing `_check` to
`committed_bytes = path.read_text(encoding="utf-8").encode("utf-8")`:
the test failed with `assert 0 == 1` and the output claimed the artifact was
“up to date”. Restoring the byte read made it pass again. So a regression to
text comparison is detected by this test.

## Formatter test change (T1-M5)

**Python (now real):**
`test_rendered_python_passes_ruff_format_and_line` writes the rendered module
to `tmp_path` and runs, with the repository's `pyproject.toml` config and the
ruff binary resolved from `PATH` (present under `just test-file`):

```
ruff format --check --config <repo>/pyproject.toml <tmp>/catalog_generated.py
ruff check --no-cache --config <repo>/pyproject.toml <tmp>/catalog_generated.py
```

Both must exit 0. The previous test was renamed to
`test_rendered_python_starts_with_the_header_and_has_no_suppressions`, which
is what it actually measures.

**TypeScript (renamed, not overclaimed):**
the new `test_rendered_typescript_has_the_configured_source_shape` asserts the
emitted union indentation, `PROVIDER_IDS` entry shape, trailing comma,
`satisfies` clause and record literal — the properties the renderer controls.
Its docstring states that this is **not** formatter cleanliness and that
`just lint-frontend` (biome) is the authoritative gate; a portable Python test
cannot invoke biome.

## Raw gate output

### Gate 1 — `just test-file tests/unit/scripts/test_generate_provider_catalog.py`

```
uv run --all-packages pytest tests/unit/scripts/test_generate_provider_catalog.py -v
============================= test session starts ==============================
platform linux -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0 -- .../.venv/bin/python
...
collecting ... collected 26 items
...
tests/unit/scripts/test_generate_provider_catalog.py::test_check_prints_parity_violations_and_exits_one PASSED [ 23%]
...
tests/unit/scripts/test_generate_provider_catalog.py::test_rendered_python_passes_ruff_format_and_line PASSED [ 88%]
...
============================== 26 passed in 2.45s ==============================
```

(exit 0; full per-test list is in `/tmp/opencode/gate1.log`.)

### Gate 2 — `just test-file tests/unit/scripts/test_generate_provider_catalog_parity.py`

```
uv run --all-packages pytest tests/unit/scripts/test_generate_provider_catalog_parity.py -v
...
collecting ... collected 9 items

tests/unit/scripts/test_generate_provider_catalog_parity.py::test_pristine_tree_has_no_violations PASSED [ 11%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_disagreeing_pricing_value_is_reported PASSED [ 22%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_empty_mem0_map_is_reported PASSED [ 33%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_duplicate_cache_arm_is_reported PASSED [ 44%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_cache_body_disagreeing_with_policy_is_reported PASSED [ 55%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_wildcard_before_provider_arms_shadows_them PASSED [ 66%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_unknown_mem0_key_is_reported PASSED [ 77%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_provider_without_prefix_is_reported PASSED [ 88%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_missing_pricing_key_is_reported PASSED [100%]

============================== 9 passed in 2.35s ===============================
```

(exit 0)

### Gate 3 — `uv run --all-packages python scripts/generate_provider_catalog.py --check`

```
provider catalog check: packages/core/narrare_core/llm/_providers/catalog_generated.py is up to date
provider catalog check: packages/web/lib/providers.generated.ts is up to date
```

(exit 0)

### Gate 4 — `just lint-check`

```
uv run --all-packages ruff check apps/ packages/ scripts/ tests/ evals/
All checks passed!
uv run --all-packages ruff format --check apps/ packages/ scripts/ tests/ evals/
3372 files already formatted
```

(exit 0)

### Gate 5 — `just test-file tests/unit/core/llm/`

```
======================== 756 passed, 1 skipped in 8.32s ========================
```

(exit 0)

### Extra — scoped strict pyright

```
uv run --all-packages pyright scripts/generate_provider_catalog.py \
  tests/unit/scripts/test_generate_provider_catalog.py \
  tests/unit/scripts/test_generate_provider_catalog_parity.py
0 errors, 0 warnings, 0 informations
```

### Extra — RULE-04 Python file-size gate

```
✅ All Python files are within hard limits
Python file-size ratchet: 0 current, 0 baseline, 0 new, 0 resolved
RESULT: Python file-size debt did not grow
```

### Extra — `just check-architecture`

Exit 0 (`Frontend RULE-04 file-size check: ✅ ... debt did not grow`; no
architecture violations reported).

The first implementation reached 737 lines, over the 600-line script hard limit.
The four literal surfaces (`DEFAULT_RATES`, `_PROVIDER_DEFAULT_MODELS`,
`_PROVIDER_PREFIXES`) are now evaluated with `ast.literal_eval` instead of
hand-walking dict/list nodes, and the remaining AST helpers were tightened.
The generator is at **599 lines**; no new module was added because the task
limits changes to the generator and its two test files. This is a
data-driven evaluation change, not compressed logic: the cache `match` still
needs real AST walking for patterns and arm bodies.

## Real divergences found

**None.** The pristine tree produces no `ParityViolation` and `--check` exits
0. No surface was edited to make the gate pass.

## Carried-forward items

- **T3-M4** — both `write_text` calls for the generated artifacts now pass
  `newline="\n"`, so the byte comparison does not depend on the platform's
  default newline translation.
- **T3-M5** — `load_catalog` rejects `providers: []` with
  `ValueError("<path>: 'providers' must list at least one provider")`, before
  either renderer can emit a member-less `StrEnum` that fails to parse.
- **T3-M3 (nit)** — the `isidentifier()` guard is kept with a comment stating
  that `_ID_PATTERN` makes it unreachable today and that it remains as defense
  in depth if the pattern is relaxed.

## Concerns / what slice B still owes

- Slice B still owes six invariants and their mutations:
  `settings.fields`, `apikeys.cover` (`settings.py`), `fallback.keys`,
  `fallback.ids`, `testcall.endpoints` (`apps/api/narrare/setup/provider_service.py`),
  and `labels.locales` (`packages/i18n/messages/{en,de,fr}/settings-ai.json`).
  The slice-A sandbox copies only the four Core files; slice B must extend
  `MUTATED_FILES`.
- `cache.arms` reports catalog ids that are missing/duplicated/shadowed; it
  does not flag an arm naming a provider outside the catalog, because the
  invariant table only requires coverage of catalog ids. A stale extra arm is
  therefore not caught by this gate (it would be caught by `cache.bodies` only
  if that provider id were in the catalog).
- `mem0.keys` intentionally requires only a non-empty **subset** of catalog
  ids; providers absent from the map fall back to `_FALLBACK_MODEL` by design.
- The TypeScript artifact's formatter cleanliness remains a biome concern
  (`just lint-frontend`), not a Python-unit-test claim.
- `check_parity` assumes the four surface files exist. A renamed/deleted
  surface raises `FileNotFoundError` from the generator rather than emitting a
  `ParityViolation`. That is fail-fast and acceptable for a pre-commit gate,
  but it is not a per-surface diagnostic.
- `scripts/generate_provider_catalog.py` is at 599 lines (hard limit 600).
  Slice B must not append its six checks to this file; it needs either a
  separate module (a deliberate scope change from this slice's file list) or a
  refactor that moves the parity code out before adding more.
