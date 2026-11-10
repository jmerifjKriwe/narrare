# UI Command-Fokus, Slice 7 — Frontend-only Rest + Backlog-Doku — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land every remaining atlas item that needs no new backend (structure canvas, knowledge neighborhood lens), write the backend-blocked remainder down as a design backlog, and re-shoot every screenshot.

**Architecture:** Structure canvas reads the existing storyboard aggregate; the lens reuses `graphLayout` + the entity relations endpoint behind a knowledge-dock switcher; the backlog is one spec page; the re-shoot is docs-only. No new endpoint, no migration, no new token.

**Tech Stack:** Vite · React 19 · TanStack Router · Vitest · Playwright E2E · `scripts/screenshots.py`.

**Spec:** `docs/superpowers/specs/2026-11-06-narrare-ui-command-fokus-design.md` §5.7 (PLAN-003 story-structure canvas, P12 knowledge dock lens, capacity rules) + §5.3/§5.5.

## Global Constraints

- English in code, tests and developer documentation; user-visible text en/de/fr in the owning capability catalog. A missing key is a build error.
- No new backend endpoint, no schema change, no migration in this slice. If an item needs one, it belongs in Task 2's backlog, not in code here.
- No new primitive, no new token, no new gate. The shared canvas edge `mx-auto max-w-[1200px] px-4` binds every canvas route (§5.7.2).
- Dock capacity: no new dock tab. The lens is a *switcher inside* the existing Wissen dock (atlas P12), never a fourth tab.
- Commit grammar (AGENTS.md): `feat`/`fix` need a real `User-visible:` line; development documentation and plans use a hidden type (`chore`), no `User-visible:` line. Trailer `Assisted-by: OpenCode (<model>)` via `git commit --trailer`.
- Nothing is committed before the task's review is green.
- Gates: `just check` · `pnpm --dir=web vitest run <path>` · `just test-e2e planning knowledge settings` (ports 8100/3200 if 8000/3100 held) · web build.
- E2E contexts use locale de-DE.

## Review Focus

1. **A single-chapter novel on the structure canvas** — proportion bar must not divide by zero; one act holds everything. (Task 0.)
2. **A novel with zero chapters** — honest empty state, no empty frame. (Task 0.)
3. **The lens with nothing selected** — names the next step (pick an entity), does not render an empty SVG. (Task 1.)
4. **A selected entity with no relations** — shows the entity alone, says so; no silent blank. (Task 1.)
5. **A stale `?entity=` id** in the lens — degrades to the empty state like the dock's list does. (Task 1.)

---

## File Structure

| File | Responsibility |
| --- | --- |
| `app/capabilities/planning/web/StructurePage.tsx` (+ test), `routes.tsx`, i18n | proportion-of-story canvas from the storyboard aggregate |
| `app/capabilities/planning/web/PlanningPage.tsx` | one entry link to the structure canvas (timeline landing, `?novel=` carried) |
| `app/capabilities/knowledge/web/NeighborhoodLens.tsx` (+ test), `dock.tsx`, i18n | switcher inside the Wissen dock + hop-1 lens from `?entity=` |
| `docs/superpowers/specs/2026-11-10-ui-command-fokus-backlog-design.md` | the backend-blocked remainder, per family |
| `assets/screenshots/*`, `scripts/screenshots.py` | full re-shoot |

---

### Task 0: Structure canvas (PLAN-003)

**Interfaces:** consumes `GET /api/planning/novels/{id}/storyboard` (shape: `{novel_id, structure_id, stages:[{key, title_key, from, to, chapters:[{chapter_id, title, position, word_count, sync_status, assignment_source, stage_key}]}]}`).

- [ ] **Step 1: Read** the storyboard page + route for the pattern (lazy, `?novel=` picker, canvas edge, empty states) and the atlas row for PLAN-003 (Akt-/Kapitel-Visualisierung, räumlich).
- [ ] **Step 2: Failing component tests** — seeded aggregate renders one band per stage, band width proportional to `to - from`; chapters appear inside their band ordered by position; a chapter with `sync_status: deviated` is marked; single-chapter novel renders (no division by zero); zero chapters → empty state naming the next step; chapter click navigates to `/novels/$id?chapter=`.
- [ ] **Step 3: Implement** — `/planning/structure` lazy root-parented route; a proportion bar (stage bands sized by ratios) with chapter marks inside; a summary line (chapters, words, deviations); primitives only; shared canvas edge; entry link from the timeline landing carrying `?novel=`; one palette row (`commands.ts`) to open it. No writes on this page: it is a read-only view, moves stay on the storyboard.
- [ ] **Step 4: E2E** — planning suite: seed novel + chapters, open `/planning/structure`, German labels, deviation marker visible, click → workspace, 1280px no horizontal page scroll.
- [ ] **Step 5: Gates + commit** — component tests, typecheck, `just test-e2e planning`; commit `feat(planning): the story's shape as a proportion canvas` + real `User-visible:` + trailer.

