# PLAN-001 Wave-3 Slice W-D (BE half) Report — summary-only plan-context endpoint

**Status:** OK
**Branch:** `chore/plan001-followups-wave3` (HEAD `8f81eb3c`)
**Date:** 2026-10-11
**Cap:** 3 production files / +69 gross new production LOC (router +12, schemas +22,
service +35) — well within ≤3 / ≤250. Test LOC: 2 new files, 387 lines (excluded
from the production cap, house convention).
**Git:** nothing staged or committed (task constraint honored; `git status` shows
the 3 production edits, the regenerated `docs/reference/openapi.json`, and the 2
new test files only).

## What was done

FU1 documented that the FE "Draft with AI" context sources
`chapter_summary`/`neighbor_summaries` via up to three full-chapter GETs whose
payload carries `content`. This slice adds the lighter BE surface:

`GET /api/v1/novels/{novel_id}/chapters/{chapter_id}/plan-context` →

```json
{
  "chapter":  {"title": "...", "summary": "..."},
  "previous": {"title": "...", "summary": "..."} | null,
  "next":     {"title": "...", "summary": "..."} | null
}
```

No `content` (and no other chapter fields) reach the wire — the schema is the
guarantee (`PlanContextChapterResponse` declares only `title` + `summary`;
exact-key assertions pin it in both test layers).

1. **`apps/api/narrare/chapters/schemas.py`** — `PlanContextChapterResponse`
   (from_attributes, title+summary) + `PlanContextResponse`
   (`chapter` required; `previous`/`next` nullable).
2. **`apps/api/narrare/chapters/service.py`** — `ChapterService.get_plan_context`:
   uid-scoped novel guard first (`novel_service.get`, foreign ≡ unknown →
   `NotFoundError` → 404), then chapter-in-novel scope via the existing
   `get_by_id(chapter_id, novel_id)` (foreign ≡ unknown → 404), then neighbors
   from `list_by_novel` (position-ordered per its contract) by index adjacency —
   mirroring the FU1/story-suggest neighbor semantics (prev/next by chapter
   position within the novel, edge chapters → `None`). The membership index
   lookup carries an explicit no-silent-None guard (RULE-11) even though the
   scoped fetch guarantees membership.
3. **`apps/api/narrare/chapters/router.py`** — thin `GET /{chapter_id}/plan-context`
   delegating immediately via the existing `_get_service` DI (RULE-06; no logic,
   no repo access in the router).

No repository change was needed: `list_by_novel` already returns the
position-ordered sibling list, so the ≤3-file cap held without touching the
repo or its contract.

## Placement note (RULE-04, alternatives considered)

`service.py` was at 264/300 before this slice; the method (+35 with docstring)
lands at **299/300**. Alternatives weighed: (a) squeeze into `service.py` —
chosen, stays under the hard limit and keeps the method where all chapter read
methods live, per the task's binding file set; (b) dedicated
`plan_context_service.py` module — rejected this slice because a new service
class requires its own Protocol (RULE-03) and would have broken the ≤3-file
cap; (c) module-level function helper — rejected as less house-consistent for a
novel/chapter-scoped read that needs the same DI seams as its siblings.
`service.py` is now AT the hard limit: the next addition to that file must
split (house precedent: `router_versions.py`).

## TDD evidence

RED first (both layers failed before implementation):
- Unit: `AttributeError: 'ChapterService' object has no attribute
  'get_plan_context'`.
- Integration: happy path + both edge tests 404 (route missing) with body
  assertions unmet; foreign-user test failed on the anti-enumeration body-shape
  parity assertion (missing route's bare `{"detail"}` has no `code`). Note: the
  two pure-404 tests (`unknown chapter`, `chapter of other novel`) passed
  spuriously in RED — a missing route and a missing resource are
  indistinguishable at status level; their meaning comes from the body-shape
  parity assertion in the foreign-user test and from running against the real
  route in GREEN.

New tests (13):
- `tests/unit/api/chapters/test_chapter_plan_context.py` (7): middle chapter
  both neighbors; first → `previous is None`; last → `next is None`; single
  chapter → no neighbors; unknown chapter → `NotFoundError`; chapter of another
  novel → `NotFoundError`; response-shape test asserting
  `model_dump()` keys exactly `{chapter, previous, next}` / `{title, summary}`
  with no `content` anywhere.
- `tests/integration/chapters/test_chapter_plan_context_api.py` (6): happy path
  (seeded novel + 3 chapters via the API, summaries seeded via the shared test
  session; exact wire keys, no `content`); first → null previous; last → null
  next; unknown chapter → 404; chapter-of-other-novel → 404; foreign user →
  404 with foreign ≡ unknown body parity (`{"detail", "code"}`, `NOT_FOUND`).

## Gate results

| Gate | Result |
|---|---|
| `pytest tests/unit/api/chapters/test_chapter_plan_context.py` | ✅ 7 passed |
| `pytest tests/integration/chapters/test_chapter_plan_context_api.py` | ✅ 6 passed |
| Regression: `tests/unit/api/chapters/` (86) + `tests/integration/chapters/` (16) | ✅ all passed |
| `just lint-file` (3 prod + 2 test files) | ✅ ruff check + format clean |
| `just typecheck-file` (same 5 files) | ✅ 0 errors / 0 warnings (prod + tests configs) |
| `just check-architecture` | ✅ exit 0 (3307 files checked; 45 services, 0 missing test files, 0 low coverage; RULE-04 sizes OK incl. service.py 299 ≤ 300) |
| `just export-openapi` | ✅ regenerated — 194 paths / 350 schemas, `plan-context` path present (+111 lines) |

## Deviations

- None material. The task anticipated "likely `chapters/service.py`" — chosen,
  with the RULE-04 placement rationale above (it fits, at 299/300).

## Concerns

- **Protocol parity deferred:** `get_plan_context` is not yet in
  `ChapterServiceProtocol`. RULE-03 is satisfied at the class level (the
  Protocol exists and predates this work), but extending it would have been a
  4th production file against the binding ≤3 cap; the protocol has zero
  consumers (grep-verified — the router depends on the concrete class).
  Recommend folding the signature into `ChapterServiceProtocol` in the next
  slice that touches `chapters/contracts.py`.
- **`service.py` at 299/300:** any future edit to this file must split first
  (see placement note). Flagging for the coordinator's next slice sizing.
- Position ties (equal `position` values) have no secondary ordering —
  `list_by_novel` orders by `position` only, same field the FE storyboard
  flatten sorts by (FU1), so the semantics match; `reorder` normalizes to
  0..n anyway.
- No FE consumer yet — the FE half of W-D (switching `useSceneDraftContext` to
  this endpoint) is out of scope for this BE dispatch.
