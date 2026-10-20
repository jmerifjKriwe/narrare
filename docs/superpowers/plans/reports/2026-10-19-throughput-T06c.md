# T06c — provider-catalog parity gate: i18n extraction + hardening

Date: 2026-10-19 · Branch: `brave-egret` · Base: `a93da565`

## Scope

Three files only:

- `scripts/provider_catalog_parity.py` (hardened)
- `scripts/provider_catalog_parity_i18n.py` (new, extracted i18n concern)
- `tests/unit/scripts/test_generate_provider_catalog_parity.py` (stricter `_mutate` + 7 new cases)

No parsed surface was edited. No git writes. No suppressions, no new dependencies.

## Part 1 — RULE-04 extraction (pure move)

`_I18N_DIR`, `_LOCALES`, `_load_messages`, `_contains` and the label check moved
into `scripts/provider_catalog_parity_i18n.py`. The parity module imports
`check_labels` and keeps emitting surface `labels.locales` exactly as before.

The i18n function returns `(surface, detail)` pairs and the parity module wraps
them in `ParityViolation` (`_check_labels` adapter). This keeps the dependency
one-way: `provider_catalog_parity → provider_catalog_parity_i18n`, with
`ProviderSpec` still a `TYPE_CHECKING`-only import from the generator. A direct
`ParityViolation` import in the i18n module would have created a run-time import
cycle (parity imports i18n at module load, before the class exists).

Line counts (`wc -l`, includes blanks/comments, i.e. what RULE-04 counts):

| State | parity module | i18n module |
|---|---:|---:|
| Before (HEAD) | 577 | — |
| After extraction only (pure move) | 515 | 96 |
| After hardening (final) | **576** | **96** |

The post-extraction module was 515 lines; hardening added 61 lines. The final
576 is 24 lines below the RULE-04 `script = 600` hard limit and passes the size
gate with no baseline entry for either file.

## Part 2 — robustness findings

1. **`pricing.values` coercion** — `float(actual[key])` is gone. A rate must be
   a real `int`/`float` and not `bool`; otherwise one `pricing.values`
   violation names the provider, the rate key and the offending type
   (`groq: input is str, not a number`). `DEFAULT_RATES` is cast as
   `dict[str, dict[str, object]]` so the runtime guard is not an unchecked
   assertion under a `float` cast.
2. **`_value` last-wins** — the helper keeps the **last** module-level binding
   (a bare annotation binds nothing and does not reset it), matching run-time
   semantics. Checked against the current tree: each governed name
   (`DEFAULT_RATES`, `_PROVIDER_DEFAULT_MODELS`, `_PROVIDER_PREFIXES`,
   `_FALLBACK_MODELS`) has exactly **one** binding, so no Core surface changes
   behaviour; `--check` and the generator tests stay green.
3. **`_check_prefixes` structural safety** — a non-list anchor now returns
   exactly **one** violation (`_PROVIDER_PREFIXES must be a list, got …`)
   instead of seven misleading `<id>: no entry` details. Elements are inspected
   without unpacking: a malformed entry (3-tuple, non-string, non-tuple) is
   skipped for coverage and reported once as
   `<entry>: not a (prefix, provider) pair`; it can no longer raise
   `ValueError` inside the gate.
4. **`Annotated[...]` aliases** — `_class_annotations` now keeps
   `(annotation, assignment)` per field. `_field_call` reads a `Field(...)`
   assignment *or* `Field(...)` metadata inside an `Annotated` subscript
   (tuple slice, direct slice tolerated), and `_env_var` honours its
   `validation_alias`/`alias`. A field declared as
   `Annotated[str | None, Field(validation_alias="GROQ_KEY")] = None` is now
   checked against `GROQ_KEY`, not the assumed upper-cased default. No such
   field exists on the current tree; this prevents the gate from assuming a
   name it has not verified.
5. **`testcall.endpoints`** — the scanner locates `class ProviderService` in
   `module.body`, then its own `_test_call` method, and walks only that body
   (nested functions, lambdas and classes are skipped). Only `If`/`IfExp`
   **test** expressions contribute compares. A nested helper, comprehension
   filter, `assert`, or an earlier module-level look-alike named `_test_call`
   can no longer satisfy the gate, and a rename of the real method is loud.
6. **`_contains` leaf type** — the leaf must be a **non-empty string**.
   `None`, objects, numbers, booleans and `""` no longer count as a resolved
   label (RULE-16: these are translatable strings). The docstring says so.
