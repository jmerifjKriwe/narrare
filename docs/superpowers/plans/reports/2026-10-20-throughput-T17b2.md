# Throughput T17b2 — the mirror table, repaired and mechanically guarded

- **Date:** 2026-10-20
- **Branch:** `brave-egret`
- **Base commit:** `0052f5da` (plus the uncommitted T17a/T17b work — untouched
  except the ci.yml table T17b authored, which is read-only here)
- **Status:** implemented, verified, **not committed** (no git writes per task
  constraints)
- **Follow-up to:** T17b, which added four rows to the `ci.yml` gate table only
  and recorded the unguarded mirror as a concern.

## 1. Gap

`ci.yml`'s header comment calls itself "the CI-gate SSOT", and
`docs/development/quality-gates.md` declares itself the canonical prose mirror.
`scripts/check_gate_drift.py` checked that the mirror file *exists* plus three
specific values/steps — it never parsed either table. T17b added four rows to
`ci.yml` alone and nothing failed, which is the same mechanism that had already
let earlier rows drift.

Mechanical comparison at `HEAD` (`0052f5da`) before T17b: both tables carried
**37** rows and were identical. After T17b's dirty change: `ci.yml` **41**,
doc **37**. So the provider-catalog and intent-parity rows were new in T17b as
well — the doc did not lack them "from before"; all four rows were T17b additions.

Missing rows (ci.yml only):

| Gate | Tool / Check |
|------|--------------|
| `--` | `generate_provider_catalog.py --check (ADR-099)` |
| `--` | `check_intent_parity.py (ADR-025/037/038)` |
| `--` | `check_pre_commit_gate_tiers.py (ADR-098)` |
| `--` | `check_review_policy_consistency.py (ADR-093)` |

## 2. Change

### `docs/development/quality-gates.md`

Four rows inserted at the positions `ci.yml` uses (provider catalog and intent
parity after `check_prompt_surface_contract.py`; the two throughput checks after
`check_adr_naming.py`). Existing rows were not reordered. Formatting follows the
doc's column widths (6/42/13/64) and `✅ Blocking` / `architecture Job`
phrasing; no long-cell rewrapping of neighbours.

Result: **41 rows in each file, identical tool sets** (40 gate-id rows compared
plus the non-gate `MutMut Mutation Score` row, which the check ignores by the
declared gate-id contract and which is identical in both files).

### `scripts/gate_drift_checks.py`

New check `ci-table-mirror` (plus helpers `extract_gate_rows` and
`compare_gate_rows`):

- a data row is a line starting with `|` (optionally after the `#` comment
  prefix in `ci.yml`) whose first cell is a gate id (`G1`, `G3e`, `G6a`, ...) or
  the `--` placeholder; header and separator rows are excluded by that rule;
- the **Tool / Check** cell (column 2) is compared as a set after collapsing
  internal whitespace and stripping, so padding differences are not drift;
- drift is reported as two lists: `only in ci.yml: ...` and
  `only in quality-gates.md: ...`;
- a missing/unreadable doc is skipped here (passed with an explanatory detail)
  because `ssot-present` already fails hard for it — no double-reporting.

**Severity: blocking.** After step 1 both tables are identical, so the check is
clean on the committed tree. The module has no "warning without exception"
state: `DriftItem` only softens a failure through `has_exception`, i.e. a
registered entry in `gate-exceptions.json` — which this task may not edit.
Blocking is the module's default for every check and needs no registry entry,
so it is the convention-conforming choice. (Had the tables still differed, the
only available warning path would have been a registry exception; that lever is
for accepted debt, not for a check that is clean today.)

## 3. Verification (raw)

```
$ uv run --all-packages python scripts/check_gate_drift.py
GATE DRIFT REPORT
======================================================================
✅ ssot-present: Quality gates SSOT present at docs/development/quality-gates.md
✅ ci-table-mirror: Both gate tables carry the same 40 tool/check rows
✅ coverage-threshold: CI --cov-fail-under=80, documented target 80%
✅ streaming-compliance: Blocking in CI
✅ locale-sync: Blocking in CI

Summary: 0 critical, 0 warnings (all drifts have registered exceptions)
exit=0
```

Mutation (real files, one row dropped from each side in opposite directions):

```
passed: False
detail: Gate table rows differ — only in ci.yml: check_locale_sync.py;
        only in quality-gates.md: check_architecture.py
```

```
$ just test-file tests/unit/scripts/test_gate_drift_ci_table_mirror.py
collected 7 items
... 7 passed in 2.37s
```

```
$ uv run --all-packages python /tmp/opencode/rowdiff.py   # throwaway row differ
ci count 41 doc count 41
only ci: []
only doc: []
dupes ci: [] dupes doc: []
```

```
$ uv run --all-packages python scripts/check_doc_drift.py --governance-only
⚠️  57 doc drift warnings
✅ Doc drift check passed (with warnings)
exit=0
```

```
$ just check-architecture
... 45 services checked, 0 missing test files, 0 low coverage
✅ All TS/TSX files are within hard limits
RESULT: Frontend file-size debt did not grow
exit=0
```

```
$ just typecheck-file scripts/gate_drift_checks.py tests/unit/scripts/test_gate_drift_ci_table_mirror.py
0 errors, 0 warnings, 0 informations   (both files)
$ ruff check / ruff format --check       All checks passed / already formatted
```

Line counts: `scripts/gate_drift_checks.py` 379, test file 119 — both under 600.

## 4. Concerns

- The check deliberately ignores non-gate-id rows (`MutMut Mutation Score` is a
  monthly schedule row, not a gate). If that row ever diverges, this check will
  not catch it; widening the id filter would couple it to unrelated table rows.
- Other prose duplication remains unguarded (the "[1] quality split" footnote is
  not compared), and the underlying recipe/CI duplication from T17b stays.
- The check reports duplicates only implicitly: a tool string listed twice in
  one table collapses into the set and reads as present. That matches the
  parity contract in the task (set equality) but is not a uniqueness gate.
