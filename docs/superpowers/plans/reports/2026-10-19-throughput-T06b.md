# Throughput T06b — Provider-catalog parity gate (API + i18n slice)

**Date:** 2026-10-19
**Branch:** `brave-egret` (base `f847948e`)
**Scope:** Task 6, slice B — the six remaining parity invariants: the two
`CoreSettings` surfaces, the three `provider_service.py` surfaces and the i18n
label surface. The gate module and its four Core invariants already existed
(T06a/T06a2); this slice only adds invariants to them.

No production surface was edited. No git writes were performed. The nine T6a
review Minors and the generator's `ParityViolation` re-export are untouched
(T6c).

## Files changed

- `scripts/provider_catalog_parity.py` — six checkers
  (`_check_settings`, `_check_api_keys`, `_check_fallbacks`, `_check_test_call`,
  `_check_labels`) plus the helpers they share
  (`_class_annotations`, `_env_var`, `_provider_member`, `_fallback_entries`,
  `_model_ids`, `_test_call_providers`, `_load_messages`, `_contains`), the
  surface-file constants, and the `check_parity` dispatch + docstring.
- `tests/unit/scripts/test_generate_provider_catalog_parity.py` — sandbox
  extended to nine files, 13 new test functions (16 parametrised cases), the
  `_details`/`_naming` assertion helpers.

Only `ast`, `json` and `pathlib` were added to the imports; no dependency and no
suppression.

## Invariants implemented (6)

All parsing stays AST-only for Python and `json` for messages; nothing is
imported. `check_parity` is still a pure function of `(specs, repo_root)`,
returns one `ParityViolation` per fact, sorted by `(surface, detail)`, and every
`detail` starts with the provider id (plus the expected/actual pair where one
exists).

| Surface | Anchor | How it is parsed | Assertion |
|---|---|---|---|
| `settings.fields` | `settings.py` → module-level `class CoreSettings` | its `AnnAssign` targets give the field names; their right-hand side is inspected for a declared alias | every non-null `settings_field` is declared, and the env var it reads equals `api_key_env` |
| `apikeys.cover` | same | same parse | every non-null `api_key_env` has a declared field (`settings_field` names one) |
| `fallback.keys` | `provider_service.py` → module-level `_FALLBACK_MODELS` | `ast.Dict` keys rendered as `AIProvider.<MEMBER>` → lower-cased id | key set == catalog ids |
| `fallback.ids` | same | each value must be an `ast.List` of `Call(Name("ProviderModel"), id=<str constant>)` | per-provider id sequence == `fallback_models` |
| `testcall.endpoints` | same → `_test_call` | `ast.walk` over the function, collecting every `Compare` operand shaped `AIProvider.<MEMBER>` | a branch exists for every provider with `requires_endpoint_selector: true` |
| `labels.locales` | `packages/i18n/messages/{en,de,fr}/settings-ai.json` | key split at the first `.`: stem = file, rest = nested path; `json.loads` per file (cached per locale/stem) | every `label_key` resolves in all three locales |

### Env-var resolution (`settings.fields`)

A field's env var is resolved from **declared** sources only:

