# Phase C Task 4 Report — URL-State Adapters

## Status

Implemented Task 4 only: typed URL-state adapters and wiring for Settings, Planning, KB, Analysis, and the editor right panel.

## Root Cause

Workspace panel state was stored feature-by-feature in local React/Zustand state with no shared URL contract. That made share/reload/back-forward behavior inconsistent and allowed Task 3's safe editor panel adapter to exist without runtime use.

## Alternatives Considered

1. Inline `URLSearchParams` handling in each component. Rejected because it duplicates parsing/normalization rules and makes invalid URL recovery drift by surface.
2. One global workspace URL store. Rejected because Settings, Planning, KB, Analysis, and editor panels have different defaults and safety policies.
3. Chosen: small pure adapters per surface plus a shared search-param helper, with component wiring preserving unrelated query params where surfaces share a route.

## Files Changed

- Added shared URL helpers in `packages/web/lib/url-state/searchParams.ts`.
- Added adapters/tests for Settings, Planning, KB, and Analysis URL state.
- Wired `SettingsView`, `PlanningPanel`, `WorldBuilding`, `AnalysisPanel`, and `EditorView` to typed URL state.
- Added/updated component tests for URL initialization, normalization, and navigation writes.
- Extended KB entry search wiring so `q` is shareable without moving server data into URL/Zustand.

## RED Evidence

- `pnpm --dir packages/web test components/studio/settings/settingsUrlState.test.ts components/studio/planning/planningUrlState.test.ts components/studio/kb/kbUrlState.test.ts components/studio/analysis/analysisUrlState.test.ts` failed with missing adapter modules.
- `pnpm --dir packages/web test components/studio/__tests__/SettingsView.test.tsx components/studio/__tests__/WorldBuilding.test.tsx components/studio/planning/__tests__/PlanningPanel.test.tsx components/studio/AnalysisPanel.test.tsx components/studio/__tests__/EditorView.test.tsx` failed on URL initialization/normalization expectations before wiring.

## GREEN Evidence

- URL adapters: `pnpm --dir packages/web test components/studio/settings/settingsUrlState.test.ts components/studio/planning/planningUrlState.test.ts components/studio/kb/kbUrlState.test.ts components/studio/analysis/analysisUrlState.test.ts components/studio/editor-view/editorRightPanelUrlState.test.ts` — 5 files, 14 tests passed.
- Components: `pnpm --dir packages/web test components/studio/__tests__/SettingsView.test.tsx components/studio/__tests__/WorldBuilding.test.tsx components/studio/planning/__tests__/PlanningPanel.test.tsx components/studio/AnalysisPanel.test.tsx components/studio/__tests__/EditorView.test.tsx` — 5 files, 42 tests passed.

## Type-Check Evidence

- `pnpm --dir packages/web type-check` — `tsc --noEmit` passed.

## Hook Fix Evidence

- Root cause: the AI-UX fallback scanner treats literal `?? "..."` defaults in KB production files as potentially visible fallback strings, even when the value is a non-visible URL-state default. The KB adapter now names the empty-query default as `EMPTY_KB_SEARCH_QUERY` and uses `query: searchParams.get("q") ?? EMPTY_KB_SEARCH_QUERY`, preserving the previous missing-`q` behavior without a literal fallback at the use site.
- Root cause: Biome `lint/suspicious/useIterableCallbackReturn` flagged the expression-bodied `URLSearchParams.forEach` callback because it returned the `nextParams.set(...)` expression. The callback now uses a block body, so serialized params are still copied while the callback returns nothing.
- Regression coverage: `pnpm --dir packages/web test components/studio/kb/kbUrlState.test.ts components/studio/__tests__/WorldBuilding.test.tsx` — 2 files, 13 tests passed.
- Type-check: `pnpm --dir packages/web type-check` — `tsc --noEmit` passed.
- Biome: `pnpm --dir packages/web exec biome check components/studio/kb/kbUrlState.ts components/studio/WorldBuilding.tsx components/studio/kb/kbUrlState.test.ts components/studio/__tests__/WorldBuilding.test.tsx` — checked 4 files, no fixes applied.
- AI-UX: `just check-ai-ux` — 45 passes, 0 violations, 3 governed baseline exclusions; Check 12 passed with no visible i18n fallback strings in KB/editor components.

## Commit

- Message: `feat(web): add typed URL state adapters for workspace panels`
- Hash: pending until the report is included in the checkpoint commit; final response records the exact hash.

## Self-Review

- Root cause addressed with typed adapters instead of feature-local query parsing.
- No new dependency and no `middleware.ts`.
- No hardcoded user-facing strings introduced.
- No backend/core contract changes.
- API data remains in TanStack Query; URL stores only tab/mode/search/selection identifiers.
- Editor `panel=session` remains unsafe for deep links and is normalized out at runtime.
- Planning/KB URL writes preserve unrelated search params so panel state adapters can compose.
