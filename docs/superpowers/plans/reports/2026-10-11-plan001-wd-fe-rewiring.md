# PLAN-001 Wave-3 Slice W-D (FE half) Report — useSceneDraftContext rewired to plan-context

**Status:** OK
**Branch:** `chore/plan001-followups-wave3` (HEAD `8f81eb3c`)
**Date:** 2026-10-11
**Cap:** 3 production files / +45 gross new production LOC (novels.ts +4,
types/planning.ts +21, useSceneDraftContext.ts net −4 / 69 lines touched) — well
within ≤3 / ≤250. Hook file size after rewiring: **82/150** (was 111).
Test/infra files (excluded from the production cap, house convention):
2 new test files (wrapper + hook, 245 lines), 1 MSW default-handler edit
(`mocks/handlers/novels.ts`, +7), 1 existing integration test updated
(`ScenePlanEditor.test.tsx`).
**Git:** nothing staged or committed (task constraint honored). The pre-existing
uncommitted W-D BE work (`apps/api/narrare/chapters/{schemas,service,router}.py`,
`docs/reference/openapi.json`, the 2 new chapter test files, the W-D BE report)
was not touched — verified via `git status` before and after.

## What was done

The BE half of W-D shipped `GET /api/v1/novels/{novel_id}/chapters/{chapter_id}/plan-context`
→ `{ chapter: {title, summary}, previous: …|null, next: …|null }`. This slice
switches the FE "Draft with AI" context assembly to it, replacing the former
up-to-three full-chapter GETs (current + prev + next, payloads incl. `content`)
with ONE summary-only request.

1. **`packages/web/types/planning.ts`** — `ChapterPlanContextChapter`
   (`title` + `summary`) and `ChapterPlanContext` (`chapter` required;
   `previous`/`next` nullable), mirroring BE `PlanContextResponse` /
   `PlanContextChapterResponse` field-exactly (RULE-17).
2. **`packages/web/lib/api/novels.ts`** — `chaptersApi.getPlanContext(novelId,
   chapterId)` wrapper (GET `/novels/{novelId}/chapters/{chapterId}/plan-context`).
   `chaptersApi` in `lib/api/novels.ts` is the house location for chapter API
   wrappers (no `lib/api/chapters.ts` exists; the barrel `index.ts`/`client.ts`
   re-export from here).
3. **`packages/web/lib/hooks/useSceneDraftContext.ts`** — the three
   chapter-detail `useQuery` calls replaced by ONE plan-context `useQuery`.
   `structure_type` (storyboard) and `outline_notes` (`getOutline`) sources are
   unchanged. `chapter_summary` composes from `data.chapter.summary`;
   `neighbor_summaries` keeps the exact compact format
   (`Previous chapter "Title": summary` / `Next chapter "Title": summary`,
   `\n`-joined). Null edges and empty summaries are omitted field-wise; the
   zero-context floor (`{}` body) is intact. The now-unused hook-internal
   helpers (`orderedStoryboardChapters`, `neighborIds`) and the
   storyboard-adjacency computation were removed — the BE resolves position
   adjacency itself. The hook-internal removal is safe: the chapter-detail
   cache entry still exists for its real consumer (the editor's
   `useEditorChapterData` fetches it independently).

### Type placement note (file-cap driven, alternatives considered)

`ChapterPlanContext` went into `types/planning.ts` (next to `SceneDraftRequest`,
whose `chapter_summary`/`neighbor_summaries` fields it feeds) rather than
`types/novel.ts` next to `Chapter`. `types/index.ts` uses an explicit
per-file re-export list, so the `novel.ts` route would have required a 4th
production edit (barrel update) against the binding ≤3 cap. Both consumers
import from `@/types/planning` directly — the same direct-module pattern the
hook already used for `SceneDraftRequest`. If the type later gains non-planning
consumers, hoisting it to `novel.ts` + barrel is a mechanical follow-up.

## TDD evidence

RED first (7 of 10 new assertions failed against the unrewired hook/wrapper):
- Wrapper tests: `chaptersApi.getPlanContext` undefined (TypeError on call).
- Hook tests: `getPlanContext` never called (old hook still issued 3
  `chaptersApi.get` calls); composition/key-family assertions unmet.
- The 3 pre- GREEN passes were exactly the degrade behaviors that must survive
  the rewiring (field-wise omission, disabled-without-chapter) — unchanged
  expectations, verified green before and after.