### Task 1: Knowledge neighborhood lens (P12)

- [ ] **Step 1: Read** `dock.tsx`, `EntitiesPanel.tsx` (the `?entity=` contract), `graphLayout.ts` (input/output shapes) and `GraphPage.tsx` (SVG idiom), plus the atlas row P12.
- [ ] **Step 2: Failing component tests** — nothing selected → names the next step; selected entity with two neighbors renders three nodes and two edges; entity with no relations renders alone and says so; stale `?entity=` degrades to the empty state; the cross-link to `/knowledge/graph` carries the novel.
- [ ] **Step 3: Implement** — a two-option switcher at the top of the Wissen dock (`Liste` | `Nachbarschaft`, existing Button/segmented idiom from the storyboard switcher — no new primitive); the lens builds a hop-1 sub-graph (selected entity + direct neighbors + edges between them) and lays it out with the existing `graphLayout` function; renders with the same SVG node/edge idiom as `GraphPage` (selected node marked, keyboard-selectable neighbors); cross-link "Im Graphen öffnen"; no writes, no new endpoint.
- [ ] **Step 4: E2E** — knowledge suite: seed 2 entities + 1 relation, select one, switch to Nachbarschaft, both names visible + cross-link carries the novel; German labels.
- [ ] **Step 5: Gates + commit** — component tests, typecheck, `just test-e2e knowledge`; commit `feat(knowledge): the dock shows an entity's neighborhood` + real `User-visible:` + trailer.

### Task 2: The backend-blocked remainder, written down

- [ ] **Step 1: Inventory** — every atlas row still unimplemented after Tasks 0–1, plus the cross-cutting deferrals (hybrid KB refs, scene AI, storyboard DnD/AI-remap/extra structures, timeline AI/ages/consistency, graph pan/zoom, stats/costs, series, shortcuts config, consistency rules, external sync, worldbuilding, multi-draft/co-author/unblock/voice/context/plot-check/dialog-coach/research docks, command-only rows needing LLM).
- [ ] **Step 2: Write** `docs/superpowers/specs/2026-11-10-ui-command-fokus-backlog-design.md`: one table row per family with atlas slot (P-number), what exists today, the missing backend contract (endpoints/tables in prose), the UI shape already decided, the entry point, and the one decision a later planning session must make first. Mark anything already covered by an existing endpoint as "no backend needed — schedule freely".
- [ ] **Step 3: Verify by reading** — every atlas row from §5.7 appears exactly once (done, backlog, or out-of-atlas), and no row claims work that Tasks 0–1 just delivered.
- [ ] **Step 4: Commit** — `chore(docs): the atlas remainder and what each item needs` (hidden type, no `User-visible:`). Report, no code.

### Task 3: Re-shoot all frames

Depends on Tasks 0–2.

- [ ] **Step 1: Re-shoot** — run the screenshot script (ephemeral stack; 8100/3200 if needed). If the new canvases deserve their own shots, add them following the established chosen-dark pattern.
- [ ] **Step 2: Triage every rewrite** — keep only real content changes (5-icon rail, new canvases, new specimens); revert pure noise with `git checkout -- <file>`; justify each decision in the report.
- [ ] **Step 3: Read** every kept PNG — 5-icon rail, correct content, dark differs, no expanded rail over the gallery.
- [ ] **Step 4: Gates + commit** — `just check`, frontend suite, `just test-e2e settings planning knowledge`, web build; commit `docs(screenshots): every frame on the current shell` + real `User-visible:` + trailer.

---

## Self-Review

**Spec coverage.** Atlas PLAN-003→T0; P12→T1; everything else that needs a backend→T2 (documented, per owner instruction); re-shoot→T3. Capacity rules hold: no new nav area, no new dock tab (switcher inside Wissen), canvases share the edge.

**Type consistency.** T0 consumes the storyboard aggregate as already typed; T1 consumes `graphLayout`'s existing input shapes.

**Review Focus.** Five lines, each with its owning task + test: single-chapter→T0; zero-chapter→T0; nothing-selected→T1; no-relations→T1; stale-id→T1.

**Proportion.** Decisions and contracts named; bodies only where the shape is the decision (band proportions, sub-graph rule, backlog table columns).
