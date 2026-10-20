# Throughput T14b — Intent-contract parity gate, remaining three families

- **Date:** 2026-10-20
- **Branch:** `brave-egret`
- **Base commit:** `08ccf552` (T14a)
- **Status:** implemented, verified, **not committed** (no git writes per task constraints)
- **Flywheel:** `.superpowers/sdd/2026-10-19-dev-throughput-program/task-14-brief.md`
- **Spec:** `docs/superpowers/specs/2026-10-19-dev-throughput-program-design.md` §4
- **Slice:** T14b of 2 — prompt-template existence per locale, prompt-surface-manifest
  block agreement, adoption-registry coverage. Extends the T14a seam; the five
  Python declaration surfaces and the three Python-side agreement families are
  unchanged.
- **Files authored:**
  - `scripts/check_intent_parity.py` (extended, 524 lines)
  - `tests/unit/scripts/test_check_intent_parity.py` (extended, 19 tests)
  - this report

## 1. RED evidence

The new tests were written against the T14a code first. Every new mutation test
failed on its assertion (the pre-T14b gate returns no message for the mutated
surface), so each family has a genuine behavioural RED — not a missing module:

```text
FAILED tests/unit/scripts/test_check_intent_parity.py::test_missing_prompt_template_for_a_locale_is_reported
FAILED tests/unit/scripts/test_check_intent_parity.py::test_missing_localized_prompt_template_names_that_locale
FAILED tests/unit/scripts/test_check_intent_parity.py::test_manifest_mode_mismatch_is_reported
FAILED tests/unit/scripts/test_check_intent_parity.py::test_manifest_block_missing_for_a_routed_intent_is_reported
FAILED tests/unit/scripts/test_check_intent_parity.py::test_manifest_block_for_an_unrouted_intent_is_reported
FAILED tests/unit/scripts/test_check_intent_parity.py::test_duplicate_manifest_block_is_reported
FAILED tests/unit/scripts/test_check_intent_parity.py::test_missing_adoption_registry_entry_is_reported
FAILED tests/unit/scripts/test_check_intent_parity.py::test_adoption_registry_entry_for_an_unknown_intent_is_reported
========================= 8 failed, 11 passed in 2.55s =========================
```

Representative assertion tail (prompt family):

```text
E       AssertionError: []
E       assert False
E        +  where False = any(<generator object
          test_missing_prompt_template_for_a_locale_is_reported.<locals>.<genexpr>
          at 0x...>)
```

Per-family RED: prompt templates **yes** (2 tests), manifest blocks **yes** (4
tests), adoption registry **yes** (2 tests).

## 2. What the gate reads and compares

`collect_facts` remains the single entry point. It now also reads the two
governance YAML files and the bundle, and adds four auxiliary surfaces to the
facts mapping (all still `dict[str, IntentFact]`, so the T14a shape is intact):

| Surface key | Source | Content |
|---|---|---|
| `route_context_modes` | `ROUTE_CONFIGS(...).allowed_context_modes` | one fact per `intent:mode` |
| `manifest` | `prompt-surface-manifest.yaml` `routes` | one fact per `routeable: true` block |
| `manifest_duplicates` | same | second and later block for an intent |
| `adoption_registry` | `adoption-registry.yaml` `prompt_path_compliance` | one fact per `{category}/{mode}` key |
| `prompt_dirs` | `_bundled/{category}/{locale}/{mode}/system.md` | one fact per existing `intent:locale` |

New families in `find_disagreements` (additive; each is skipped when its surface
key is absent, so the T14a synthetic-facts tests keep working unchanged):

1. **Prompt-template existence.** For every routed intent with a category and
   mode, every required locale must resolve to an existing `system.md`. One
   violation per missing file names the intent, the locale and the resolved path.
2. **Manifest block agreement.** Exactly one `routeable: true` block per routed
   intent; block `category` and `mode` must equal the route table's values
   (including `null`); a missing block, a routeable block for an unrouted intent
   and a duplicate block are violations naming the intent and the manifest.
3. **Adoption-registry coverage.** Every routed intent's default
   `{category}/{default_mode}` must be a `prompt_path_compliance` key; every
   registry key must resolve to a routed intent's default mode or one of its
   `allowed_context_modes`. Missing keys name the intent and the registry; extra
   keys name the key and the registry.

`routeable: false` manifest blocks (SENTIMENT, GENERATE, TITLE_GENERATE,
RESEARCH, CONSISTENCY_TRIAGE) stay outside the routed block set — they are the
governance declaration of an intentionally unrouted intent.

## 3. Summary line (measured, this tree)

```text
$ uv run --all-packages python scripts/check_intent_parity.py
30 intents, 24 routed, 0 disagreements
exit=0
```

