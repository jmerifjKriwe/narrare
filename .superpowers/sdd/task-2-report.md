# Phase B — Task 2: StatusMessage — Report

**Status:** ✅ COMPLETE
**Branch:** `ui-primitives`
**Worktree:** `/tmp/opencode/narrare-ui-primitives`
**Commit message (from plan):** `feat(web): add StatusMessage primitive and migrate extraction status surfaces`

## What was built

Non-blocking loading/error/empty/success live-region primitive
`StatusMessage` under `packages/web/components/ui/status-message.tsx`,
implemented test-first (TDD), plus migration of four adopter surfaces that
previously hand-rolled `role="alert"` / `role="status"` markup.

### Files created
- `packages/web/components/ui/status-message.tsx` (49 lines, ≤ 200 limit ✅)
- `packages/web/components/ui/__tests__/status-message.test.tsx` (5 tests)

### Files modified (migration adopters)
- `packages/web/components/studio/extraction/ExtractionError.tsx`
  — bespoke red border box → `<StatusMessage state="error" message={…} action={retry} />`
- `packages/web/components/studio/extraction/ExtractionDone.tsx`
  — bespoke green success block → `<StatusMessage state="success" message={title} />`
  (description retained as a sibling so both i18n strings stay addressable)
- `packages/web/components/studio/extraction/ExtractionLoading.tsx`
  — title + cancel wrapped in `<StatusMessage state="loading" message={aiThinking} action={stop} />`;
  phase description + animated progress bar kept. The redundant ad-hoc hero
  circular spinner was removed because `StatusMessage` already renders an
  `aria-hidden` spinner with `aria-busy` (consistent with "replacing ad-hoc
  inline markup").
- `packages/web/components/ui/connection-lost-banner.tsx`
  — re-expressed as a thin wrapper over `<StatusMessage state="error" … />`
  (plan-required). `role="alert"`, message, and retry behaviour preserved.

### Files modified (test maintenance)
Three obsolete bespoke-styling assertions were replaced with assertions on
the new accessible contract. All string-presence and behaviour assertions
were left untouched and still pass.
- `ExtractionError.test.tsx` — `text-red-600` → `role="alert"` + `aria-live="assertive"`
- `ExtractionDone.test.tsx` — `text-green-600` → `role="status"` + `aria-live="polite"`
- `ExtractionLoading.test.tsx` — `font-medium` → `role="status"` + `aria-busy="true"`

## TDD trace

| Step | Action | Result |
|------|--------|--------|
| 1 | Write failing test | 5 tests written |
| 2 | Run test (RED) | ✅ FAIL — `Failed to resolve import "@/components/ui/status-message"` — exactly as plan predicted |
| 3 | Write minimal implementation | `status-message.tsx` created |
| 4 | Run test (GREEN) | ✅ 5/5 pass |
| 5 | Type-check + lint | ✅ clean (2 self-introduced format/import-order nits auto-fixed with biome) |
| 6 | Migrate adopters | ✅ 4 surfaces migrated, 3 obsolete styling tests updated, no regression |
| 7 | Commit | pending (run after report write) |

## Test summary

```
status-message.test.tsx .................. 5 passed   (new primitive unit tests)
Extraction{Loading,Error,Done}.test.tsx .. 11 passed  (migrated adopters — no regression)
extraction suite (full) .................. 57 passed  (all extraction tests)
connection-lost.test.tsx ................. 9 passed   (banner re-expression — no regression)
analysis/editor/kb consumer panels ...... 288 passed  (ConnectionLostBanner adopters)
```
**Total relevant: 0 failed.** (Full numbers above are the per-suite counts run.)

## Verification commands run
- `pnpm --filter narrare-web exec vitest run components/ui/__tests__/status-message.test.tsx` → 5 pass
- `pnpm --filter narrare-web exec vitest run components/studio/extraction/__tests__/ __tests__/connection-lost.test.tsx` → 67 pass
- `pnpm --filter narrare-web exec vitest run components/studio/analysis/ components/studio/editor/__tests__/UnblockPanel.test.tsx components/studio/kb/__tests__/{ConsistencyCheckPanel,WorldbuildingAnalysisPanel}.test.tsx` → 288 pass
- `pnpm --filter narrare-web run type-check` (`tsc --noEmit`) → clean
- `pnpm --filter narrare-web exec biome check <9 touched files>` → clean (no fixes applied)

## Constraints compliance

- ✅ No new runtime dependency (Tailwind + existing `lucide-react` only).
- ✅ No `middleware.ts`.
- ✅ No hardcoded user-facing strings — `message` is a resolved-i18n prop; the
  primitive never calls `t()` (i18n resolved in the adopter wrappers).
- ✅ `role`/`aria-live` correct per state: `loading`/`success`/`empty` →
  `role="status"` + polite; `error` → `role="alert"` + assertive (forced).
- ✅ `aria-busy="true"` on loading; decorative spinner carries `aria-hidden`.
- ✅ `idle` keeps the live region mounted but empty (sr-only) so the next
  transition announces.
- ✅ Tailwind utility classes + semantic tokens only
  (`text-muted-foreground`, `border-destructive/40`, `bg-destructive/5`,
  `text-destructive`); no inline `style={{}}` introduced (the single
  pre-existing animated progress-bar `width` inline style in
  `ExtractionLoading` is untouched and out of scope).
- ✅ TypeScript strict, no `any`, no type suppressions.
- ✅ React 19 — no `forwardRef` (leaf/presentational, no ref needed).
- ✅ RULE-04 file-size limit honoured (status-message.tsx = 49 ≤ 200).
- ✅ Never used `--no-verify`.

## Notable behaviour changes (intended)

The standardisation that the plan calls for shifts the migrated surfaces from
bespoke palettes onto the primitive's semantic tokens:

1. **ExtractionError** — bespoke `text-red-600` / red border → destructive
   tokens (`border-destructive/40 bg-destructive/5 text-destructive`), and now
   announces via a real `role="alert"` / `aria-live="assertive"` region (the old
   markup had no role/aria-live at all — an a11y improvement).
2. **ExtractionDone** — bespoke `text-green-600` → muted-foreground success
   text inside a `role="status"` polite region (the primitive deliberately
   special-cases only errors; non-error states share the muted treatment per
   spec §5.7).
3. **ExtractionLoading** — bespoke purple title + hero circular spinner →
   `StatusMessage` loading bar (spinner + `aria-busy` + polite live region)
   housing the title and cancel action; the phase progress bar is preserved.
4. **ConnectionLostBanner** — bespoke amber palette → destructive tokens;
   `role="alert"`, message, and retry behaviour preserved (verified by the
   existing connection-lost test, all 9 cases pass).

## Out-of-scope leftover noted

`.superpowers/sdd/task-1-report.md` shows a pre-existing uncommitted content
modification (real diff, present at session start — leftover from the Task 1
session). It is **not** part of Task 2 and was deliberately left out of this
commit. Flagging for the coordinator.

## Blockers
None.
