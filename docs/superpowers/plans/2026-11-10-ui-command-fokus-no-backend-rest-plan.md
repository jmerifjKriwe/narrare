# UI Command-Fokus, Slice 8 — No-backend remainder — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the six items the backlog marks "no backend needed": shortcut registry + settings cluster, graph pan/zoom, storyboard drag & drop, slash alias, the remaining structure adapters, plus the three small review leftovers; then re-shoot.

**Architecture:** All frontend. The shortcut registry becomes shell data read by the hub, the palette footer and the workspace hint; pan/zoom is view state over the existing layout; DnD rides the existing stage `PUT`; the slash alias opens the existing palette with an initial query; three structure entries are added to the existing registry and the switcher learns to read it.

**Tech Stack:** React 19 · TanStack Router · Vitest · Playwright E2E · `scripts/screenshots.py`.

**Spec:** atlas §5.7 (SET-004 row, KB-008 pan/zoom note, P5 storyboard row, WRITE slash row, PLAN-005 structure adapters) + backlog page `docs/superpowers/specs/2026-11-10-ui-command-fokus-backlog-design.md`.

## Global Constraints

- English in code, tests and developer documentation; user-visible text en/de/fr. A missing key is a build error.
- No new endpoint, no schema change, no migration. Structure adapters are registry data, not a new API.
- No new primitive, no new token, no new gate.
- Dock/nav capacity untouched (no new dock tab, no new nav area).
- Commit grammar (AGENTS.md): `feat`/`fix`/`docs` need a real `User-visible:` line; hidden types (`chore`, `refactor`, `test`) do not. Trailer `Assisted-by: OpenCode (<model>)`.
- Nothing committed before the task's review is green.
- Gates: `just check` · `pnpm --dir=web vitest run <path>` · `just test-e2e <capability>` (8100/3200 if 8000/3100 held) · web build.
- E2E contexts use locale de-DE.

## Scope rulings (recorded)

- **Custom keybindings are OUT.** SET-004 wants view *and* customize; rebinding needs one dispatcher for every listener site plus conflict resolution. This slice ships the registry and the read-only cluster; the backlog row records what rebinding needs. A half-version that claims customization would lie.
- **Graph clustering is OUT.** The canvas already caps nodes (`maxNodes`) and pan/zoom makes large graphs navigable; clustering waits for evidence from real novels. The decision the backlog asked for is recorded as "no clustering until a real novel exceeds the cap".
- **Slash alias is a door, not a new menu:** `/` in an empty editor paragraph opens the existing palette with an initial query. No second command surface.

## Review Focus

1. **A shortcut the app does not actually have** — the registry may list only bindings that exist in code; anything aspirational is a lie. (Task 0.)
2. **Pan/zoom trap** — a user can never zoom out to nothing or drag the graph off-screen; reset is one action away; keyboard can do both. (Task 1.)
3. **DnD without a keyboard path** — the menu stays; a drag must not be the only way to move a chapter, and a failed drop snaps back. (Task 2.)
4. **Slash outside an empty paragraph** — typing `/` mid-sentence must stay a slash, not open a menu. (Task 3.)
5. **A structure whose stages do not match the backend registry** — the switcher reads the registry; a mismatch must fail loudly in tests, not silently render empty columns. (Task 4.)

---

## File Structure

