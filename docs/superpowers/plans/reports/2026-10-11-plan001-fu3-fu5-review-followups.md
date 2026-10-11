# PLAN-001 Review Follow-ups FU3 + FU5 Report — graceful id degrade + empty XML-block omission

**Status:** OK
**Branch:** `fix/plan001-review-followups` (off main `5474f680`)
**Date:** 2026-10-11
**Cap:** 2 production files / 47 gross / 31 net new production LOC (tests excluded;
≤3 files / ≤250 LOC) — within limits. The "+1 shared helper" allowance was NOT
needed: both FU3 id-parse sites live in `scene_service.py`, so the helper is a
module-private function there, no third file.
**Git:** nothing staged or committed (task constraint honored; verified `git status`).

## What was done

### FU3 — corrupt JSONB ref id raised on aggregate GET

`scene_service._to_ref_schema` called `uuid.UUID(str(raw_id))` unguarded: a
corrupt ref id (non-UUID string in the JSONB) raised `ValueError` and failed the
whole GET, inconsistent with the graceful unknown-`status` degrade in
`_helpers._to_core_scene`.

Root cause: the mapping treated a runtime-arbitrary JSONB column (hybrid refs
are user-tolerant storage; backfill-era rows may carry non-UUID id strings) as
guaranteed-well-formed. Same failure mode existed at the second id-parse site,
`present_characters` — mirror-checked via grep: those two are the ONLY
`uuid.UUID(str(...))` sites in the planning scene mapping paths (`_helpers.py`
parses names only, never ids; the `kb_suggested_provider.py` hit is a different
domain, out of scope).

Fix (same degrade shape as the `_to_core_scene` unknown-status pattern — explicit
validation, structured warning keeps it visible per RULE-11, explicit default;
no silent swallow):

1. New module-private `_parse_ref_id(raw_id) -> uuid.UUID | None` — falsy id →
   `None`; parse failure → `logger.warning("corrupt_scene_ref_id", raw_id=…)` +
   `None`. The ref `name` (user content, RULE-22) always survives.
2. `_to_ref_schema` and the `present_characters` mapping both use it → corrupt
   ids degrade to `id=None`, GET returns 200 with names intact.

### FU5 — `_xml_block` emitted empty wrappers

`_xml_block` always emitted `<tag>…</tag>` even when every labeled line was
empty (bare draft with no context → empty `<chapter_context>`/`<instruction>`
blocks in the run prompt).

Fix (minimal, wrapper semantics byte-identical for non-empty content):

1. `_xml_block`: `if not body: return ""` before wrapping — all-empty content
   omits the block; any non-empty content wraps exactly as before.
2. New module-private `_join_blocks` — the draft/refine builders join their
   blocks through it, dropping omitted blocks so no stray separators remain
   (a fully empty draft run prompt is now `""`, not `"\n"`).
3. `build_refine_run_prompt` benefits symmetrically: empty neighbor/chapter
   summaries omit `<chapter_context>`; `<scene_plan>` always stays (the Core
   renderer never renders empty).

## TDD evidence

RED first, all for the right reasons (5 failed / 1 passed):

- `test_scene_service.py::TestCorruptRefIdDegrade` (2 tests) — seeded rows with
  `"not-a-uuid"` / int ref ids raised `ValueError` on GET; presence id `"corrupt"`
  likewise. The names-preserved assertions pin the degrade target.
- `test_scene_ai_guards.py::TestRunPromptEmptyBlockDegrade` (3 of 4 failed) —
  fully-empty draft prompt contained `<chapter_context>`/`<instruction>`
  wrappers; empty-context draft emitted a bare `<instruction>`-only expectation
  failed on the missing omission; refine with empty context emitted an empty
  `<chapter_context>`.
- The 4th test (`test_draft_prompt_populated_context_keeps_exact_wrapper_shape`)
  was green from the start BY DESIGN — it locks the byte-identical wrapper shape
  for populated content as the regression guard.

GREEN after implementation: all new tests pass; existing populated-context
prompt tests (`test_draft_run_prompt_carries_xml_wrapped_chapter_context`,
`test_refine_run_prompt_wraps_rendered_scene_and_neighbors`, prompt-path
compliance) stay green unchanged.

New tests (12 assertions across 6 tests, test LOC not counted against cap):
FU3 — corrupt pov/location ref ids → name-only refs; corrupt presence id →
name+goal preserved. FU5 — fully-empty draft → prompt `""`, no wrappers;
empty context + instruction → exact `<instruction>` block only; populated
draft → exact byte-identical two-block shape; refine with empty context →
`<scene_plan>` present, no `<chapter_context>`/`<instruction>`.

