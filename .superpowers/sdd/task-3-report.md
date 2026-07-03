# Phase B — Task 3: PanelHeader — Report

**Status:** ✅ COMPLETE
**Branch:** `ui-primitives`
**Commit message:** `feat(web): add PanelHeader primitive and migrate ConsistencyPanelHeader`
**Worktree:** `/tmp/opencode/narrare-ui-primitives`

## What was built

Accessible panel-header primitive `PanelHeader` under
`packages/web/components/ui/panel-header.tsx`, implemented test-first (TDD),
plus migration of the largest duplicated header-chrome adopter
(`ConsistencyPanelHeader`) onto the new primitive.

### Files created
- `packages/web/components/ui/panel-header.tsx` (66 lines, ≤ 200 limit ✅)
- `packages/web/components/ui/__tests__/panel-header.test.tsx` (4 tests)

### Files modified (migration adopter)
- `packages/web/components/studio/analysis/ConsistencyPanelHeader.tsx`
  — the hand-rolled `flex items-center justify-between p-4 border-b bg-card`
  header chrome + title + close boilerplate is now composed from `PanelHeader`.

## TDD trace

| Step | Action | Result |
|------|--------|--------|
| 1 | Write failing test | 4 tests written (test file pre-existed from a prior partial run; verified to match the plan spec, incl. the `closeLabel` decision) |
| 2 | Run test (RED) | ✅ FAIL — `Failed to resolve import "@/components/ui/panel-header"` (module does not exist) — exactly as plan predicted |
| 3 | Write minimal implementation | `panel-header.tsx` created |
| 4 | Run test (GREEN) | ✅ 4/4 pass |
| 5 | Type-check + lint | ✅ clean (3 self-introduced lint nits fixed via `biome check --write` on the two new files only: import sort + single-line JSX formatting) |
| 6 | Migrate adopter | ✅ no regression |
| 7 | Commit | ✅ all pre-commit hooks pass |

## Test summary

```
panel-header.test.tsx ...... 4 passed   (new primitive unit tests)
components/studio/analysis/ 249 passed  (24 files — full analysis suite, no regression)
```
**Total: 253 passed, 0 failed.**

## Verification commands run
- `pnpm --filter narrare-web exec vitest run components/ui/__tests__/panel-header.test.tsx` → 4 pass
- `pnpm --filter narrare-web exec vitest run components/studio/analysis/` → 249 pass (24 files)
- `pnpm --filter narrare-web run type-check` (`tsc --noEmit`) → clean
- `pnpm --filter narrare-web run lint:check` (`biome check .`) → **0 errors**, 6 warnings (all pre-existing, none in the 3 touched files)
- Pre-commit hooks (check_architecture.py, Biome, i18n, TypeScript, Feature Adoption, …) → all Passed/Skipped

## Design decision — labelled action buttons (architectural discipline)

The plan's Task 3 Step 6 says `actions={...refresh/stop buttons via IconButton...}`.
This wording was **not** followed literally, for two grounded reasons:

1. `IconButton` is **icon-only** (no visible label). The Consistency header's
   Stop and Refresh controls carry **visible text labels** that existing tests
   assert on (`screen.getByText("refresh")`, `getByText("aiActions.stop")`).
   Converting them to icon-only would silently drop the visible labels — a
   **UX regression** and would break those assertions.
2. Task 4 introduces `ToolbarButton` — the dedicated primitive for **labelled**
   toolbar actions (with `showLabel` + `aria-pressed`). Converting these two
   buttons is properly Task 4's job; doing it now would duplicate that work and
   cross task boundaries.

**Chosen (sustainable, no regression):** migrate only the *header chrome*
(outer container, title, leading icon, close control) onto `PanelHeader`, and
pass the existing labelled Stop/Refresh buttons through the `actions` slot
**unchanged**. Their `ToolbarButton` conversion is deferred to Task 4.
Alternatives considered: (a) convert now to `IconButton` — rejected (UX
regression); (b) convert now to `ToolbarButton` — rejected (Task 4 not yet
built; scope creep). This keeps Task 3 focused on the `PanelHeader` primitive
with zero behaviour change.

## Notable behaviour changes (intended, standardisation)

1. **Single close control.** The header previously rendered *two* close
   affordances (an `ArrowLeft` "back" button and an `X` close button), both
   calling the same `onClose`. `PanelHeader` renders one standard `X` close.
   The redundant back button is removed — semantically identical (both invoked
   `onClose`). Verified: `ConsistencyPanel.test.tsx` clicks
   `getAllByLabelText("close")`'s **last** element, which is still the (now
   sole) close button → 16/16 pass.
2. **Leading icon colour.** The `Shield` icon was green
   (`text-green-600 dark:text-green-400`); `PanelHeader` renders the leading
   icon with the standard `text-muted-foreground`. The primitive owns icon
   presentation (the point of adopting it); adding a per-adopter override would
   defeat the standardisation, so the normalisation is accepted.
3. **Title gains a stable `id`** (`useId()` or caller `titleId`) — the
   `aria-labelledby` seam `PanelShell` (Task 7) will wire up.

## Constraints compliance

- ✅ No new runtime dependency (Tailwind + existing `lucide-react` only; reuses `IconButton` from Task 1).
- ✅ No `middleware.ts`.
- ✅ No hardcoded user-facing strings — `title`/`closeLabel` are resolved-i18n props; `PanelHeader` throws at runtime if `onClose` is supplied without `closeLabel` (RULE-16 enforcement, no silent fallback).
- ✅ `type="button"` enforced (via the reused `IconButton` close control).
- ✅ `aria-label` required for the close control (never inferred).
- ✅ Decorative leading icon carries `aria-hidden="true"`.
- ✅ `focus-visible:` ring (inherited from `IconButton`).
- ✅ Tailwind utility classes + semantic tokens only; no inline `style={{}}`.
- ✅ TypeScript strict, no `any`, no type suppressions.
- ✅ React 19 — no `forwardRef` (leaf/presentational).
- ✅ RULE-13 — presentation only (owns no SSE/AI streaming).
- ✅ RULE-04 file-size limit honoured (66 ≤ 200).
- ✅ Never used `--no-verify`.

## Pre-existing working-tree state (inherited, NOT part of this task)

- `.superpowers/sdd/task-1-report.md` — modified, uncommitted (a prior session
  correctly rewrote it for Phase B Task 1 but never committed it; left as-is,
  out of Task 3 scope).
- `.superpowers/sdd/task-3-report.md` previously held **stale content from an
  unrelated plan** ("Phase C — Editor Right-Panel Slot", commit `928f49f3`).
  This file overwrites it with the accurate Phase B Task 3 report, as
  instructed.

## Blockers
None.
