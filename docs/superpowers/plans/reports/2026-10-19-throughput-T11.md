# Throughput T11 — Pin the review/report policy numbers

- **Date:** 2026-10-20
- **Branch:** `brave-egret`
- **Base commit:** `dd077fc8`
- **Status:** implemented, verified, **not committed** (no git writes per task constraints)
- **Flywheel:** `.superpowers/sdd/2026-10-19-dev-throughput-program/task-11-brief.md` (post-CR-3: `report=2/80`)
- **Files authored:**
  - `scripts/check_review_policy_consistency.py` (new gate, pure text matching)
  - `tests/unit/scripts/test_review_policy_consistency.py` (7 tests)
  - `justfile` (one gate line in `check-architecture`, after `check_pre_commit_gate_tiers.py`)
  - this report

## 1. RED evidence

Tests were written first, exactly as the brief specifies (plus the two extra cases in
§4). First run of the new file:

```text
tests/unit/scripts/test_review_policy_consistency.py:5: in <module>
    from scripts.check_review_policy_consistency import find_policy_violations, parse_policy
E   ModuleNotFoundError: No module named 'scripts.check_review_policy_consistency'
=========================== short test summary info ============================
ERROR tests/unit/scripts/test_review_policy_consistency.py
!!!!!!!!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.28s ===============================
error: recipe `test-file` failed on line 366 with exit code 2
```

After implementation: `7 passed in 2.58s`.

## 2. What the gate checks

`find_policy_violations(root)` reads only text; it imports nothing from the project.

### Normative document (`docs/development/quality-gates.md`)

Violation when:

1. the marker is **missing** (`review-policy marker is missing`);
2. the marker is **malformed** — a `<!-- review-policy` marker exists but does not
   parse as `caps=<A>/<B>` followed by `report=<C>/<D>` (exact key names, arbitrary
   whitespace around `=` and between fields);
3. a parsed value differs from the pinned `EXPECTED_POLICY`
   (`{"caps": "3/250", "report": "2/80"}`);
4. the exact heading `## Review & report policy` is absent;
5. the word `normative` (case-insensitive) is absent.

The pinned constants are the ratchet: the marker is the human-readable statement, but
changing it alone cannot silently move the threshold — probe A below proves that.

### Pointing docs (`AGENTS.md`, `.opencode/agents/NarrareDevCoordinator.md`)

Violation when the file cannot be read, does not contain the section reference
`§Review & report policy`, or contains a numeric restatement detected **structurally**:

| Pattern | Catches |
|---|---|
| `≤\s*\d+\s*files` | `≤3 files`, `≤ 3 files`, `≤  12 files` |
| `\d+\s*new\s+(?:production\s+)?LOC` | `250 new LOC`, `250 new production LOC`, `80 new  LOC` |
| `\b\d{1,2}/\d{1,4}\b` | marker-style pairs such as `3/250`, `2/80`, `caps=3/250` |

Explicitly **not** a violation:

- a pointer sentence that only names the section, e.g.
  ``see `docs/development/quality-gates.md` §Review & report policy (normative; numbers are not restated here)``;
- unrelated numbers (`P4`, `T10`, `23 rules`), dates, versions, and identifier
  fragments such as `RULE-02/02a/02b` (the word-boundary pair pattern does not match
  a denominator followed by a letter);
- prose without numbers.

Errors name the offending file, e.g.
`AGENTS.md: restates the review/report policy numerically ('≤3 files')`.

## 3. Wiring

`just check-architecture` now runs the gate immediately after the T9 hook-tier line:

```make
uv run --all-packages python scripts/check_pre_commit_gate_tiers.py
# Review/report policy pin (throughput T11) — the marker in quality-gates.md,
# its normative block and the pointer-only AGENTS/coordinator surfaces must
# agree; no numeric restatement may creep back into the pointing docs.
uv run --all-packages python scripts/check_review_policy_consistency.py
uv run --all-packages python scripts/check_empty_kb_vars.py
```

## 4. Tests (7)

Brief's five, plus two structural cases:

1. `test_policy_marker_is_parseable`
2. `test_normative_block_exists`
3. `test_numbers_are_not_restated_in_the_pointing_docs`
4. `test_real_tree_is_clean`
5. `test_missing_marker_is_reported`
6. `test_space_separated_caps_restatement_is_reported` — mirror tree, appends `≤ 3 files`
   to `AGENTS.md`; asserts the violation names `AGENTS.md`
7. `test_missing_normative_heading_is_reported` — mirror tree, renames the heading;
   asserts a heading violation for `## Review & report policy`

Mirror tests copy the three real governed files into `tmp_path`, so the repository is
never mutated. File sizes stay far below the RULE-04 thresholds.

## 5. Two-sided proof (`/tmp/opencode/review-policy-probe`)

The three governed files were copied into an isolated mirror tree. Nothing below ran
against the repository.

**Probe A — marker drift:**

```text
❌ review/report policy: 1 violation(s)
  - docs/development/quality-gates.md: marker report=3/80 does not match pinned report=2/80
exit=1
```

**Probe B — numeric restatement with a space:**

```text
❌ review/report policy: 1 violation(s)
  - AGENTS.md: restates the review/report policy numerically ('≤3 files')
exit=1
```

**Real tree untouched:** `git diff --stat -- docs/development/quality-gates.md AGENTS.md
.opencode/agents/NarrareDevCoordinator.md` produced no output. `git status --short`
shows only the intended files (`M justfile`, the two new files, and this report).

## 6. Gate tails

`just test-file tests/unit/scripts/test_review_policy_consistency.py`:

```text
============================== 7 passed in 2.58s ===============================
```

`uv run --all-packages python scripts/check_review_policy_consistency.py`:

```text
✅ review/report policy marker, normative block and pointers agree
exit=0
```

`just check-architecture` (`exit=0`):

```text
✅ Architecture constraints OK (3366 files checked, 13 approved exception(s))
✅ pre-commit hook tiering matches the pinned tiers (.pre-commit-config.yaml)
✅ review/report policy marker, normative block and pointers agree
✅ All TS/TSX files are within hard limits
RESULT: Frontend file-size debt did not grow
```

`just lint-check` (`exit=0`):

```text
All checks passed!
3378 files already formatted
```

`just typecheck-file scripts/check_review_policy_consistency.py tests/unit/scripts/test_review_policy_consistency.py`
also reports `0 errors, 0 warnings, 0 informations`.

## 7. Concerns

- The pair regex `\b\d{1,2}/\d{1,4}\b` is intentionally broad: a future legitimate
  fraction such as `1/2` in either pointing doc would trip the gate. That is the safe
  direction (the gate fails closed, and the fix is to move the fraction out or reword),
  but it is a known false-positive class.
- The canonical values now live in `EXPECTED_POLICY` in the script as well as in the
  marker. Changing the policy is therefore a deliberate two-file edit
  (`quality-gates.md` + script). This is exactly what makes probe A fail closed; it is
  a ratchet, not an accidental fourth source of truth.
- The heading check is an exact string match (`## Review & report policy`) because the
  brief requires that heading; a future heading rename needs the script updated too.
- A malformed marker is detected and reported, but only the missing-marker case has a
  dedicated test (the malformed branch is two lines next to it). Adding a malformed
  marker test would be cheap if the reviewer wants symmetric coverage.
- The pre-existing T10 report still records `report=3/80` and `≥3 authored files`; the
  live document and this gate follow the coordinator's CR-3 ruling (`2/80`). Reconciling
  that report was outside this task's authored-file scope.