| File | Responsibility |
| --- | --- |
| `web/lib/shortcuts.ts` (+ test) | the canonical registry: action id, label key, platform-aware keycaps, where it applies |
| `app/capabilities/settings/web/ShortcutsPage.tsx` (+ test), `routes`/`CLUSTERS`, i18n | the read-only cluster |
| `web/components/Palette.tsx`, `web/routes/__root.tsx`, editor hint | read keycaps from the registry (no hardcoded `⌘K`) |
| `app/capabilities/knowledge/web/GraphPage.tsx` (+ test) | pan/zoom view state, reset, keyboard |
| `app/capabilities/planning/web/StoryboardPage.tsx` (+ test) | drag & drop over the existing stage PUT |
| `app/capabilities/planning/web/ChapterEditor.tsx` (or the editor's key handler) + `Palette.tsx` | slash alias → palette with initial query |
| `app/capabilities/planning/structures.py` (+ tests), `StoryboardPage.tsx` switcher | three new adapters + registry-driven switcher |
| 3 small leftovers | 12-band test, lens `key`, dead-id cleanup |

---

### Task 0: Shortcut registry + settings cluster (SET-004 view)

- [ ] **Step 1: Inventory the real bindings** — grep every `keydown`/`onKeyDown` in `web/` and `app/capabilities/*/web`; list action, keys, scope (global/editor/dock). Only these go in the registry.
- [ ] **Step 2: Failing tests** — registry shape (unique ids, non-empty keycaps, mac vs other platform), and the cluster page renders one row per registry entry with its group.
- [ ] **Step 3: Implement** — `web/lib/shortcuts.ts`; settings cluster at `/settings/shortcuts` (CLUSTERS + route + page on existing primitives, grouped table); palette footer and workspace hint read the registry; i18n en/de/fr.
- [ ] **Step 4: Gates + commit** — unit tests, typecheck, `just test-e2e settings`; `feat(settings): every shortcut in one place` + `User-visible:` + trailer.

### Task 1: Graph pan and zoom

- [ ] **Step 1: Read** `GraphPage.tsx` viewport/`VIEWPORT` const and the SVG idiom; the layout is fixed, so this is view-only.
- [ ] **Step 2: Failing tests** — zoom in/out changes the viewBox scale; reset returns to fit; clamping keeps scale within bounds; a pan capture cannot move the graph out of reach (bounded translate); keyboard: buttons are focusable and operate.
- [ ] **Step 3: Implement** — wheel zoom (with modifier-free intent documented), pointer drag pan, zoom in/out/reset buttons beside the canvas, `role="group"` + labels; no new token; selection still works after transform.
- [ ] **Step 4: Gates + commit** — component tests, `just test-e2e knowledge`; `feat(knowledge): the graph pans and zooms` + `User-visible:` + trailer.

### Task 2: Storyboard drag and drop

- [ ] **Step 1: Failing tests** — dragging a card onto another stage column calls the existing stage PUT with that stage; a refused PUT snaps the card back with the existing Notice; the menu still moves a chapter (keyboard path unchanged).
- [ ] **Step 2: Implement** — HTML5 drag (`draggable`, `dragstart`/`dragover`/`drop`) on cards and columns; a visible drop target; `aria-grabbed`-free, announcement via the existing live region after a move; disabled while a save is in flight.
- [ ] **Step 3: Gates + commit** — component tests, `just test-e2e planning`; `feat(planning): chapters drag onto a stage` + `User-visible:` + trailer.

### Task 3: Slash opens the palette

- [ ] **Step 1: Failing tests** — `/` in an empty paragraph opens the palette with an initial query; `/` mid-sentence inserts a slash; Escape closes without inserting.
- [ ] **Step 2: Implement** — editor key handler (empty-paragraph check) → palette open with `initialQuery="/"`; `Palette` gains the optional prop, prefilling the field; no second menu.
- [ ] **Step 3: Gates + commit** — editor + palette tests, `just test-e2e writing`; `feat(writing): slash opens the command palette` + `User-visible:` + trailer.

### Task 4: The remaining structure adapters

- [ ] **Step 1: Failing backend tests** — `save-the-cat` (15 beats over 3 acts), `five-act`, `seven-point` exist, have ordered non-overlapping ranges covering 0–1, and their title keys resolve in all catalogs.
- [ ] **Step 2: Implement** — registry entries + title keys; make the storyboard switcher read the registry (remove the hardcoded two-id list) so a fourth structure needs no page change.
- [ ] **Step 3: Gates + commit** — backend planning tests, component test for the registry-driven switcher, `just test-e2e planning`; `feat(planning): five structures to plan against` + `User-visible:` + trailer.

### Task 5: The three review leftovers

- [ ] **Step 1** — pin the 12-band hero's-journey width case in `StructurePage.test`.
- [ ] **Step 2** — `key={selected.id}` on the lens graph so a selection switch cannot render a hybrid frame.
- [ ] **Step 3** — extract the dead-`?entity=` cleanup into one small helper used by the list and the lens.
- [ ] **Step 4: Gates + commit** — `refactor(knowledge): one dead-entity guard` (hidden type) + trailer.

### Task 6: Re-shoot

- [ ] **Step 1** — add/refresh shots for the shortcuts cluster and any changed surface; re-shoot all frames; keep only real content changes, revert noise.
- [ ] **Step 2** — read every kept PNG.
- [ ] **Step 3: Gates + commit** — `just check`, frontend, `just test-e2e settings planning knowledge writing`, build; `docs(screenshots): every frame on the current shell` + `User-visible:` + trailer.

---

## Self-Review

**Spec coverage.** SET-004→T0 (view; customize recorded OUT); KB-008 pan/zoom→T1 (clustering ruling recorded); P5 DnD→T2; slash row→T3; extra adapters→T4; leftovers→T5; re-shoot→T6.

**Type consistency.** Registry keys are catalog keys (compiler-checked); structure ids flow from one backend registry into the switcher.

**Review Focus.** Five lines, each with its owning task + test: invented shortcut→T0; zoom trap→T1; DnD keyboard path→T2; slash mid-sentence→T3; registry mismatch→T4.

**Proportion.** Decisions and contracts named; bodies only where the shape is the decision.