## 4. Mutation captures (temporary copies, CLI exit codes)

Each tree was a copy of the five declaration files, the two governance files and
`_bundled/` under `/tmp/opencode`; the real tree was not touched.

```text
=== prompt template deleted (writing/en/new_chapter/system.md) ===
30 intents, 24 routed, 1 disagreements
WRITE: missing prompt template for locale 'en' at 'packages/core/narrare_core/prompts/_bundled/writing/en/new_chapter/system.md'
exit=1
=== manifest WRITE mode changed (new_chapter -> other_mode) ===
30 intents, 24 routed, 1 disagreements
WRITE: mode disagreement between 'route_configs' ('new_chapter') and prompt-surface-manifest.yaml ('other_mode')
exit=1
=== adoption-registry entry removed (writing/new_chapter) ===
30 intents, 24 routed, 1 disagreements
WRITE: missing entry 'writing/new_chapter' in adoption-registry.yaml
exit=1
=== adoption-registry entry added (NOT_A_REAL_INTENT) ===
30 intents, 24 routed, 1 disagreements
NOT_A_REAL_INTENT: entry in adoption-registry.yaml matches no routed intent or mode
exit=1
```

## 5. Gate tails

`just test-file tests/unit/scripts/test_check_intent_parity.py`:

```text
============================== 19 passed in 4.09s ==============================
```

`just lint-check`:

```text
All checks passed!
3382 files already formatted
exit=0
```

`just typecheck-file scripts/check_intent_parity.py tests/unit/scripts/test_check_intent_parity.py`:

```text
0 errors, 0 warnings, 0 informations
```

Proving no existing gate changed behaviour:

```text
$ uv run --all-packages python scripts/check_prompt_surface_contract.py
✅ Prompt Surface Contract OK
exit=0
$ uv run --all-packages python scripts/check_locale_sync.py
Groups checked: 50
Synced: 50
Drifted: 0
exit=0
```

## 6. Deviation and concerns

- **Locale grid is policy-driven, not the literal `en`+`de`+`fr` grid.** The task
  wording says the template must exist "for `en`, `de`, `fr`". Measured on the
  pristine tree, 22 of 22 routed feature intents have only `en` templates; the
  localized categories (`meta`, `universal`) own the `de`/`fr` variants. Requiring
  all three for every routed intent would emit 44 violations on a tree that
  `check_locale_sync.py` reports as `Drifted: 0` and that ADR-026 Phase 5 declares
  EN-only for feature prompts. The gate therefore mirrors
  `scripts/adoption/scorer._required_locales_for`: `en`+`de`+`fr` for
  `meta`/`universal`/`universal_rules`, `en` otherwise. The `de` requirement is
  still exercised: `test_missing_localized_prompt_template_names_that_locale`
  relocates WRITE into `universal` in a temp tree and asserts the missing `de`
  file is named. If the intent is a literal three-locale requirement, that is an
  ADR-026 decision to reverse, not a gate setting.
- **Registry mapping is derived, because the registry is mode-keyed.** The
  registry has no intent-keyed section; its `prompt_path_compliance` keys are
  `{category}/{mode}`. The gate maps each routed intent to its default
  `{category}/{default_mode}` and validates extra keys against the default plus
  `allowed_context_modes` universe (measured 46 required = 46 registry keys, no
  extras). A future intent-keyed registry section would need one line in
  `_registry_facts` and `_adoption_registry_disagreements`.
- **`collect_facts` now requires the manifest and registry to exist.** All
  current callers copy them (the tests and the gate itself); no other module
  imports `collect_facts`.
- The gate is still not wired into `justfile`, pre-commit or CI — that is T15, as
  the task split specifies.

## Coordinator ruling CR-7 (after independent re-measurement)

Two more spec sentences described a repo that does not exist:

- **Locale grid.** `packages/core/narrare_core/prompts/_bundled/writing/` ships `en`
  (plus `tones`), not `en`/`de`/`fr`. ADR-026's policy requires `en` for every group
  and `en`/`de`/`fr` only for meta/universal. A literal three-locale rule would emit
  44 violations on a pristine tree — i.e. it would have invented a defect. The gate
  follows the policy; the spec sentence is corrected in place.
- **Registry shape.** `adoption-registry.yaml` is keyed by prompt path
  (`prompt_path_compliance: {category}/{mode}`), not by intent: 46 entries cover the
  24 routed intents because several intents share a route. The sentence "an entry for
  every routed intent" is true only after that mapping; the spec now says so.

Both are corrections of the *document*, not relaxations of the gate: the gate checks
what the policy actually requires, and the report names the measurement.
