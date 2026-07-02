# Phase C Task 3 Report — Editor Right-Panel Slot Rendering, URL Sync, and Phase-C Accessibility

## Status

DONE — Task 2 typed store changes and Task 3 component call-site migration are ready for the checkpoint commit `refactor(web): render editor panels through typed right slot`.

## Root Cause

Editor right-panel rendering still depended on deleted boolean visibility fields and a priority hook, so the UI layer could not consume Task 2's single-occupant `rightPanel.active` invariant. The sustainable fix was to route all editor right-side rendering through one typed slot and migrate toolbar/header/trigger call sites to `rightPanel.active` plus typed panel actions.

## Alternatives Considered

1. Keep `useEditorPanelVisibility` as a compatibility adapter over `rightPanel.active`. Rejected because it preserves a duplicate visibility abstraction and weakens the single-occupant source of truth.
2. Migrate only `EditorView` and leave toolbar/analysis triggers on compatibility actions. Rejected because it leaves removed boolean field reads in active components and fails the type-check gate.
3. Chosen: create `EditorRightPanelSlot`, parse only safe URL panel values, delete obsolete side-panel/visibility files, and migrate editor header/toolbar/triggers/tests to typed panel state.

## Files Changed

- Created `packages/web/components/studio/editor-view/EditorRightPanelSlot.tsx`
- Created `packages/web/components/studio/editor-view/EditorRightPanelSlot.test.tsx`
- Created `packages/web/components/studio/editor-view/editorRightPanelUrlState.ts`
- Created `packages/web/components/studio/editor-view/editorRightPanelUrlState.test.ts`
- Modified `packages/web/components/studio/EditorView.tsx`
- Modified `packages/web/components/studio/editor-view/EditorToolbar.tsx`
- Modified `packages/web/components/studio/editor-view/EditorHeader.tsx`
- Modified `packages/web/components/studio/editor-view/useEditorGenerationActions.ts`
- Modified analysis trigger components and tests to use typed right-panel state
- Modified `packages/web/components/studio/__tests__/EditorView.test.tsx`
- Modified `packages/web/lib/stores/__tests__/editorStore.test.ts`
- Deleted `packages/web/components/studio/editor-view/useEditorPanelVisibility.ts`
- Deleted `packages/web/components/studio/editor-view/EditorSidePanels.tsx`

Task 2 files remain included in this checkpoint because Task 2 was intentionally uncommitted by plan.

## RED Test Evidence

Command:

```bash
pnpm --dir packages/web test components/studio/editor-view/EditorRightPanelSlot.test.tsx components/studio/editor-view/editorRightPanelUrlState.test.ts components/studio/__tests__/EditorView.test.tsx
```

Observed expected failure before implementation:

```text
Test Files 3 failed (3)
Tests 3 failed | 12 passed (15)
```

## GREEN Verification Evidence

Focused task tests:

```bash
pnpm --dir packages/web test lib/stores/editorRightPanelState.test.ts components/studio/editor-view/EditorRightPanelSlot.test.tsx components/studio/editor-view/editorRightPanelUrlState.test.ts components/studio/__tests__/EditorView.test.tsx
```

Observed:

```text
Test Files 4 passed (4)
Tests 27 passed (27)
```

Expanded regression tests for touched store/trigger call sites:

```bash
pnpm --dir packages/web test lib/stores/editorRightPanelState.test.ts lib/stores/__tests__/editorStore.test.ts components/studio/editor-view/EditorRightPanelSlot.test.tsx components/studio/editor-view/editorRightPanelUrlState.test.ts components/studio/__tests__/EditorView.test.tsx components/studio/analysis/__tests__/BetaReaderTrigger.test.tsx components/studio/analysis/__tests__/CharacterVoiceTrigger.test.tsx components/studio/analysis/__tests__/CoreferenceTrigger.test.tsx components/studio/analysis/__tests__/POVTrigger.test.tsx components/studio/analysis/__tests__/ReadabilityTrigger.test.tsx
```

Observed:

```text
Test Files 10 passed (10)
Tests 86 passed (86)
```

Type-check:

```bash
pnpm --dir packages/web type-check
```

Observed:

```text
$ tsc --noEmit
```

## Deletion/Reference Checks

- `useEditorPanelVisibility` and `EditorSidePanels` files are deleted.
- Search for `useEditorPanelVisibility|EditorSidePanels` in `packages/web` returned no files.
- Search for removed right-panel boolean field names in `packages/web` returned no files.

## Self-Review

- Root cause articulated: component layer still consumed removed boolean panel state.
- Solution fits Phase C architecture: typed single right-panel slot and store-backed active panel state.
- No Task 4 Settings/Planning/KB/Analysis URL adapters implemented.
- No new runtime dependency.
- No `middleware.ts` introduced.
- No hardcoded user-facing strings introduced; the new region label uses `studio.shell.editorRightPanel`.
- Tailwind utility classes only.
- Props and API responses remain typed; no `any` introduced.
- Obsolete visibility/side-panel files deleted.

## Concerns

None blocking. `code-review-graph detect_changes` reported structural test gaps for some changed components even though focused component tests and migrated trigger tests pass; this appears to be graph coverage mapping rather than a failing verification gate.

## Hook Fix

Root cause: the desktop right-panel wrapper used `<aside role="region">`, which duplicated a region landmark role that Biome's `lint/a11y/useSemanticElements` expects to be represented by a semantic `<section>` element instead of an explicit role on an `aside`.

Fix: replaced the wrapper with `<section aria-labelledby="editor-right-panel-title" ...>`, preserving the existing hidden heading, Tailwind classes, and accessible name. Tests did not need updates because an accessible `<section>` still exposes a `region` landmark.

Verification:

```bash
pnpm --dir packages/web exec biome check components/studio/editor-view/EditorRightPanelSlot.tsx
```

Observed after fix:

```text
Checked 1 file in 39ms. No fixes applied.
```

```bash
pnpm --dir packages/web test lib/stores/editorRightPanelState.test.ts lib/stores/__tests__/editorStore.test.ts components/studio/editor-view/EditorRightPanelSlot.test.tsx components/studio/editor-view/editorRightPanelUrlState.test.ts components/studio/__tests__/EditorView.test.tsx components/studio/analysis/__tests__/BetaReaderTrigger.test.tsx components/studio/analysis/__tests__/CharacterVoiceTrigger.test.tsx components/studio/analysis/__tests__/CoreferenceTrigger.test.tsx components/studio/analysis/__tests__/POVTrigger.test.tsx components/studio/analysis/__tests__/ReadabilityTrigger.test.tsx
```

Observed after fix:

```text
Test Files 10 passed (10)
Tests 86 passed (86)
```

```bash
pnpm --dir packages/web type-check
```

Observed after fix:

```text
$ tsc --noEmit
```
