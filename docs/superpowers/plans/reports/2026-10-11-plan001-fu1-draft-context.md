# PLAN-001 Follow-up #1 Report — FE "Draft with AI" sends no chapter context

**Status:** OK
**Branch:** `fix/plan001-draft-context` (off main `0a9174c0`)
**Date:** 2026-10-11
**Cap:** 3 production files / ~147 gross / ~124 net new production LOC
(editor 200→184; ≤3 / ≤250) — within limits.
**Git:** nothing staged or committed (task constraint honored; verified `git status` at end).

## What was done

`ScenePlanEditor.handleDraft` posted `body: {}`, so the BE composed an empty
`<chapter_context>` block and drafted from project title/genre only. The context
assembly now lives in a dedicated hook and the component consumes it:

1. **New** `packages/web/lib/hooks/useSceneDraftContext.ts` (111 lines after the fix-round doc additions, hook limit
   150) — `useSceneDraftContext(novelId, chapterId): SceneDraftRequest`. Sources
   each context field independently via TanStack Query; returns an object that
   spreads ONLY fields that actually resolved, so an empty-context run produces
   today's `{}` body (RULE-17: no invented values; the zero-context path stays the
   graceful floor, just no longer the default).
2. **New** `packages/web/components/studio/planning/scenePlanHelpers.ts` (30 lines)
   — pure aggregate helpers (`withPositions`, `proposalToScene`, `nowIso`) moved
   verbatim out of `ScenePlanEditor`. This was the extraction the component's
   200/200 budget forced: moving them frees the lines the hook wiring needs
   without compressing anything (RULE-04 modularize, not compress).
3. **Edited** `packages/web/components/studio/planning/ScenePlanEditor.tsx`
   (200 → 184 lines) — imports the helpers + hook, calls
   `useSceneDraftContext(novelId, chapterId)` above the early returns (hooks
   order safe), and `handleDraft` posts `body: draftContext` instead of `{}`.
4. **Test edits** `ScenePlanEditor.test.tsx` (+229 test LOC, not counted against
   the production cap) — TDD: RED first (new assertions failed against `body: {}`),
   then GREEN after implementation.

## Fields sourced (RULE-17-exact, all optional in `SceneDraftRequest`)

| Field | Source | Notes |
|---|---|---|
| `structure_type` | `useStoryboard(novelId)` → `storyboard.structure_type` | BE reports `novel.story_structure` there verbatim (`planning/service.py` `get_storyboard`), so it is the planning-native value; cache is shared with `StoryboardPanel`. |
| `outline_notes` | `getOutline(novelId, chapterId)` → `outline_notes` | Outline aggregate; query key mirrors `planningKeys.outline` so `useUpdateOutline` invalidations refresh it. `outline.stage_assignment` is a stage id, not a structure type — NOT mapped anywhere (no invented semantics). |
| `chapter_summary` | `chaptersApi.get(novelId, chapterId)` → `Chapter.summary` | The studio's chapter detail record under the `["novels", novelId, "chapters", chapterId]` key shared with the editor view. Freshness relies on mount-refetch (default `staleTime` 0) — no flow currently invalidates this key. NOTE (named FE follow-up): `useSummary.ts` invalidates `["chapters", chapterId]` on summarize success, a key nothing consumes — a pre-existing dead invalidation, so a freshly generated summary is only picked up on the next mount. |
| `neighbor_summaries` | `Chapter.summary` of the position-adjacent chapters | Chapter order derived from the storyboard stage layout (flattened, sorted by `position`); prev/next fetched via the same chapter-detail endpoint; composed as one compact free-form string per line: `Previous chapter "Title": summary` / `Next chapter "Title": summary` (BE composes it verbatim into a labeled `<chapter_context>` line — free-form per contract). Missing summaries omit their line. |
| `instruction` | intentionally NOT sourced | No UI collects one (task constraint); server default `""` applies. |
| `scene_count` | intentionally NOT sourced | No UI for it; `0 = model chooses` server default applies. |

