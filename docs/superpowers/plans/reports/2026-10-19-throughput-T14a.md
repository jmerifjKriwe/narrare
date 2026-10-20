# Throughput T14a — Intent-contract parity gate, first slice

- **Date:** 2026-10-20
- **Branch:** `brave-egret`
- **Base commit:** `db48bbe3`
- **Status:** implemented, verified, **not committed** (no git writes per task constraints)
- **Flywheel:** `.superpowers/sdd/2026-10-19-dev-throughput-program/task-14-brief.md`
- **Spec:** `docs/superpowers/specs/2026-10-19-dev-throughput-program-design.md` §4
- **Slice:** T14a of 2 — the six Python declaration surfaces and the three
  Python-side agreement families. T14b (prompt-directory existence per locale,
  manifest-block agreement, adoption-registry coverage) is deliberately absent.
- **Files authored:**
  - `scripts/check_intent_parity.py` (new, 323 lines / 222 non-blank non-comment)
  - `tests/unit/scripts/test_check_intent_parity.py` (new, 8 tests)
  - this report

## 1. RED evidence

The five brief tests and the three mutation tests were written before the script.
The first run failed at collection:

```text
tests/unit/scripts/test_check_intent_parity.py:13: in <module>
    from scripts.check_intent_parity import collect_facts, find_disagreements
E   ModuleNotFoundError: No module named 'scripts.check_intent_parity'
=========================== short test summary info ============================
ERROR tests/unit/scripts/test_check_intent_parity.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.28s ===============================
```

After implementation: `8 passed in 2.26s`.

## 2. What the gate reads and compares

All five files are parsed with `ast`; the script imports no project code.

| Surface key | Source file | Symbol |
|---|---|---|
| `enums` | `llm/intents/_enums.py` | `LLMIntent` members |
| `categories` | `llm/intent_categories.py` | `INTENT_CATEGORY_MAP` keys (category values resolved through `IntentCategory`) |
| `route_intents` | `prompts/route_table_intents.py` | `INTENT_TO_CATEGORY` ∪ `INTENT_TO_MODE`, merged one fact per intent |
| `route_configs` | `prompts/route_table.py` | `ROUTE_CONFIGS` (`PromptRouteConfig(category, mode, ...)`) |
| `profiles` | `llm/intent_profiles.py` | `INTENT_PROFILES` keys |

Families implemented:

1. **Key-set identity** across the five surfaces.
2. **Category agreement** across the surfaces that declare the prompt-route
   category.
3. **Mode agreement** across the surfaces that declare a mode.

The compared universe subtracts `EXEMPT_INTENTS = {"EMBED"}` (ADR-025 — not
gateway-routed) and the intents declared in `NON_ROUTEABLE_INTENTS` in
`route_table.py` (they have no route-table entry by design). A newly added enum
member that is neither exempt nor declared non-routeable must therefore appear in
every surface; an intent dropped from a route table is reported.

## 3. Measured finding: `category` is two different facts

The spec assumes `INTENT_TO_CATEGORY[i] == INTENT_CATEGORY_MAP[i].value`. The tree
does not satisfy that, and the divergences are not typos:

| Intent | `INTENT_CATEGORY_MAP` (model selection, ADR-001) | `INTENT_TO_CATEGORY` / `ROUTE_CONFIGS` (bundled template) |
|---|---|---|
| `CHAT` | `chat` | `writing` |
| `SUMMARIZE` | `planning` | `analysis` |
| `EXTRACT` | `extraction` | `analysis` |
| `FACT_EXTRACT` | `extraction` | `analysis` |
| `SUGGEST` | `extraction` | `writing` |

`INTENT_CATEGORY_MAP` feeds model routing and the thinking policy; the route-table
category names the prompt directory. The gate therefore compares `categories` by
**key set only** and asserts category **values** among the surfaces that declare
the prompt-route category. Making the two domains agree would change model
routing behaviour and is an architecture decision, not a parity fix; it is
recorded here rather than silently normalised.

## 4. Summary line (measured, this tree)

```text
$ uv run --all-packages python scripts/check_intent_parity.py
30 intents, 24 routed, 0 disagreements
exit=0
```

`30` = `LLMIntent` members (including `EMBED`). `24` = `ROUTE_CONFIGS` entries —
the spec's "29 routed" counts the manifest's 24 `routeable: true` plus 5
`routeable: false` blocks; the Python route table holds 24 routes.

## 5. Mutation captures (temporary copies of the real tree)

