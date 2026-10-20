# Throughput T14c — Intent-contract parity gate, lookup-table presence

- **Date:** 2026-10-20
- **Branch:** `brave-egret`
- **Base commit:** `79b78e61` (T13 docs)
- **Status:** implemented, verified, **not committed** (no git writes per task constraints)
- **Flywheel:** T14c follow-up to `2026-10-19-throughput-T14a.md` / `-T14b.md`
- **Slice:** close the measured gap in the mode-agreement family — a deleted
  `INTENT_TO_MODE` entry was invisible because `route_intents` merges the two
  lookup tables as a key union and `_agreement` skips `None` values.
- **Files authored:**
  - `scripts/check_intent_parity.py` (extended, 463 lines)
  - `tests/unit/scripts/test_check_intent_parity.py` (extended, 22 tests)
  - this report

## 1. The invariant (measured, not guessed)

On the real tree, `INTENT_TO_CATEGORY` has 24 entries and `INTENT_TO_MODE` has
22. Exactly two routed intents have no mode entry — `KB_CREATE` and `EXTRACT` —
and both declare `ROUTE_CONFIGS[i].default_mode is None`. Every other routed
intent has a mode entry and a non-`None` default mode. Therefore:

1. an `INTENT_TO_MODE` entry exists **exactly when** the route table's
   `default_mode` is not `None`;
2. where both exist, the values agree (already checked by `_agreement`);
3. an absent entry with a non-`None` default mode is a disagreement;
4. an entry where `default_mode is None` is a disagreement.

The same class of gap existed for `INTENT_TO_CATEGORY` (every routed intent has
a category entry and every route config a category), so the presence check is
applied to both tables. Fixing only mode would have left the identical bug in
the category surface.

## 2. RED evidence

The three new tests were written before the fix. All three failed on the
pre-T14c gate, each because the mutation produced no message:

```text
FAILED tests/unit/scripts/test_check_intent_parity.py::test_deleting_a_mode_entry_is_reported
FAILED tests/unit/scripts/test_check_intent_parity.py::test_deleting_a_category_entry_is_reported
FAILED tests/unit/scripts/test_check_intent_parity.py::test_adding_a_mode_entry_where_the_route_config_has_none_is_reported
========================= 3 failed, 19 passed in 5.00s =========================
```

Representative tail:

```text
E       AssertionError: []
E       assert False
```

## 3. Implementation

`collect_facts` keeps the merged `route_intents` fact (used by key-set identity)
and adds two explicit presence surfaces, all still `dict[str, IntentFact]`:

| Surface key | Source | Content |
|---|---|---|
| `intent_to_category` | `INTENT_TO_CATEGORY` | one fact per entry present in the table |
| `intent_to_mode` | `INTENT_TO_MODE` | one fact per entry present in the table |

`_presence_disagreements(facts, surface, field, label)` compares, per routed
intent, the *existence* of the lookup entry against the route table value:

- `default_mode` not `None` and entry absent → `missing from 'INTENT_TO_MODE'
  surface but 'route_configs' declares mode '<value>'`;
- `default_mode` `None` and entry present → `present in 'INTENT_TO_MODE'
  surface ('<value>') but 'route_configs' declares no mode`.

Entries for intents that have no route config at all stay with the existing
key-set family, so no intent is reported twice for the same fact. The family is
skipped when the presence surface key is absent, matching the T14b precedent,
so the T14a synthetic-facts tests keep working unchanged.

## 4. Summary line (measured, this tree)

```text
$ uv run --all-packages python scripts/check_intent_parity.py
30 intents, 24 routed, 0 disagreements
exit=0
```

## 5. Mutation captures (temporary copies, CLI exit codes)

Each tree was a copy of the five declaration files, the two governance files and
the routed EN prompt templates; the real tree was not touched.

```text
--- deleted_mode_entry ---
30 intents, 24 routed, 1 disagreements
WRITE: missing from 'INTENT_TO_MODE' surface but 'route_configs' declares mode 'new_chapter'
exit=1
--- extra_mode_entry ---
30 intents, 24 routed, 1 disagreements
KB_CREATE: present in 'INTENT_TO_MODE' surface ('create') but 'route_configs' declares no mode
exit=1
```

## 6. Gate tails

`just test-file tests/unit/scripts/test_check_intent_parity.py`:

```text
============================== 22 passed in 4.63s ==============================
```

`uv run --all-packages pyright scripts/check_intent_parity.py scripts/_intent_surface_reader.py`:

```text
0 errors, 0 warnings, 0 informations
```

`just check-architecture`: exit 0 (intent-parity, RULE-04 service/frontend
sizes and every other gate green).

`just lint-file scripts/check_intent_parity.py tests/unit/scripts/test_check_intent_parity.py`:

```text
All checks passed!
2 files already formatted
```

`wc -l scripts/check_intent_parity.py`:

```text
463
```

## 7. Concerns

- **The presence family is keyed off `route_configs`, not `enums`.** For an
  intent that appears in a lookup table but not in `ROUTE_CONFIGS`, the key-set
  family reports the missing route config; the presence family deliberately does
  not add a second message. This keeps one fact, one message.
- **Synthetic-facts guard.** Like the T14b families, presence is skipped when
  `intent_to_category`/`intent_to_mode` are absent from the facts mapping.
  Production `collect_facts` always populates both; the guard exists so the
  T14a hand-built facts fixtures stay a subset rather than a second contract.
- **T15 wiring untouched.** `.github/workflows/ci.yml`, `.pre-commit-config.yaml`
  and `justfile` remain as T15 left them; the gate is exercised only through the
  existing `just check-architecture` path and the test file.
