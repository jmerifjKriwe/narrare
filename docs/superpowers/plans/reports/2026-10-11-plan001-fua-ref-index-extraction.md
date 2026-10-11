# PLAN-001 Follow-up a Report — `consistency/ref_index.py` RULE-04 extraction

**Status:** OK
**Branch:** `chore/plan001-followups-wave3` (HEAD 1d0e199c at task start; uncommitted
working tree — no commit/stage per task rules)
**Date:** 2026-10-11

## Summary

The T15-recommended extraction is done: `_check_timeline_refs` and
`_check_chapter_frontmatter_refs` — plus the `_check_hybrid_ref` /
`_check_scalar_ref` decision trees that only those two chains call — moved
verbatim into a new support module
`apps/api/narrare/consistency/ref_index_checks.py` (same-dir public-named
`ref_index_*` family, cf. sibling `ref_index_helpers.py`; name
keeps the coherent `ref_index_*` module family). **Pure refactor**: identical
bodies (method → free function with the previously-`self._` repositories as
explicit keyword params), identical semantics, identical public surface on
`ref_index.py` (`CrossFeatureRefIndexImpl.check_refs` / `resolve_ref`, ctor
kwargs, the five duck protocols). Zero test edits — the purity proof.

`ref_index.py` lands at **191 lines** (≤300 service guideline, RULE-04);
`ref_index_checks.py` at **228 lines** (within limits). The storyboard scan
(`_check_storyboard_refs` / `_deprecated_name_issue`) stays on the service
per the task's "only what structurally belongs with them" scope.

## Root cause & alternatives

Root cause: the T15 scene-plan scan grew an already-over-limit service
(313 lines pre-T15 → 337 after) past the ≤300 guideline. Options considered:

1. **Move all four chains incl. the storyboard scan** — rejected: exceeds the
   T15-recommended scope the task fixed ("the two, plus only what structurally
   belongs with them").
2. **Free functions with explicit repo params; `check_refs` dispatches
   directly** (chosen) — matches the house precedent
   (`story_suggest_service.py` L253 calls `compose_story_suggest_prompt(...)`
   directly with repos as kwargs).
3. **Keep private delegating methods that forward to module functions** —
   rejected: a pointless indirection layer between dispatch and the chains.

## Protocols note (self-review finding)

Pyright (`reportPrivateUsage`) rejects importing `ref_index.py`'s
underscore-prefixed protocols cross-module. Per the established house pattern
(`kb_lifecycle_consumer.py`, `planning/_helpers.py` each declare their own
minimal duck protocols; the T15 report itself documents "minimal duck
Protocol, mirroring the kb-lifecycle"), `ref_index_checks.py` declares the
three protocols it needs locally (`_KBLookupProtocol`, `_TimelineRepoProtocol`,
`_ChapterRepoProtocol` — docstrings note they mirror the service's). They are
structural: every repo object satisfying the service's protocols satisfies
these, so behavior is unchanged (fakes in `_ref_index_fakes.py` pass both).

Second self-review catch: the first deletion pass left `_check_scalar_ref` on
the service as dead code (its only caller had moved). Removed after a
caller-grep — final `ref_index.py` keeps only dispatch/resolve + the
storyboard chain.

## Line counts (wc -l evidence)

| File | Before | After |
|------|-------:|------:|
| `apps/api/narrare/consistency/ref_index.py` | 337 | **191** |
| `apps/api/narrare/consistency/ref_index_checks.py` | — | **228** (new) |

Diff: 14 insertions / 160 deletions on `ref_index.py` (dispatch calls the two
chains with repo kwargs; moved bodies deleted); new module is the moved code +
module docstring, imports, three mirrored protocols, and one-line function
docstrings. Net new LOC ≈ docstrings/imports/signatures only — a move, within
the ≤250-new-LOC cap. Production files touched: **2** (cap ≤3).

## Purity evidence (mutation-free)

Full consistency suite before AND after — same counts, same results:

- **Before:** `uv run --all-packages pytest tests/unit/api/consistency/ -q`
  → `155 passed in 6.94s`
- **After:** same command → `155 passed in 6.73s`
- `git status` shows exactly the two production files; **no test file
  modified** (`tests/unit/api/consistency/test_ref_index_branches.py`,
  `test_ref_index_helpers.py`, `_ref_index_fakes.py` untouched).

## Gates

- `uv run --all-packages pytest tests/unit/api/consistency/ -q` → **155 passed** (before and after)
- `just check-architecture` → **exit 0** (3304 files checked; 13 approved
  exceptions, baseline no-growth: 12 current vs 12 baseline)
- `just lint-file apps/api/narrare/consistency/ref_index.py apps/api/narrare/consistency/ref_index_checks.py` → **all checks passed** (ruff check + format)
- `just typecheck-file apps/api/narrare/consistency/ref_index.py apps/api/narrare/consistency/ref_index_checks.py` → **0 errors, 0 warnings**

## Self-review checklist

- [x] Root cause + alternatives documented; no workaround (protocol fix follows
      the documented per-module duck-protocol convention, not a suppression)
- [x] Public methods typed, no `Any`
- [x] No business logic added to router/deps; no raw SQL anywhere
- [x] DI unchanged — repositories still injected once at construction and
      passed explicitly into the chains
- [x] File sizes within limits (191 / 228); English only; no commit/stage
- [x] Tests: zero edits, full consistency suite green before and after