Each run used a fresh copy of the five declaration files (repository-relative
directory shape preserved) under `/tmp/opencode`; the real tree was not touched.

```text
=== enum member dropped (WRITE -> WRITE_ALIAS in _enums.py) ===
30 intents, 24 routed, 8 disagreements
WRITE_ALIAS: missing from 'categories' surface (declared in 'enums')
WRITE: present in 'categories' surface but missing from 'enums'
exit=1

=== category changed (INTENT_TO_CATEGORY WRITE: writing -> analysis) ===
30 intents, 24 routed, 1 disagreements
WRITE: category disagreement between 'route_intents' ('analysis') and 'route_configs' ('writing')
exit=1

=== mode changed (ROUTE_CONFIGS WRITE: new_chapter -> other_mode) ===
30 intents, 24 routed, 1 disagreements
WRITE: mode disagreement between 'route_intents' ('new_chapter') and 'route_configs' ('other_mode')
exit=1
```

## 6. Gate tails

`just test-file tests/unit/scripts/test_check_intent_parity.py`:

```text
============================== 8 passed in 2.26s ===============================
```

`just lint-check` (`exit=0`):

```text
All checks passed!
3382 files already formatted
```

`uv run --all-packages pyright scripts/check_intent_parity.py`:

```text
0 errors, 0 warnings, 0 informations
```

Proving no existing gate changed:

```text
$ uv run --all-packages python scripts/check_prompt_surface_contract.py
✅ Prompt Surface Contract OK
exit=0
$ uv run --all-packages python scripts/check_locale_sync.py
Drifted: 0
exit=0
```

## 7. T14b seam

`find_disagreements` is the single extension point. T14b adds three further
families there — prompt-directory existence per locale (using each intent's
resolved category/mode), prompt-surface-manifest block agreement, and
adoption-registry coverage — reads `scripts/architecture/prompt-surface-manifest.yaml`
and `scripts/architecture/adoption-registry.yaml` with `yaml`, and keeps
`EXEMPT_INTENTS` as the one exemption. No fact extraction for those files exists
yet; the `collect_facts` shape is unchanged so the seam is additive.

## 8. Concerns

- **Category domains differ for five intents** (§3). The gate reports the
  divergence that matters (same-domain surfaces) but cannot report the model
  grouping against the prompt grouping without failing the pristine tree. A
  follow-up ADR should either unify the two categories or state their separation.
- **The spec's `29 routed` does not match the Python route table.** The gate
  prints the measured `24`; the manifest's five `routeable: false` blocks belong
  to T14b.
- **The brief's "six files" is five files**: `route_table_intents.py` carries both
  `INTENT_TO_CATEGORY` and `INTENT_TO_MODE`, so the six declaration surfaces live
  in five files. The mutation helper copies those five.
- **Mutation tests use `shutil.copy2` per file**, not `copytree`, because the
  minimal tree spans two package subdirectories; the isolation requirement (only
  declaration files, real tree untouched) is met.
- The gate is not wired into `justfile`, pre-commit or CI — T14b does that once
  all six families exist, per the task split.

## Coordinator rulings CR-5 / CR-6 (after independent re-measurement)

Re-measured in the real tree: `LLMIntent` has 30 members, `ROUTE_CONFIGS` and
`INTENT_TO_CATEGORY` 24 keys each, `INTENT_TO_MODE` 22, `INTENT_CATEGORY_MAP` 30.
Five intents carry different values in the two category maps:

```
SUMMARIZE    model=planning    prompt=analysis
EXTRACT      model=extraction  prompt=analysis
FACT_EXTRACT model=extraction  prompt=analysis
SUGGEST      model=extraction  prompt=writing
CHAT         model=chat        prompt=writing
```

- **CR-5:** the two are different taxonomies — model routing (ADR-001) and prompt
  category. The gate compares `INTENT_CATEGORY_MAP` by **key set only** and compares
  categories among the prompt-route surfaces, as implemented. Spec §4's claim that
  the values are equal was false; it is corrected in place, with the measurement and
  the reason, rather than the gate being relaxed silently.
- **CR-6:** "routed" means an intent with a route entry: **24**, not 29. The spec's
  29 counted every manifest block, 5 of which are `routeable: false`. Corrected in
  the spec's acceptance criterion.

Both corrections are the kind of thing this gate exists to surface: the design
document asserted an invariant the code never had, and no check compared them.

## Commit

Committed as `08ccf552` — `feat(scripts): intent-contract parity gate, core families`.

Status correction: the "not committed" line above describes the report at the time
it was written; this section records the commit that landed it.
