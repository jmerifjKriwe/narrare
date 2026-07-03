# Phase C Task 2 Report — Editor Right-Panel Typed Registry and Store Arbitration

## Status

DONE_WITH_CONCERNS — Task 2 reducer/state/store work is implemented and reducer tests pass. No checkpoint commit was created because Task 3 component call-site migration remains pending and the plan explicitly says not to commit Task 2 when known call-site type-check failures remain.

## Root Cause

The editor right panel used distributed boolean state (`contextPanelOpen`, `generationPanelOpen`, `betaReaderPanelOpen`, etc.). That state shape can represent impossible combinations, because multiple right panels can be `true` at the same time and each call site must locally arbitrate priority. The sustainable fix is a typed single-occupant state model (`rightPanel.active`) with pure open/close/toggle reducers.

## Alternatives Considered

1. Keep booleans and add stricter toggle helpers. Rejected because the underlying state could still represent multiple active panels and consumers would still need defensive arbitration.
2. Migrate all component call sites in this task. Rejected because the approved plan explicitly scopes Task 3 to component call-site migration and URL/accessibility wiring.
3. Chosen: introduce a typed reducer/state registry and Zustand actions now, leave component call-site migration to Task 3 as planned.

## Files Changed

- Created `packages/web/lib/stores/editorRightPanelState.ts`
- Created `packages/web/lib/stores/editorRightPanelState.test.ts`
- Created `packages/web/components/studio/editor-view/useActiveEditorRightPanel.ts`
- Modified `packages/web/lib/stores/editorStoreTypes.ts`
- Modified `packages/web/lib/stores/editorStore.ts`
- Deleted `packages/web/lib/stores/editorPanelToggles.ts`

## RED Test Evidence

Command:

```bash
pnpm --dir packages/web test lib/stores/editorRightPanelState.test.ts
```

Observed expected failure before implementation:

```text
FAIL lib/stores/editorRightPanelState.test.ts
Error: Failed to resolve import "./editorRightPanelState" from "lib/stores/editorRightPanelState.test.ts". Does the file exist?
Test Files 1 failed (1)
Tests no tests
```

## GREEN Test Evidence

Command:

```bash
pnpm --dir packages/web test lib/stores/editorRightPanelState.test.ts
```

Observed pass after implementation:

```text
✓ lib/stores/editorRightPanelState.test.ts (5 tests) 8ms
Test Files 1 passed (1)
Tests 5 passed (5)
```

## Known Task 3 Follow-Up Type-Check Blockers

Full type-check was intentionally not run per Task 2 instructions. Exact pending call-site files still referencing removed boolean panel fields:

- `packages/web/lib/stores/__tests__/editorStore.test.ts`
- `packages/web/components/studio/EditorView.tsx`
- `packages/web/components/studio/__tests__/EditorView.test.tsx`
- `packages/web/components/studio/_components/EditorHeader.tsx`
- `packages/web/components/studio/_components/EditorToolbar.tsx`
- `packages/web/components/studio/editor-view/EditorHeader.tsx`
- `packages/web/components/studio/editor-view/EditorToolbar.tsx`
- `packages/web/components/studio/editor-view/useEditorGenerationActions.ts`
- `packages/web/components/studio/editor-view/useEditorPanelVisibility.ts`
- `packages/web/components/studio/analysis/BetaReaderTrigger.tsx`
- `packages/web/components/studio/analysis/CharacterVoiceTrigger.tsx`
- `packages/web/components/studio/analysis/ConsistencyTrigger.tsx`
- `packages/web/components/studio/analysis/CoreferenceTrigger.tsx`
- `packages/web/components/studio/analysis/POVTrigger.tsx`
- `packages/web/components/studio/analysis/ReadabilityTrigger.tsx`
- `packages/web/components/studio/analysis/SentimentTrigger.tsx`
- `packages/web/components/studio/analysis/__tests__/BetaReaderTrigger.test.tsx`
- `packages/web/components/studio/analysis/__tests__/CharacterVoiceTrigger.test.tsx`
- `packages/web/components/studio/analysis/__tests__/CoreferenceTrigger.test.tsx`
- `packages/web/components/studio/analysis/__tests__/POVTrigger.test.tsx`
- `packages/web/components/studio/analysis/__tests__/ReadabilityTrigger.test.tsx`

## Commit

No commit created. Commit hash/message: N/A. Reason: Task 3 call-site migration remains pending and Task 2 instructions say not to commit when known type-check blockers remain.

## Tooling Note

BLOCKED: Need to run `GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P) && GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P) && BRANCH=$(git branch --show-current) && SUPERPROJECT=$(git rev-parse --show-superproject-working-tree 2>/dev/null || true) && printf 'git_dir=%s\ngit_common=%s\nbranch=%s\nsuperproject=%s\n' "$GIT_DIR" "$GIT_COMMON" "$BRANCH" "$SUPERPROJECT" && git status --short && git log --oneline -5` but permission denied. I continued only with work that did not require that blocked command.

## Self-Review

- Root cause articulated: impossible multi-panel boolean state.
- Solution fits planned Phase C architecture: a typed single-state right-panel controller in the editor store.
- No new runtime dependencies.
- No `middleware.ts` created.
- No hardcoded user-facing strings introduced.
- Tailwind/UI markup not changed in this task.
- TypeScript uses explicit union/interface types and no `any`.
- TDD followed for the pure reducer: failing test observed before implementation, passing test observed after implementation.
- No Task 3 component call-site migration implemented.
- No checkpoint commit created because known Task 3 blockers remain.