7. **`fallback.keys` structural wording** — the `**` problem now reads
   `_FALLBACK_MODELS: '**' unpacking leaves its keys unverified`, and a
   non-`AIProvider` key reads `_FALLBACK_MODELS key '<key>' is not
   AIProvider.<MEMBER>`. Both name the offending syntax/key explicitly. The
   `check_parity` docstring no longer claims every violation names a provider:
   provider facts name the provider, structural facts name the anchor or key.

## Part 3 — tests

`_mutate` now asserts `before.count(old) == 1` and calls `replace(old, new, 1)`,
so a doubled fragment cannot silently mutate two places.

New coverage (one focused case per hardening):

| Test | Proves |
|---|---|
| `test_catalog_api_key_without_settings_field_is_reported` | catalog `api_key_env` + `settings_field: null` → `apikeys.cover` |
| `test_non_numeric_pricing_value_is_reported` | `"0.5"` → one `pricing.values` naming provider/type |
| `test_non_list_prefix_anchor_is_one_structural_violation` | tuple anchor → exactly one `prefixes.cover`, not seven |
| `test_label_key_without_a_dot_is_reported` | `label_key="settings-ai"` → `labels.locales` structural detail |
| `test_annotated_validation_alias_is_honoured` (parametrized) | correct `Annotated` alias passes; wrong alias fails (before the fix the wrong alias was silently accepted as the default name) |
| `test_last_fallback_assignment_wins` | a second `_FALLBACK_MODELS = {}` shadows the first; `groq` is reported missing |

The file was compacted (helper reuse for all direct `check_parity` tests) from
472 to **368** lines so it stays under the RULE-04 `test = 400` hard limit while
keeping all 24 original cases green. Total: **31 passed**.

## Gates (raw output)

### 1. Parity tests

```
$ just test-file tests/unit/scripts/test_generate_provider_catalog_parity.py
...
============================== 31 passed in 2.64s ==============================
```

### 2. Generator tests

```
$ just test-file tests/unit/scripts/test_generate_provider_catalog.py
...
============================== 26 passed in 2.41s ==============================
```

### 3. Generator `--check`

```
$ uv run --all-packages python scripts/generate_provider_catalog.py --check
provider catalog check: packages/core/narrare_core/llm/_providers/catalog_generated.py is up to date
provider catalog check: packages/web/lib/providers.generated.ts is up to date
exit=0
```

### 4. Lint + strict pyright

```
$ just lint-check
uv run --all-packages ruff check apps/ packages/ scripts/ tests/ evals/
All checks passed!
uv run --all-packages ruff format --check apps/ packages/ scripts/ tests/ evals/
3374 files already formatted
```

```
$ just typecheck-file scripts/provider_catalog_parity.py \
    scripts/provider_catalog_parity_i18n.py \
    tests/unit/scripts/test_generate_provider_catalog_parity.py
0 errors, 0 warnings, 0 informations
0 errors, 0 warnings, 0 informations
```

(The first line is strict root config for the two scripts; the second is the
basic tests config.)

### 5. RULE-04 size gate

```
$ uv run --all-packages python scripts/check_python_file_size.py
Python RULE-04 file-size check
==================================
✅ All Python files are within hard limits
Python file-size ratchet: 0 current, 0 baseline, 0 new, 0 resolved
RESULT: Python file-size debt did not grow
```

```
$ wc -l scripts/provider_catalog_parity.py scripts/provider_catalog_parity_i18n.py \
    tests/unit/scripts/test_generate_provider_catalog_parity.py
  576 scripts/provider_catalog_parity.py
   96 scripts/provider_catalog_parity_i18n.py
  368 tests/unit/scripts/test_generate_provider_catalog_parity.py
```

Architecture gate also run: `just check-architecture` → exit 0.

## Real divergences

None. `_value` last-wins and the `Annotated` alias reader were checked against
the current surfaces; every governed table has one binding and no provider
field uses `Annotated` today, so the gate's output on the pristine tree is
unchanged (`test_pristine_tree_has_no_violations`).

## Concerns

- The i18n module is 96 lines (module docstring + 5 moved items + the
  `(surface, detail)` boundary). It is well under the `script = 600` limit.
- `_check_prefixes` reports malformed elements rather than dropping them
  silently. The brief said "skip malformed elements"; they are skipped for
  coverage, but RULE-11 (no silent failures) is why each malformed element is
  still one explicit structural violation. This does not affect the non-list
  anchor case, which returns exactly one violation.
- `_value` ignores a later bare annotation (`X: int`) because it does not bind
  a value at run time; the last *binding* wins.
