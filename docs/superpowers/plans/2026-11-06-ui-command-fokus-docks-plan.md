# UI Command-Fokus, Slice 2 — Docks + Palette + Galerie — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modernize the two workspace docks and the palette on existing v2 backends, and pin the new states in the gallery — no new backend, no new primitive, no new gate.

**Architecture:** Chat and Knowledge panels render conversational/card states from the same APIs (`/ask`, entity/checks endpoints) through existing primitives (`Notice`, `Row`, `Panel`, `JobStatus`, `Cover`); missing palette entries wrap existing endpoints via `commands.ts` + lazy dialogs; the gallery gains one specimen per new state and the screenshots re-shoot.

**Tech Stack:** Python 3.14 · FastAPI · Vite · React 19 · TanStack Router · Tailwind v4 · Vitest · Playwright E2E.

**Spec:** `docs/superpowers/specs/2026-11-06-narrare-ui-command-fokus-design.md` (§5.3 docks, §5.4 palette, §5.5 AI patterns)

## Global Constraints

- English in code, tests and developer documentation; user-visible text in en, de and fr through `i18n/*.json`. A missing key is a build error.
- One capability is one folder; a capability never imports another capability. Shared UI lives in `web/ui/` and `web/components/`; commands speak the shell contract (`@shell/lib/commands`), components only inside `run`'s dynamic `import()`.
- Tokens only from `web/globals.css`; no new primitive, no second data store, no new token, no new gate.
- No new backend endpoint, no schema change, no migration in this slice. If a desired palette action has no backend, it is OUT — recorded in the task report, not built.
- Every `feat`/`fix` commit carries a real `User-visible:` line and the trailer `Assisted-by: OpenCode (<model>)` via `git commit --trailer`. Author and committer stay human.
- Nothing is committed before the task's review is green.
- Gates: `just check` · `pnpm --dir=web vitest run <path>` · `just test-e2e <capability>` (ports `NARRE_E2E_API_PORT=8100 NARRE_E2E_WEB_PORT=3200` if 8000/3100 are held) · web build at the end.
- E2E contexts use locale de-DE.

## Review Focus

0. **A feature family with no slot** — every family in `docs/features/INDEX.md` plus the v1 corpus names must resolve to exactly one slot in the atlas table; a family with two plausible slots gets a recorded decision, not a silent default. (Task 0.)
0b. **A draft that invents new primitives** — Zielzustand drafts use only landed primitives and skeleton frames; anything that needs a new token/component is labeled as such in the draft. (Task 1.)

1. **A refused/slow `/ask`** — the panel shows the ask in progress (`JobStatus`), then the refusal with a retry, never a stuck spinner. (Task 2.)
2. **A 120-character entity name in the dock list** — wraps or clamps without breaking the row or the filter. (Task 3.)
3. **A palette command whose backend 409s/422s** (e.g. setup-required) — the dialog reports the refusal in words, no silent close. (Task 4.)
4. **Dark chosen theme on every new state** — gallery specimens render in both themes; the re-shoot proves it. (Tasks 1 and 5.)
5. **A dock panel at 1280 px with the rail expanded** — no horizontal overflow, no clipped action buttons. (Tasks 2–3, E2E viewport assert.)

---

## File Structure

| File | Responsibility |
| --- | --- |
| `docs/superpowers/specs/2026-11-06-narrare-ui-command-fokus-design.md` | the atlas amendment (new §5.7 + capacity rules) |
| `app/capabilities/settings/web/DesignGallery.tsx` (+ test) | Zielzustand drafts (new "Target" section, variants labeled) + one specimen per new state |
| `scripts/screenshots.py`, `assets/screenshots/*` | master shots incl. target drafts, both themes |
| `app/capabilities/chat/web/ChatPanel.tsx` (+ `dock.tsx` if it shapes the panel) | conversational turns, source chips, progress + refusal states |
| `app/capabilities/knowledge/web/ChecksPanel.tsx` | consistency-finding card on primitives |
| `app/capabilities/knowledge/web/EntitiesPanel.tsx` | list-row polish only (no rewrite of the 800-line panel) |
| `app/capabilities/*/web/commands.ts` | new rows only for endpoints that already exist |

---

### Task 0: Platz-Atlas (Design, kein Code)

**Files:**
- Modify: `docs/superpowers/specs/2026-11-06-narrare-ui-command-fokus-design.md` (new §5.7 + capacity rules; nothing else)
- Test: none (docs). Verification is the table's completeness check below.

**Interfaces:**
- Consumes: `docs/features/INDEX.md` (all rows incl. `planned`/`idea`), the v1 corpus names, current composition points (`capability.yaml` nav, generated `nav`/`docks`/`commands`/`settingsPages` registries, `IconRail.tsx`, workspace dock column).
- Produces: the slot map every later task builds against.

- [ ] **Step 1: Inventory the future**

