# Throughput T17a — intent parity sees post-literal declarations

- **Date:** 2026-10-20
- **Branch:** `brave-egret`
- **Base commit:** `0052f5da`
- **Status:** implemented, verified, **not committed** (no git writes per task constraints)
- **Review finding:** R2 — the intent parity gate cannot see a declaration added,
  changed or deleted after the dict literal.
- **Files authored:**
  - `scripts/_intent_surface_reader.py` (extended, 205 lines)
  - `scripts/check_intent_parity.py` (474 lines)
  - `tests/unit/scripts/test_check_intent_parity_post_literal.py` (new, 112 lines)
  - `tests/unit/scripts/test_intent_surface_reader.py` (new, 39 lines)
  - `docs/superpowers/plans/reports/2026-10-20-throughput-T17a.md` (this report)

## 1. Root cause

`module_assignments` returns only the `Name` targets of module-level
`Assign`/`AnnAssign` nodes. Every consumer therefore compares the dict literal
and nothing else, so
`INTENT_TO_MODE[LLMIntent.WRITE] = "other_mode"` (and `del INTENT_TO_MODE[...]`)
was invisible: the presence family never saw the entry, the key-set family never
saw the removal. T16b documented that as a "known scope limit" instead of
closing it. The declaration surfaces are ordinary module-level mappings, and the
Python semantics of a post-literal subscript write are part of their declared
value, so the reader — not the document — was wrong.

## 2. Fix

`_intent_surface_reader.dict_entries(tree, variable_name)` returns
`{key: value-node}` for a module-level mapping:

1. seed from the literal in `module_assignments(tree).get(variable_name)`
   (enum-member keys `LLMIntent.X` and string-literal keys, the
   `attribute_dict` semantics extended by string keys);
2. walk `tree.body` in source order and apply, for a single-target
   `NAME[key] = value` where `NAME` is the requested variable, the last write
   wins rule;
3. apply `del NAME[key]` as a removal.

Unrecognised key forms (`ast.Name`, expressions) are skipped exactly as the
literal reader skips them; the resulting absence is reported by the caller's
existing key-set/presence families, so no new error channel was invented. The
reader stays dependency-free, pure and well under the 600-line script limit
(205 lines).

`check_intent_parity.collect_facts` now reads all six module-level mappings
through `dict_entries`: `INTENT_CATEGORY_MAP`, `INTENT_TO_CATEGORY`,
`INTENT_TO_MODE`, `ROUTE_CONFIGS`, `NON_ROUTEABLE_INTENTS` and
`INTENT_PROFILES`. A local `_string_entries` keeps the previous
"drop non-string values" behaviour for the two string tables.

`attribute_dict` and `string_dict` remain public helpers: the scaffolder's
`_entries` still uses `attribute_dict` for literal insertion line numbers, so
neither was deleted. `string_dict` now has no caller in the repository (the
scaffolder never used it); it is kept deliberately per the task's "do not
delete public helpers on speculation".

The docstring's "known scope limit" paragraph was replaced with the new truth:
the reader applies post-literal writes and deletions in source order.

## 3. RED first — pre-fix capture

Probe script (temporary copy of the declaration tree, real `find_disagreements`):

```
1 mode override WRITE: 0 disagreements -> GREEN (missed)
2 mode entry KB_CREATE: 0 disagreements -> GREEN (missed)
3 mode delete WRITE: 0 disagreements -> GREEN (missed)
4 category override WRITE: 0 disagreements -> GREEN (missed)
```

## 4. GREEN — post-fix CLI (exit 1, one message each)

```
1 mode override WRITE: exit 1 -> WRITE: mode disagreement between 'route_intents' ('other_mode') and 'route_configs' ('new_chapter')
2 mode entry KB_CREATE: exit 1 -> KB_CREATE: present in 'INTENT_TO_MODE' surface ('create') but 'route_configs' declares no mode
3 mode delete WRITE: exit 1 -> WRITE: missing from 'INTENT_TO_MODE' surface but 'route_configs' declares mode 'new_chapter'
4 category override WRITE: exit 1 -> WRITE: category disagreement between 'route_intents' ('analysis') and 'route_configs' ('writing')
```

## 5. Tests

- `tests/unit/scripts/test_check_intent_parity.py` — 22 passed (unchanged size,
  344 lines).
- `tests/unit/scripts/test_check_intent_parity_post_literal.py` — 4 passed
  (the four mutation directions above).
- `tests/unit/scripts/test_intent_surface_reader.py` — 2 passed (reader-level:
  last write wins, deletes, string keys, unrecognised key silently skipped,
  unrelated writes ignored).
- `tests/unit/scripts/test_scaffold_feature.py` — 13 passed (the scaffolder
  shares the reader).

The four mutation tests were moved into their own module because the checker's
test file would otherwise have exceeded the RULE-04 400-line hard limit
(438 lines). The reader-level test lives in its own module for the same reason;
`test_check_intent_parity.py` stays at its original size.

## 6. Gates

- `uv run --all-packages python scripts/check_intent_parity.py` → exit 0,
  `30 intents, 24 routed, 0 disagreements`.
- `uv run --all-packages pyright scripts/_intent_surface_reader.py
  scripts/check_intent_parity.py scripts/scaffold_intent.py` → 0 errors.
- `just lint-file` on all five authored files → ruff check + format clean.
- `just check-architecture` → exit 0, no violations.
- `wc -l` → `_intent_surface_reader.py` 205, `check_intent_parity.py` 474.

## 7. Remaining concerns

None functional. The reader intentionally does not model conditional writes
(`if ...: NAME[k] = v`), loop-built entries or `update()` calls; those are not
declarations the module evaluates statically, and the gate still compares every
statically visible entry. A future surface that builds its mapping dynamically
would need its own reader, not a silent widening of this one.