1. a `validation_alias="…"` keyword on its `Field(...)` call,
2. else `alias="…"`,
3. else the field name upper-cased (pydantic-settings' default).

Only string-literal aliases are evaluable. A field that declares a non-literal
alias (`AliasChoices(...)`, a bare name) yields a violation
(`… declares an alias this gate cannot evaluate`) rather than assuming the
default name — an unknown env var is never treated as a match. The catalog
comment on `google` that calls `gemini_api_key` an accepted alias is **not** a
declaration, so it plays no part: `google` resolves through its declared
`google_api_key` field, which upper-cases to `GOOGLE_API_KEY`, the catalog's
`api_key_env`.

### Division between the two settings surfaces

`apikeys.cover` is existence only; `settings.fields` owns env-var equality.
A field that exists but reads the wrong env var is therefore reported exactly
once, by `settings.fields`; a missing field is reported by both, and an
`api_key_env` with no `settings_field` in the catalog is reported only by
`apikeys.cover`.

### Behaviour on a missing / malformed anchor

| Surface | Anchor absent, renamed or the wrong node shape | Surface file missing / unparsable |
|---|---|---|
| `settings.fields` | class absent → one violation **per provider with a field**: `<id>: CoreSettings is missing from packages/core/narrare_core/settings.py`; field absent → `<id>: <field> is not declared in CoreSettings` | `read_text`/`ast.parse` raises out of `check_parity` → non-zero exit with a traceback (same fail-fast contract as T06a's four Core surfaces) |
| `apikeys.cover` | class absent or field absent → `<id>: no declared CoreSettings field named <field>`; catalog has `api_key_env` but no `settings_field` → `<id>: <ENV> has no settings_field in the catalog` | as above |
| `fallback.keys` | assignment absent or not an `ast.Dict` → one violation per catalog provider: `<id>: _FALLBACK_MODELS is not a dict literal in apps/api/narrare/setup/provider_service.py`; a key that is not `AIProvider.<MEMBER>` → `<unparsed>: is not an AIProvider.<MEMBER> key`; `**` unpacking and duplicate keys are reported too | raises out (as above) |
| `fallback.ids` | when the table itself is absent it stays silent **by design** — `fallback.keys` has already failed on the same anchor and the gate exits 1, so nothing is silently green. When a *value* is not the expected list shape → `<id>: fallback list is not a list of ProviderModel(id=...)`; a partial scan is never compared against a truncated set | raises out (as above) |
| `testcall.endpoints` | function absent (including renamed) → `<id>: _test_call is missing from …` for every endpoint-selector provider; function present but no comparison for that id → `<id>: no branch in _test_call handles its endpoint selector` | raises out (as above) |
| `labels.locales` | **every** failure is a violation naming the provider: file unreadable → `<id>: <rel-path> cannot be read (No such file or directory)`; decode/JSON error → `<id>: <rel-path> is not valid UTF-8 JSON (…)`; non-object document → `<id>: <rel-path> is not a JSON object`; absent path (or `null` leaf) → `<id>: <label_key> missing in <rel-path>`; key without a dot → `<id>: label_key <key> is not a <file>.<path> key` | reported as violations (never a pass) |

The i18n surface never imports, and never returns `[]` because a file or a path
is absent: a missing file, a malformed JSON and an absent nested path each
produce a violation per provider (per affected locale).

## RED evidence (before implementation)

The 13 new test functions were written first and run against the unmodified
module (all four Core checkers only). Authentic RED: the new invariants did not
exist, so each mutation produced no violation and each assertion failed. The
pristine test passed at that point because the tree is consistent (expected —
it is the pre-implementation baseline). Raw tail:

```
=========================== short test summary info ============================
FAILED tests/unit/scripts/test_generate_provider_catalog_parity.py::test_settings_field_with_unevaluable_alias_is_reported
FAILED tests/unit/scripts/test_generate_provider_catalog_parity.py::test_missing_fallback_provider_is_reported
FAILED tests/unit/scripts/test_generate_provider_catalog_parity.py::test_absent_fallback_table_is_reported
FAILED tests/unit/scripts/test_generate_provider_catalog_parity.py::test_settings_field_with_wrong_env_var_is_reported
FAILED tests/unit/scripts/test_generate_provider_catalog_parity.py::test_undeclared_settings_field_is_reported
FAILED tests/unit/scripts/test_generate_provider_catalog_parity.py::test_api_key_env_without_declared_field_is_reported
FAILED tests/unit/scripts/test_generate_provider_catalog_parity.py::test_label_key_missing_in_a_locale_is_reported[de]
FAILED tests/unit/scripts/test_generate_provider_catalog_parity.py::test_label_key_missing_in_a_locale_is_reported[fr]
FAILED tests/unit/scripts/test_generate_provider_catalog_parity.py::test_absent_test_call_is_reported
FAILED tests/unit/scripts/test_generate_provider_catalog_parity.py::test_label_key_missing_in_a_locale_is_reported[en]
FAILED tests/unit/scripts/test_generate_provider_catalog_parity.py::test_disagreeing_fallback_model_id_is_reported
FAILED tests/unit/scripts/test_generate_provider_catalog_parity.py::test_absent_locale_file_is_reported
FAILED tests/unit/scripts/test_generate_provider_catalog_parity.py::test_malformed_locale_file_is_reported
FAILED tests/unit/scripts/test_generate_provider_catalog_parity.py::test_absent_settings_class_is_reported
FAILED tests/unit/scripts/test_generate_provider_catalog_parity.py::test_endpoint_selector_provider_without_test_call_branch_is_reported
========================= 15 failed, 9 passed in 2.72s ==========================
```

15 = 12 test functions + 3 locale parametrisations (the 9 passes are the 8
pre-existing tests plus the pristine test).

## Mutation tests and "mutation applied" proof

`_sandbox` now copies nine files (`MUTATED_FILES`: the four Core surfaces,
`settings.py`, `provider_service.py` and the three locale files). Every test
still calls `_mutate`, which asserts the old string is present and that the file
changed, so a stale mutation string fails instead of leaving a vacuous green
test. Each new mutation string was counted in the real file — **all 13 occur
exactly once**:

```
settings.anthropic_field   occurrences=1   settings.groq_field   occurrences=1
settings.zai_field         occurrences=1   settings.class        occurrences=1
settings.openai_field      occurrences=1   fallback.groq_key     occurrences=1
fallback.table             occurrences=1   fallback.model_id     occurrences=1
testcall.ollama            occurrences=1   testcall.def          occurrences=1
labels.en                  occurrences=1   labels.de             occurrences=1
labels.fr                  occurrences=1
```

| Test | Mutation | Asserted |
|---|---|---|
| `test_undeclared_settings_field_is_reported` | removes `anthropic_api_key` | `settings.fields` + `anthropic` + `not declared` |
| `test_settings_field_with_wrong_env_var_is_reported` | `groq_api_key` gets `Field(validation_alias="GROQ_KEY")` | exactly one `settings.fields` naming `groq`, containing both `GROQ_KEY` and `GROQ_API_KEY` |
| `test_settings_field_with_unevaluable_alias_is_reported` | `zai_api_key` gets `validation_alias=ALIAS` (non-literal) | `settings.fields` + `zai` + `cannot evaluate` |
| `test_absent_settings_class_is_reported` | `class CoreSettings` → `class Renamed` | `settings.fields` + `anthropic` + `CoreSettings`, **and** `apikeys.cover` + `anthropic` |
| `test_api_key_env_without_declared_field_is_reported` | removes `openai_api_key` | `apikeys.cover` + `openai` + `openai_api_key` |
| `test_missing_fallback_provider_is_reported` | `AIProvider.GROQ:` → `AIProvider.PERPLEXITY:` | `fallback.keys` + `groq` + `missing`, **and** `perplexity` + `extra` |
| `test_absent_fallback_table_is_reported` | `_FALLBACK_MODELS` → `_RENAMED_FALLBACK_MODELS` | `fallback.keys` + `anthropic` + `_FALLBACK_MODELS` + `not a dict literal` |
| `test_disagreeing_fallback_model_id_is_reported` | `llama-3.3-70b-versatile` → `llama-3.1-70b-versatile` | exactly one `fallback.ids` naming `groq`, containing both ids |
| `test_endpoint_selector_provider_without_test_call_branch_is_reported` | `elif provider == AIProvider.OLLAMA:` → `…OLLAMA_CLOUD:` | `testcall.endpoints` + `ollama`; **and** no `zai` violation (the untouched provider stays green) |
| `test_absent_test_call_is_reported` | `async def _test_call(` → `async def _renamed_call(` | `testcall.endpoints` naming both `ollama` and `zai`, each mentioning `_test_call` |
| `test_label_key_missing_in_a_locale_is_reported[en/de/fr]` | `"zai"` → `"zaii"` in **that** locale only | `labels.locales` + `zai` + `messages/<locale>/` |
| `test_absent_locale_file_is_reported` | deletes `fr/settings-ai.json` | `labels.locales` + `anthropic` + `messages/fr/` |
| `test_malformed_locale_file_is_reported` | writes `{"providers": {` into `de/settings-ai.json` | `labels.locales` + `groq` + `messages/de/` + `not valid UTF-8 JSON` |
| `test_pristine_tree_has_no_violations` | none | `check_parity(...) == []` over **all twelve** invariants |

The locale invariant is parametrised over `en`, `de`, `fr` because "resolves in
all three" is the point: a test that only broke `en` would not notice a missing
`fr` key. The three anchor tests (absent class, absent table, absent function,
absent file, malformed JSON) exist because a scanner that silently returns `[]`
on an unreadable anchor is worse than no gate.

## Two bugs the new tests caught during implementation

1. **`_test_call` is an `async def` method, not a module-level `def`.** The first
   `_test_call_providers` searched `module.body` for `ast.FunctionDef`; it found
   nothing, so the pristine test failed with two `testcall.endpoints`
   violations. The anchor test and the pristine test caught it immediately; the
   lookup is now `ast.walk` accepting both function node types.
2. **Leaf resolution in `_contains`.** A pyright-driven rewrite briefly required
   *every* path segment to be a mapping, including the label leaf (a string),
   which made all 21 label checks fail. The pristine test and Gate 3 (`--check`
   printed 21 `labels.locales` violations) caught it; the final implementation
   re-checks the shape at each step and treats a `null` leaf as absent.

Both were regression-checked: after the fix, Gate 1 and Gate 3 are green again.

## Raw gate output

### Gate 1 — `just test-file tests/unit/scripts/test_generate_provider_catalog_parity.py`

```
collecting ... collected 24 items

tests/unit/scripts/test_generate_provider_catalog_parity.py::test_unknown_mem0_key_is_reported PASSED [  4%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_label_key_missing_in_a_locale_is_reported[en] PASSED [  8%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_pristine_tree_has_no_violations PASSED [ 12%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_absent_test_call_is_reported PASSED [ 16%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_api_key_env_without_declared_field_is_reported PASSED [ 20%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_settings_field_with_unevaluable_alias_is_reported PASSED [ 25%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_absent_fallback_table_is_reported PASSED [ 29%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_duplicate_cache_arm_is_reported PASSED [ 33%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_endpoint_selector_provider_without_test_call_branch_is_reported PASSED [ 37%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_absent_settings_class_is_reported PASSED [ 41%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_empty_mem0_map_is_reported PASSED [ 45%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_undeclared_settings_field_is_reported PASSED [ 50%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_disagreeing_pricing_value_is_reported PASSED [ 54%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_cache_body_disagreeing_with_policy_is_reported PASSED [ 58%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_settings_field_with_wrong_env_var_is_reported PASSED [ 62%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_malformed_locale_file_is_reported PASSED [ 66%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_absent_locale_file_is_reported PASSED [ 70%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_wildcard_before_provider_arms_shadows_them PASSED [ 75%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_missing_fallback_provider_is_reported PASSED [ 79%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_disagreeing_fallback_model_id_is_reported PASSED [ 83%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_label_key_missing_in_a_locale_is_reported[fr] PASSED [ 87%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_provider_without_prefix_is_reported PASSED [ 91%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_label_key_missing_in_a_locale_is_reported[de] PASSED [ 95%]
tests/unit/scripts/test_generate_provider_catalog_parity.py::test_missing_pricing_key_is_reported PASSED [100%]

============================== 24 passed in 2.66s ==============================
```

(exit 0)

### Gate 2 — `just test-file tests/unit/scripts/test_generate_provider_catalog.py`

```
collecting ... collected 26 items

tests/unit/scripts/test_generate_provider_catalog.py::test_load_catalog_rejects_invalid_documents[providers: nope\n-must be a list] PASSED [  3%]
tests/unit/scripts/test_generate_provider_catalog.py::test_committed_python_artifact_matches_a_fresh_render PASSED [  7%]
tests/unit/scripts/test_generate_provider_catalog.py::test_check_reports_drifted_artifact PASSED [ 11%]
tests/unit/scripts/test_generate_provider_catalog.py::test_load_catalog_rejects_invalid_documents[…unknown field] PASSED [ 15%]
tests/unit/scripts/test_generate_provider_catalog.py::test_load_catalog_rejects_invalid_documents[…'output' must be a number] PASSED [ 19%]
tests/unit/scripts/test_generate_provider_catalog.py::test_rendered_python_declares_class_syntax_strenum PASSED [ 23%]
tests/unit/scripts/test_generate_provider_catalog.py::test_renderers_escape_hostile_label_keys PASSED [ 26%]
tests/unit/scripts/test_generate_provider_catalog.py::test_check_compares_artifact_bytes_not_decoded_text PASSED [ 30%]
tests/unit/scripts/test_generate_provider_catalog.py::test_catalog_lists_the_seven_providers_in_canonical_order PASSED [ 34%]
tests/unit/scripts/test_generate_provider_catalog.py::test_rendered_python_starts_with_the_header_and_has_no_suppressions PASSED [ 38%]
tests/unit/scripts/test_generate_provider_catalog.py::test_check_prints_parity_violations_and_exits_one PASSED [ 42%]
tests/unit/scripts/test_generate_provider_catalog.py::test_load_catalog_rejects_invalid_documents[…missing field] PASSED [ 46%]
tests/unit/scripts/test_generate_provider_catalog.py::test_load_catalog_rejects_id_without_a_leading_letter PASSED [ 50%]
tests/unit/scripts/test_generate_provider_catalog.py::test_load_catalog_rejects_invalid_documents[[]\n-expected a mapping] PASSED [ 53%]
tests/unit/scripts/test_generate_provider_catalog.py::test_load_catalog_rejects_invalid_documents[…unknown rate] PASSED [ 57%]
tests/unit/scripts/test_generate_provider_catalog.py::test_load_catalog_rejects_invalid_documents[…at least one fallback model] PASSED [ 61%]
tests/unit/scripts/test_generate_provider_catalog.py::test_rendered_python_passes_ruff_format_and_line PASSED [ 65%]
tests/unit/scripts/test_generate_provider_catalog.py::test_load_catalog_rejects_invalid_documents[…must match] PASSED [ 69%]
tests/unit/scripts/test_generate_provider_catalog.py::test_load_catalog_rejects_invalid_documents[…not one of] PASSED [ 73%]
tests/unit/scripts/test_generate_provider_catalog.py::test_load_catalog_rejects_invalid_documents[…expected a non-empty string or null] PASSED [ 76%]
tests/unit/scripts/test_generate_provider_catalog.py::test_load_catalog_rejects_invalid_documents[…duplicate provider id] PASSED [ 80%]
tests/unit/scripts/test_generate_provider_catalog.py::test_load_catalog_rejects_invalid_documents[providers: []\n-at least one provider] PASSED [ 84%]
tests/unit/scripts/test_generate_provider_catalog.py::test_load_catalog_rejects_invalid_documents[…not one of] PASSED [ 88%]
tests/unit/scripts/test_generate_provider_catalog.py::test_committed_typescript_artifact_matches_a_fresh_render PASSED [ 92%]
tests/unit/scripts/test_generate_provider_catalog.py::test_rendered_typescript_has_the_configured_source_shape PASSED [ 96%]
tests/unit/scripts/test_generate_provider_catalog.py::test_load_catalog_rejects_invalid_documents[…expected a boolean] PASSED [100%]

============================== 26 passed in 2.41s ==============================
```

(exit 0; the `[…]` elisions are only in the long `-v` parametrised ids —
the run itself printed them in full)

### Gate 3 — `uv run --all-packages python scripts/generate_provider_catalog.py --check`

```
provider catalog check: packages/core/narrare_core/llm/_providers/catalog_generated.py is up to date
provider catalog check: packages/web/lib/providers.generated.ts is up to date
```

(exit 0 — no `surface: detail` line, i.e. all twelve invariants are clean on the
committed tree)

### Gate 4 — `just lint-check`

```
uv run --all-packages ruff check apps/ packages/ scripts/ tests/ evals/
All checks passed!
uv run --all-packages ruff format --check apps/ packages/ scripts/ tests/ evals/
3373 files already formatted
```

(exit 0)

### Gate 4 (continued) — strict pyright on the changed files

```
uv run --all-packages pyright scripts/provider_catalog_parity.py \
  tests/unit/scripts/test_generate_provider_catalog_parity.py
0 errors, 0 warnings, 0 informations
0 errors, 0 warnings, 0 informations
```

(`just typecheck-file scripts/provider_catalog_parity.py
tests/unit/scripts/test_generate_provider_catalog_parity.py`, exit 0; the parity
module is checked against the strict root config, the test file against
`tests/pyrightconfig.json`.)

### Gate 5 — RULE-04 size gate

```
📏 Checking Python file-size limits...
uv run --all-packages python scripts/check_python_file_size.py
Python RULE-04 file-size check
==================================
✅ All Python files are within hard limits
Python file-size ratchet: 0 current, 0 baseline, 0 new, 0 resolved
RESULT: Python file-size debt did not grow
```

(exit 0)
**`scripts/provider_catalog_parity.py` = 577 lines** (script hard limit 600;
224 at the base). The test module is 359 lines (test hard limit 400 — an
earlier draft reached 428 and was compacted with the `_details`/`_naming`
helpers; no test was dropped).

### Extra — `just check-architecture`

```
✅ Architecture constraints OK (3361 files checked, 13 approved exception(s))
```

(exit 0; not part of this task's gate list, run as a self-check)

## Real divergences found

**None.** Gate 3 exits 0 and `test_pristine_tree_has_no_violations` passes, so
all twelve invariants are satisfied by the committed tree. No surface was edited
to make the gate pass, and no catalog value was changed.

## Concerns

- **`scripts/provider_catalog_parity.py` is at 577/600 lines** — 23 lines of
  headroom. The module now carries ten checkers and their helpers; T6c's removal
  of the generator re-export does not affect this file, so any further invariant
  would need an extraction (e.g. the i18n check into its own module) rather than
  another append.
- **A missing or unparsable *surface file*** (as opposed to a missing anchor
  inside an existing file) still raises out of `check_parity`
  (`FileNotFoundError`/`SyntaxError`, non-zero exit, traceback) for
  `settings.py` and `provider_service.py`, exactly as T06a's four Core surfaces
  do. That is fail-fast, not fail-silent, but it is not a per-surface
  diagnostic; making `_parse` fail-soft would change T06a's four invariants too,
  so it was left out of this slice.
- **`testcall.endpoints` checks branch *existence*, not branch semantics**: a
  branch that compares the provider but ignores `zai_endpoint` still passes.
  That matches the invariant table; behavioural coverage of the selector lives
  in the setup-wizard tests.
- **`fallback.ids` is silent when the whole table is missing** (see the table
  above): the gate still exits 1 through `fallback.keys`, so no fact passes, but
  a reader of the output sees one surface report the anchor rather than two.
- **`labels.locales` treats a `null` leaf as absent.** That is deliberate (a
  null is not a translatable label) but it means a locale file with
  `"zai": null` reports a missing key rather than a type error.
- `_check_settings` and `_check_api_keys` each parse `settings.py` once; at
  ~40 ms per run for nine surfaces this is not worth a shared parse cache, but
  it is the obvious lever if the hook ever needs to be faster.
- The nine T06a review Minors and the generator's `ParityViolation` re-export
  remain open, by mandate (T6c).
