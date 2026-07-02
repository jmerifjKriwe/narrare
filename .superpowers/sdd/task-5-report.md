# Phase C Task 5 Report — Responsive Baseline for Workspace Panels

## Status

Implemented Task 5 only: responsive baseline wrappers and scroll containment for the editor right panel, KB layout, planning tabs, storyboard stage scroller, and timeline tab bar.

## Root Cause

Workspace panels still used desktop-first single-row or single-panel containers after Tasks 1–4. That meant typed panel identity and URL state could survive reloads, but the rendered shells had no tested mobile/tablet baseline for progressive disclosure or bounded scrolling.

## Alternatives Considered

1. Patch only the failing mobile symptoms in each view. Rejected because it would leave panel responsiveness untested and keep shell behavior feature-local.
2. Introduce the future shared `PanelShell`/Phase B primitives now. Rejected because Task 5 is explicitly Phase C-only and must not implement Phase B primitives.
3. Chosen: add local responsive wrappers and test IDs at the existing shell/panel orchestration points, preserving typed panel identity and URL state from earlier tasks.

## Files Changed

- Added `packages/web/components/studio/_components/WorldBuildingLayout.test.tsx`.
- Updated `WorldBuildingLayout` with a mobile-first `flex-col` / desktop `lg:flex-row` KB container and bounded detail scrolling.
- Updated `EditorRightPanelSlot` with desktop and mobile panel frames and unique heading IDs.
- Updated `PlanningPanel` with a labelled expanded section, horizontal tab scroller, and bounded tab content region.
- Updated `StoryboardPanel` and `TimelinePanel` horizontal scrollers for responsive containment.
- Extended responsive assertions in `EditorRightPanelSlot.test.tsx` and `PlanningPanel.test.tsx`.

## RED Evidence

- `pnpm --dir packages/web test components/studio/_components/WorldBuildingLayout.test.tsx components/studio/editor-view/EditorRightPanelSlot.test.tsx components/studio/planning/__tests__/PlanningPanel.test.tsx` failed before implementation with missing `kb-responsive-layout`, `editor-right-panel-mobile`, and responsive planning region/wrapper test targets.

## GREEN Evidence

- `pnpm --dir packages/web test components/studio/_components/WorldBuildingLayout.test.tsx components/studio/editor-view/EditorRightPanelSlot.test.tsx components/studio/planning/__tests__/PlanningPanel.test.tsx` — 3 files, 10 tests passed.

## Type-Check Evidence

- `pnpm --dir packages/web type-check` — `tsc --noEmit` passed.

## Commit

- Message: `feat(web): add responsive baseline for workspace panels`
- Hash: pending until the report is included in the checkpoint commit; final response records the exact hash.

## Self-Review

- Root cause addressed with tested responsive wrappers rather than ad hoc per-viewport fixes.
- Scope stayed within Task 5; no Task 6 live regions, focus-return changes, or route-level accessibility work added.
- No new dependency, no `middleware.ts`, and no backend/core contract changes.
- No hardcoded user-facing strings introduced; new accessible label uses existing `studio.storyboard.title` translation.
- Tailwind utility classes only; no inline styles.
- File sizes remain below frontend limits; changed files are modular and single-purpose.

## Hook Fix Evidence — Biome Semantic Element Blocker

- Root cause: `EditorRightPanelSlot` used an explicit `role="region"` on the desktop right-panel wrapper where Biome requires the equivalent semantic `<section>` element.
- Fix: replaced the wrapper with `<section>` while preserving `data-testid="editor-right-panel-desktop"`, `aria-labelledby="editor-right-panel-title-desktop"`, and existing Tailwind classes. No lint suppression added.
- RED: `pnpm --dir packages/web exec biome check components/studio/editor-view/EditorRightPanelSlot.tsx` failed with `lint/a11y/useSemanticElements` at `EditorRightPanelSlot.tsx:198:9`.
- GREEN: `pnpm --dir packages/web exec biome check components/studio/editor-view/EditorRightPanelSlot.tsx` passed (`Checked 1 file in 6ms. No fixes applied.`).
- Regression: `pnpm --dir packages/web test components/studio/editor-view/EditorRightPanelSlot.test.tsx` passed (1 file, 5 tests).
- Type-check: `pnpm --dir packages/web type-check` passed (`tsc --noEmit`).