## Gate results

| Gate | Result |
|---|---|
| `uv run --all-packages pytest tests/unit/planning/ tests/unit/api/planning/ -q` | ✅ 307 passed |
| `uv run --all-packages pytest tests/integration/planning/ -q` | ✅ 60 passed (~169s) |
| `just check-architecture` | ✅ exit 0 (3303 files, 13 approved exceptions; exception baseline + prompt-surface + RULE-10 test-existence gates all clean) |
| `uv run pyright apps/api/narrare/planning/scene_service.py apps/api/narrare/planning/_scene_ai_support.py` | ✅ 0 errors, 0 warnings, 0 informations |
| `just lint-file` (both files) | ✅ ruff check + format clean |

Note: the combined scoped command (unit + integration in one invocation) exceeds
a 120s default timeout because the integration leg alone is ~169s; both legs
were run and are green.

## Fix round 2 (review findings: 1 MINOR + 1 NIT)

The MINOR was the same defect class FU3 meant to close: `_to_schema`'s presence
loop still lacked the `_to_core_scene` JSONB tolerance — (a) non-dict entries
raised AttributeError (GET died); (b) `{"name": null}` mapped through
`str(None)` to the literal string `"None"` on the wire.

Changes (scene_service.py only, TDD red→green; 3 new regression tests failing
for the flagged defects first):

1. Presence mapping extracted to `_presence_schemas(row)` mirroring
   `_to_core_scene`'s structure: entries treated as `object` via the same
   `Sequence[object]` cast (keeps the isinstance guard runtime-meaningful for
   pyright), `if not isinstance(presence, dict): continue` — non-dict entries
   are skipped, valid siblings survive (skip, not truncate).
2. Null-name deviation from the reviewer's literal prescription: `.get("name",
   "") or ""` would produce `""` — but `ScenePresenceSchema.name` is
   `min_length=1`, so an empty string raises ValidationError and the GET dies
   anyway. The contract-compliant degrade is entry OMISSION, matching the
   name-less→absent precedent already used by `_to_ref_schema` and
   `_scene_ai_support._name_ref`. The acceptance intent ("null name must not
   reach the wire, never as `'None'`") is met: name-less/blank entries are
   omitted, no `"None"` string can appear. Kept entries still get the `or ""`
   hygiene on `goal` (no min_length there) — null goal → `""`, tested.
3. Residual-asymmetry tighten (FINDING 2 authorization): `_to_ref_schema` also
   raised AttributeError on a non-dict truthy JSONB ref (`raw.get` on a
   string/int) — the same (a) defect one layer up. Signature is now
   `raw: object` with an isinstance-dict guard, the exact mirror of
   `_helpers._ref_name`; non-dict refs map to no ref, names of dict refs
   survive. The class docstring's "same tolerance as `_to_core_scene`" claim
   is kept and now substantiated for entry shape and ref shape by tests:
   corrupt ids → name-only refs; non-dict presences skipped; name-less/null
   presences omitted; non-dict refs → None.

Residual asymmetry, deliberately untouched and reported: a corrupt non-list
scalar stored in `beats` would raise in `_to_schema` (`list(row.beats)`) and
identically in the `_to_core_scene` mirror (`tuple(row.beats or ())`) — the
asymmetry is symmetric with the mirror, the column is non-nullable with a
list default, and the review did not name it.

Gates: unit planning suites 310 passed (+3); integration planning 60 passed;
`just check-architecture` exit 0; scoped pyright `scene_service.py` 0 errors;
lint/format clean; file 239 lines (≤300).

## Deviations

- None material. `build_draft_run_prompt`/`build_refine_run_prompt` now route
  their joins through `_join_blocks` so an omitted block leaves no stray `"\n"`
  separator — slightly beyond the literal `_xml_block`-only fix, but required to
  satisfy the acceptance criterion ("empty-context draft run prompt contains NO
  wrappers") without shipping a leading-newline prompt; non-empty output stays
  byte-identical (locked by exact-equality test).

## Concerns

- `_parse_ref_id` logs `raw_id` on degrade. Ref ids are linkage metadata, not
  narrative user content, so this stays inside the RULE-22 logging posture used
  by the `_to_core_scene` status log; flag if the house rule should also cover
  ref-id strings.
- Corrupt ids now surface as `id=None` name-only refs to the FE; a subsequent
  aggregate PUT round-trips `id: null` back to storage (existing `_ref_to_raw`
  behavior), i.e. the corruption is normalized away on next save. That is the
  intended degrade, noted so nobody expects the bad value to persist.