New tests (10):
- `lib/api/__tests__/chapter-plan-context.test.ts` (3): URL/method capture
  (`GET /api/v1/novels/novel-42/chapters/chapter-99/plan-context`) + field-exact
  payload; summary-only shape (no `content` key anywhere); null-edge round-trip.
- `lib/hooks/__tests__/useSceneDraftContext.test.tsx` (7): **exactly ONE
  plan-context request and zero `chaptersApi.get` calls**; query-cache key
  family `["novels", novelId, "chapters", chapterId, "plan-context"]`; compact
  composition of all four fields; null-edge/empty-summary omission; failed
  plan-context → fields omitted while storyboard/outline survive; zero-context
  floor `{}`; no chapter selected → no fetch, floor `{}`.

Updated integration tests (`ScenePlanEditor.test.tsx`, 3): the "sourced
chapter context" test now stubs ONE plan-context handler and pins the fetch
count at **3** (storyboard + outline + plan-context; was 5 with three chapter
GETs); the "every source fetch fails" 500-handler targets the plan-context
route (the old `:chapterId` 500-handler no longer matches the sub-path — and
would have tripped the MSW unhandled-request guard); the "empty summaries"
test feeds empty summary + null edges and keeps the same expected body.

## Query-key hygiene & freshness (task item 4)

- **Key family:** `["novels", novelId, "chapters", chapterId, "plan-context"]`
  (literal, per the task's suggested shape). It is nested below the shared
  chapter-detail key `["novels", novelId, "chapters", chapterId]`, so any
  chapter-scoped invalidation/prefetch (e.g. `invalidateQueries` on the chapter
  key, or the broad `["novels", novelId]` used by `useConfirmRemap`) also
  refreshes plan-context — coherent by construction. A dedicated key factory
  (`novelsKeys.chapterPlanContext`) was considered but skipped: the file cap
  reserved the 3rd production slot for the hook itself, and the chapter-detail
  family is already literal-keyed at every call site (`useEditorChapterData`,
  this hook's predecessor) — the factory consolidation is a separate I-F6-style
  sweep, not this slice.
- **Freshness:** unchanged semantics — TanStack defaults (refetch on mount,
  `staleTime` 0), exactly like the three queries it replaces. **No invalidation
  wiring was added or is expected**: consumers mutating a chapter's summary via
  the editor's `markSaved`/`updateMeta` path already invalidate the broader
  `["novels", novelId, "chapters"]` family prefix (a superset — cf.
  `useEditorPersistence.ts:39-41`), which covers both the chapter-detail key
  `["novels", novelId, "chapters", chapterId]` and, by nesting, plan-context; a
  summary change made elsewhere (future FE surface) should invalidate the same
  chapter family and will propagate. Documented here as the contract; nothing to
  enforce in code today.

## Gate results

| Gate | Result |
|---|---|
| `pnpm test` (full web suite) | ✅ 458 files / 3952 tests passed (incl. 10 new + 3 updated) |
| `pnpm type-check` (`tsc --noEmit`) | ✅ 0 errors |
| `pnpm lint:check` (biome) | ✅ clean (2 auto-fixed import-order findings in the new files during the cycle; remaining "1 info" is the pre-existing `biome.json` deserialize note) |
| File-size gate (hook ≤150) | ✅ 82/150 |

## Deviations

- None material. One judgment call within the binding file set: the
  `ChapterPlanContext` type lives in `types/planning.ts` instead of
  `types/novel.ts` (placement note above) — the alternative would have exceeded
  the ≤3-file cap by one barrel edit.

## Concerns

- **Neighbor semantics shift (acceptable):** the storyboard-stage-ordered
  adjacency of the old FE implementation is replaced by the BE's
  position-within-novel adjacency (BE report: `list_by_novel` order). For
  novels whose storyboard stages diverge from raw positions, the "Previous/Next
  chapter" lines may differ from the pre-W-D behavior — this matches the BE
  half's contract and the BE report's ordering note, and the storyboard fixture
  in tests has no divergent layout to pin either way. Flagging for awareness.
- **`chaptersApi.get` test mock narrowed:** the hook test's module mock stubs
  only `get` + `getPlanContext` — sufficient for the hook's imports; other
  `chaptersApi` consumers are unaffected (they mock the module themselves).
- No other FE consumer of the plan-context endpoint exists yet; when the
  story-suggest or other summary flows adopt it, they should reuse
  `chaptersApi.getPlanContext` and the same key family rather than re-deriving
  keys.