List every feature family that will need a UI home: planning tools (scene/gap/structure/timeline/storyboard/character-arc), assist & writing tools (multi-draft, workflows, inline suggestions, co-author, rewrite, unblock, voice, context inspector, slash-commands, prompt history, title/plot assists, dialogue coach, name generator, research), analysis tools (beta reader, sentiment, readability, POV, coreference, sensitivity, voice author/char/drift, literary suite, plot analysis), series, knowledge graph/editor-graph/worldbuilding/merge, consistency rules, stats/costs, import/export/sync, shortcuts, prompts UX.

- [ ] **Step 2: Assign exactly one slot per family**

Slots: Nav-Area (new rail entry) / Dock-Tab (workspace dock child route) / Canvas-Route (full-page capability route) / Command-only (palette row, no surface) / Settings-Cluster. Two slots plausible → record the decision with the reason (one line). No family left unassigned, no family with two homes.

- [ ] **Step 3: Capacity rules (binding)**

Fix in the spec: max nav entries before grouping overflows the rail (with the grouping rule: which families share an area and why); dock-tab overflow behavior at N tabs (N measured against the 352 px column); canvas page geometry pattern (reuse of the workspace column arithmetic or its own, plus shelf/workspace entry points); when a NEW nav area is allowed (almost never — default is dock/canvas/command under an existing area).

- [ ] **Step 4: Verify by reading**

`git diff --stat` shows exactly the spec file; re-read §5.7 and check every family from Step 1 appears exactly once.

- [ ] **Step 5: Commit**

`docs(ui): the placement atlas reserves every future slot` + real `User-visible:` (none in the product — say so) + trailer.

### Task 1: Zielzustand-Entwürfe als Master (Galerie + Shots)

**Files:**
- Modify: `app/capabilities/settings/web/DesignGallery.tsx`, `DesignGallery.test.tsx`, `scripts/screenshots.py`, `assets/screenshots/*`
- Test: gallery unit test (new "Target" section headings present), settings E2E (section visible), screenshots read.

**Interfaces:**
- Consumes: Task 0's atlas (slot per family) and §5.3–§5.5 patterns.
- Produces: the visual master every later slice builds toward; variants only where Task 0 left a real fork.

- [ ] **Step 1: Draft frames from landed primitives**

New gallery section "Target" with one skeleton frame per slot family (planning canvas, analysis dashboard, assist picker entry, extended nav/dock states), built from `Panel`/`Row`/`Notice`/`Button` only — clearly labeled `ENTWURF`, no fake functionality, no new tokens/components. Where Task 0 recorded a real fork (e.g. planning as Canvas vs Dock; nav flat vs grouped), render BOTH variants side by side with the decision note. Single draft everywhere else — variants are for forks, not decoration.

- [ ] **Step 2: Failing test first**

Extend the gallery test with the "Target" headings (RED), implement (GREEN).

- [ ] **Step 3: Re-shoot + read**

Screenshot script covers the Target section in light + dark; read the images (all frames present, labeled, dark differs).

- [ ] **Step 4: Run + commit**

Gallery test, typecheck, `just test-e2e settings`. Commit `docs(screenshots): the target drafts become the visual master` + `User-visible:` + trailer.

### Task 2: Chat dock becomes a conversation

**Files:**
- Modify: `app/capabilities/chat/web/ChatPanel.tsx`, `dock.tsx` (only if it shapes panel chrome)
- Test: `app/capabilities/chat/web/ChatPanel.test.tsx` (extend), chat E2E (`app/capabilities/chat/e2e/`)

**Interfaces:**
- Consumes: `POST /api/chat/ask` (unchanged), `JobStatus`, `Notice`, `Row`.
- Produces: turn list (question → progress → answer + source chips); timeline/cast blocks as cards, not beige boxes.

- [ ] **Step 1: Read the panel and its tests**

Read `ChatPanel.tsx`, `dock.tsx`, the existing test, and one chat E2E file for the `page`/`stack`/`WEB_URL`/de-DE pattern.

- [ ] **Step 2: Write the failing component tests**

Turns render in order (question, then answer); sources render as chips carrying the引用 target (not a bare URL string); a refused ask renders a `Notice` with a retry affordance. RED: new assertions fail on the current form-style panel.

- [ ] **Step 3: Implement**

Same API, same streaming path. States: asking (`JobStatus`), answered (turn + chips), refused (Notice + retry). No new primitive, no token, no backend touch.

- [ ] **Step 4: E2E node**

Chat suite: ask → progress visible → answer turn + at least one source chip; German labels (de-DE fixture pattern).

- [ ] **Step 5: Run**

`pnpm --dir=web vitest run ../app/capabilities/chat/web/ChatPanel.test.tsx`, `pnpm --dir=web typecheck`, `just test-e2e chat`. Expected: PASS.

- [ ] **Step 6: Commit**

`feat(chat): the dock answers as a conversation` + real `User-visible:` + trailer.

---