## Graceful degradation

- Every source query degrades independently: fetch failure or missing data ⇒ the
  field is simply absent from the body (`{}` floor = today's shipped shape).
- No new loading blocker: the Draft button's only disabled condition remains
  `draft.isPending`; whatever context has arrived by click time is sent.
- BE contract untouched (all request fields have `""` defaults; empty values are
  omitted from the `<chapter_context>` block by `_labeled`).

## getOutline orphan status (CURRENT_STATE follow-up #4)

**Resolved** as a side effect, as the task anticipated: `getOutline` had zero
production consumers; `useSceneDraftContext` now consumes it (verified by grep —
definition + hook only). Not removed.

## TDD evidence

RED (before implementation): new tests failed against the shipped `body: {}` —
`expected {} to deeply equal { structure_type: … }` / `contextGets` never reached 5;
the degrade test passed from the start (it pins today's behavior as the floor) and
stayed green as the regression guard. All 10 pre-existing tests green throughout.

New tests:
1. `sends the sourced chapter context in the draft POST body` — seeded storyboard
   (3 chapters across 2 stages, chapter-1 between 0 and 2) + outline notes +
   per-chapter summaries; asserts the exact POST body including the composed
   `neighbor_summaries` string.
2. `degrades to an empty context body when every source fetch fails` — storyboard/
   outline/chapter GETs all 500; body `{}`, proposal still applies (PUT fires, no
   crash).
3. `omits per-field context when summaries are empty but keeps resolved fields` —
   empty summaries ⇒ only `structure_type` + `outline_notes` in the body.

MSW note: the harness `setup()` gained benign context-source handlers (empty
values) so the legacy tests keep seeing the zero-context body and the unhandled-
request guard stays clean.

## Gate results

| Gate | Result |
|---|---|
| `cd packages/web && pnpm test` | ✅ 456 files / 3942 tests passed |
| `cd packages/web && pnpm type-check` | ✅ `tsc --noEmit` clean |
| `cd packages/web && pnpm lint:check` | ✅ clean (after `pnpm lint` formatted the 2 new/edited files; only those were touched) |
| `pnpm check:i18n` (repo root) | ✅ all clear |
| `.venv/bin/python scripts/check_frontend_file_size.py` | ✅ 0 current / 0 baseline / 0 new violations; `ScenePlanEditor.tsx` 184 ≤ 200, `useSceneDraftContext.ts` 111 ≤ 150 |

Re-review note (round 2): the full-degrade test (test 10) intentionally has NO settle guard — its `{}`-body assertion is timing-invariant (all sources fail ⇒ data undefined ⇒ body always `{}`), and a test-9-pattern `contextGets === 5` guard would deadlock there (storyboard 500 ⇒ neighbors never enable ⇒ counter caps at 3).
| `just check-architecture` | ✅ exit 0 (45 services checked, 0 missing test files) |

## Deviations

- None material. One note: the task suggested the hook could be "the only new
  file", but keeping `ScenePlanEditor` at ≤200 required moving its three pure
  helpers (`withPositions`, `proposalToScene`, `nowIso`) into
  `scenePlanHelpers.ts` — the component was at exactly 200/200 and the hook
  wiring needs 2 net lines. Stays within the ≤3-production-files cap (hook +
  helpers + component).

## Concerns

- `chapter_summary`/`neighbor_summaries` source the chapter-detail endpoint,
  whose `Chapter` payload includes `content` — three full-chapter GETs per
  planning-tab mount (cached/shared with the editor view). A lighter
  summary-only endpoint would be a nice BE follow-up, but inventing one was out
  of scope for this FE-only dispatch.
- `neighbor_summaries` ordering assumes the storyboard stage layout reflects
  narrative chapter order; the flatten sorts by `position`, so this matches the
  BE's own chapter enumeration.
- Context is fetched on mount, not on click; a user clicking Draft within the
  first query round-trip gets whatever has resolved (documented graceful floor,
  per task constraint "no loading blocker on the button beyond what exists").
