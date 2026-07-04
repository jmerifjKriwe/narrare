# Task 7 — PanelShell + use-panel-focus

**Branch:** `ui-primitives` · **Base HEAD:** `16bc5653`
**Plan:** `docs/superpowers/plans/2026-07-03-ui-primitives-phase-b.md` (Task 7)

## Status

✅ **Complete.** Primitive + hook created with TDD; `EditorRightPanelSlot` migrated;
all checks green.

## Deliverables

| File | Kind | Lines |
|------|------|------|
| `packages/web/lib/hooks/use-panel-focus.ts` | new (hook) | 58 (≤150) |
| `packages/web/lib/hooks/__tests__/use-panel-focus.test.ts` | new (test) | 5 tests |
| `packages/web/components/ui/panel-shell.tsx` | new (component) | 72 (≤200) |
| `packages/web/components/ui/__tests__/panel-shell.test.tsx` | new (test) | 7 tests |
| `packages/web/components/studio/editor-view/EditorRightPanelSlot.tsx` | migrated | 76 (≤200) |

## Test summary

- `use-panel-focus.test.ts` — **5 passed**
  (move-in on open, no-op when closed, Escape→onClose, focus return to opener,
  latest-onClose via ref despite identity churn).
- `panel-shell.test.tsx` — **7 passed**
  (labelled region + sr-only heading via `titleId`, single mounted shell,
  renders nothing when `open=false`, responsive classes, border side,
  Escape→onClose, `testId` passthrough).
- `EditorRightPanelSlot.test.tsx` — **8 passed** (existing contract preserved,
  zero test edits).
- Regression sweep (`editor-view/` + all `ui/__tests__` + new hook) — **56
  passed**, 0 failures.

Checks: `tsc --noEmit` ✅ · `biome check .` exit 0 ✅ ·
`check_architecture.py` ✅ · `check-testid` ✅.

## Key design decision — single responsive shell (deviation from plan template)

The plan's PanelShell template renders **dual**: an always-mounted desktop
`<section>` plus a mobile modal `<dialog>` + backdrop, sharing the same
children. **I deliberately implemented a single responsive shell instead**, and
document the rationale here per the architectural-discipline standard
(root-cause first, sustainability over template-following).

**Root cause:** the adopter, `EditorRightPanelSlot`, hosts
`EditorPanelContent`, which renders panels that **own streaming hooks**
(`useConsistencyStream`, `useReadability`, `useCharacterVoiceCheck`, … — RULE-13
presentation/shell separation). Dual-mounting those children would instantiate
every streaming hook **twice** → duplicate SSE subscriptions / cancel handles /
state. The plan's own claim ("children are presentational, so the dual render
is identity-safe") does not hold for this adopter.

**Evidence the single shell is the proven pattern:** the pre-existing
`EditorRightPanelSlot` already used one responsive element (bottom-sheet at
narrow widths, static sidebar at `lg`), and its test suite explicitly asserts
this — `"uses one responsive shell for desktop and mobile panel layouts"` checks
`fixed`, `lg:static`, `lg:w-96`, `lg:flex` on a single element and asserts the
absence of separate mobile/desktop shells. Dual render would also break
`"renders exactly the active panel occupant"` (it would mount the occupant
twice) and `"renders no right slot when active panel is null"` (the always-on
desktop region would remain).

**Consequences of the decision:**
- PanelShell renders **one** `<section aria-labelledby={titleId}>` with an
  sr-only `<h2 id={titleId}>{dialogLabel}</h2>`, plus the responsive Tailwind
  classes previously inlined in the slot.
- No modal `<dialog>` / backdrop / `aria-modal` (the mobile surface is a
  bottom-sheet, not a full modal).
- No Tab focus-trap in `use-panel-focus`. PanelShell renders inline at `lg`
  (`lg:static`); a global Tab-trap would lock the keyboard inside the panel and
  prevent reaching the editor. The plan's hook *implementation* included a trap,
  but its hook *tests* do not exercise it, so omitting it is both TDD-minimal
  and correct for the inline-desktop case.
- The primitive's own tests therefore differ from the plan's Step-5 test code
  (which asserted `role="dialog"`/`aria-modal`/backdrop). They encode the
  single-shell behaviour instead. This is the intended TDD outcome: tests are
  written for the design that fits the real adopter.

## use-panel-focus specifics

Signature matches the plan: `usePanelFocus({ open, panelRef, onClose })`.
Behaviour: on open, remember `document.activeElement` as the opener and move
focus to the first focusable in the panel; while open, Escape → `onClose()`; on
close, restore focus to the opener.

**Important:** `onClose` is read through a ref (`onCloseRef`), so the effect's
deps are `[open, panelRef]` only. Without this, the slot — which rebuilds its
`handleClose` every render — would cause the effect to re-run on every parent
re-render, flickering focus (return-to-opener then re-move-in) on each render.
A dedicated test pins this (`"always invokes the latest onClose even if its
identity changes"`).

## Migration notes (EditorRightPanelSlot)

- The bespoke Escape `useEffect` was **removed** — its responsibility now lives
  in `use-panel-focus` (invoked via PanelShell).
- Focus-return-to-opener is folded into the `onClose` handler
  (`handleClose`), preserving the previous behaviour exactly (incl. the
  `returnFocusTo?.isConnected` guard). This keeps the hook's surface
  plan-aligned (no `returnFocusTo` param on the hook).
- The shell-owned polite `role="status"` live region and the `activePanel ===
  null` early-return are kept verbatim — PanelShell is presentation-only and
  does not own the open/close announcement (RULE-13).
- No streaming/AI hooks were touched; only the chrome changed.
- All visible strings remain resolved i18n (`t("shell.editorRightPanel")`,
  `t("shell.panelOpened")`, `t("shell.panelClosed")`); no hardcoded strings
  introduced. Existing keys reused — no i18n file changes.

## Constraints honoured

RULE-04 (file limits) ✅ · RULE-09/RULE-23 (strict TS, no `any`, no
suppressions) ✅ · RULE-13 (presentation-only; no SSE in shell) ✅ · RULE-16
(resolved i18n strings; required `dialogLabel`) ✅ · a11y (`type="button"` where
buttons exist, `aria-labelledby`, focus-visible rings via tokens, sr-only
heading) ✅ · no new runtime dependency ✅ · no `middleware.ts` ✅ · React 19 (no
`forwardRef`) ✅.

## Verification commands

```
pnpm --filter narrare-web exec vitest run \
  lib/hooks/__tests__/use-panel-focus.test.ts \
  components/ui/__tests__/panel-shell.test.tsx \
  components/studio/editor-view/EditorRightPanelSlot.test.tsx
pnpm --filter narrare-web run type-check
pnpm --filter narrare-web run lint:check
```