### Task 3: Knowledge dock earns its primitives

**Files:**
- Modify: `app/capabilities/knowledge/web/ChecksPanel.tsx`, `app/capabilities/knowledge/web/EntitiesPanel.tsx` (rows only)
- Test: extend the panels' tests where they exist; knowledge E2E

**Interfaces:**
- Consumes: checks/entities endpoints (unchanged), `Notice`, `Button`, `Row`, `Panel`.
- Produces: consistency-finding card (finding, evidence, Accept/Discard on `Button`), entity rows with wrapped/clamped names + tag/type filters unchanged.

- [ ] **Step 1: Read panels, tests, one E2E file.**
- [ ] **Step 2: Failing tests** — finding card renders evidence + both actions; a 120-char entity name does not break its row (jsdom: assert wrapping classes, not pixels; pixels belong to E2E).
- [ ] **Step 3: Implement** — card on primitives; rows only, no panel rewrite, no new variant, no token.
- [ ] **Step 4: E2E nodes** — knowledge suite: finding card visible with both actions; long entity name fully readable (scrollWidth idiom); dock at 1280 px with expanded rail: no horizontal overflow (`scrollWidth <= clientWidth` on the dock column).
- [ ] **Step 5: Run** — panel tests, typecheck, `just test-e2e knowledge`. Expected: PASS.
- [ ] **Step 6: Commit** — `feat(knowledge): the dock states its findings on primitives` + `User-visible:` + trailer.

---

### Task 4: Palette gaps for existing backends

**Files:**
- Modify: `app/capabilities/*/web/commands.ts` (rows + lazy dialogs only)
- Test: unit tests for `run` handlers where the capability already tests commands; else E2E nodes in the owning capability's suite.

**Interfaces:**
- Consumes: only endpoints that exist on this branch (`continue_chapter`, `export_novel`, `import_novel`?, checks/extraction triggers — verify by reading each `router.py`).
- Produces: one command row per gap, reusing `JobStatus`/dialogs/diff view. A gap with no backend is listed in the report as OUT, not built.

- [ ] **Step 1: Inventory** — list every `commands.ts` row against its backend endpoint; write the gap list (missing row + existing endpoint) into the task report. Gaps without backends are OUT by the Global Constraints.
- [ ] **Step 2: Failing tests** — one per added command (unit where the pattern exists, else E2E): command runs, progress shows, refusal surfaces in words.
- [ ] **Step 3: Implement** — rows follow the `new-chapter` pattern (data only, dynamic `import()` for dialogs, no component imports at module scope).
- [ ] **Step 4: Run** — the owning suites + typecheck. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(<cap>): palette runs <action>` (one commit; if several capabilities, one commit per capability) + `User-visible:` + trailer each.

---

### Task 5: Gallery specimens, re-shoot, gates

**Files:**
- Modify: `app/capabilities/settings/web/DesignGallery.tsx`, `DesignGallery.test.tsx`, `scripts/screenshots.py`, `assets/screenshots/*`
- Test: gallery unit test (new sections present), settings E2E (gallery node still green), full gates.

**Interfaces:**
- Consumes: Tasks 2–4 states (plus Task 1's drafts, which it extends with specimens).
- Produces: specimens (conversation turn + chips, consistency card, wrapped entity row, one palette-triggered dialog state if headless-renderable — else its button row), both themes shot.

- [ ] **Step 1: Specimens + failing test** — extend the gallery test with the new section headings (RED), implement sections from the real panels' primitives (no copy-pasted logic; specimens, not embeds).
- [ ] **Step 2: Re-shoot** — script command; read the new/changed images (four sections + new specimens present, dark differs, no expanded rail over the gallery).
- [ ] **Step 3: Full gates** — `just check`, full frontend suite, `just test-e2e settings chat knowledge` (or affected), web build with clean chunks.
- [ ] **Step 4: Commit** — `docs(screenshots): the gallery pins the dock and palette states` + `User-visible:` + trailer. Report, no code.

---

## Self-Review

**Spec coverage.** Atlas→T0 (every future family gets one slot); master drafts→T1 (variants only at recorded forks); §5.3→T2+T3 (dock content on primitives; shell chrome itself already landed); §5.4→T4 (palette rows for existing backends; slash-commands tie to multi-draft-era editor work, out of slice); §5.5→T2+T5 (diff markers already landed in prompts; multi-draft compare waits on WRITE-008's backend); canvas routes→atlas assigns them now, backends come later. Nothing in §5 lacks an owner.

**Type consistency.** Command rows follow the `Command` contract (`titleKey` checked against the catalog at build); gallery specimens reuse, never reimplement.

**Review Focus.** Five lines, each with its owning task + test: refusal→T1, long entity→T2, command refusal→T3, dark→T4, 1280px rail→T1/T2.

**Proportion.** Decisions and values are named; bodies appear only where the shape is the decision (E2E idioms, commit scopes).
