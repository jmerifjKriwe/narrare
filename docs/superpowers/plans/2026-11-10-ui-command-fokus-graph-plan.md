# UI Command-Fokus, Slice 3 — Knowledge-Graph-Canvas (KB-008) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The first real canvas: `/knowledge/graph` renders the novel's entities and relations as a readable, selectable SVG graph — proving the canvas pattern (route, edge, entry points) every later canvas reuses.

**Architecture:** One new read-only list endpoint (`GET /novels/{id}/relations`, no schema change, no migration) feeds a deterministic layout pure function; a lazy `GraphPage` renders nodes/edges + detail panel; entry from the Knowledge page; gallery specimen + screenshots pin it.

**Tech Stack:** Python 3.14 · FastAPI · SQLAlchemy async · Vite · React 19 · TanStack Router · SVG (no graph lib, no new dependency) · Vitest · Playwright E2E.

**Spec:** `docs/superpowers/specs/2026-11-06-narrare-ui-command-fokus-design.md` (§5.3 canvas, §5.7 KB-008 row + P12: full graph lives here, dock lens comes later)

## Global Constraints

- English in code, tests and developer documentation; user-visible text in en, de and fr through the capability catalogs (`app/capabilities/knowledge/web/i18n/*.json`). A missing key is a build error.
- One capability is one folder; capability reaches the shell only through `@shell/*`. No new capability, no new store, no migration in this slice.
- Tokens only from `web/globals.css`; no new primitive, no new token, no new gate.
- The graph is READ-ONLY in this slice: no create/edit/delete UI for entities or relations (those live in the docks). Selecting shows detail; editing navigates to the dock.
- Every `feat`/`fix` commit carries a real `User-visible:` line and the trailer `Assisted-by: OpenCode (<model>)` via `git commit --trailer`. Author and committer stay human.
- Nothing is committed before the task's review is green.
- Gates: `just check` · `just test-file <path>` · `pnpm --dir=web vitest run <path>` · `just test-e2e knowledge` (ports 8100/3200 if 8000/3100 held) · `just generate` after API change · web build at the end.
- E2E contexts use locale de-DE.

## Review Focus

1. **A novel with 200 entities** — layout stays deterministic and the page stays usable (cap node/edge counts with a "showing N of M" note rather than rendering unbounded SVG). (Tasks 1–2.)
2. **An entity with no relations / a novel with no entities** — honest empty states, not an empty viewport. (Task 2.)
3. **A refused/failed relations read** — Notice with retry, matching the dock's refusal language. (Task 2.)
4. **Pan/zoom expectations** — explicitly OUT: fit-to-viewport SVG + scroll; interactive pan/zoom is a recorded follow-up, not silent absence. (Task 2.)
5. **Dark theme** — tokens resolve; re-shot in both themes. (Task 3.)

---

## File Structure

| File | Responsibility |
| --- | --- |
| `app/capabilities/knowledge/{router,service,repository}.py` + tests | `GET /novels/{novel_id}/relations` read path only |
| `app/capabilities/knowledge/web/graphLayout.ts` (+ test) | deterministic layout pure function: nodes → positions, edges → lines |
| `app/capabilities/knowledge/web/GraphPage.tsx` (+ test) | canvas page: SVG, select → detail, empty/loading/error |
| `app/capabilities/knowledge/web/routes.tsx` | `/knowledge/graph` root-parented lazy route in `routes` |
| `app/capabilities/knowledge/web/KnowledgePage.tsx` | entry link ("Im Graphen öffnen"-wording per atlas cross-link) |
| `app/capabilities/settings/web/DesignGallery.tsx` (+ test) | Target-vs-Specimen: atlas draft stays, built-state specimen added |
| `scripts/screenshots.py`, `assets/screenshots/*` | graph shots light+dark |

---

### Task 0: The read path (backend, read-only)

**Files:**
- Modify: `app/capabilities/knowledge/router.py`, `service.py`, `repository.py` (or wherever the relations read lives — first step is to locate it and mirror its shape), generated `web/lib/api/*` + `openapi.json` via `just generate`.
- Test: capability tests beside the existing relations tests.

- [ ] **Step 1: Locate the relations read** — find the repository function behind `GET /entities/{id}/relations`; the new path reuses its row mapping.
- [ ] **Step 2: Failing test** — `GET /novels/{novel_id}/relations` returns exactly the union of the novel's entities' relations (seed 2 entities + 1 relation + 1 unrelated novel's data as noise); unknown novel → 404 per existing convention (verify the convention first).
- [ ] **Step 3: Implement** — service + router, read-only, no schema change, no migration. `just generate`, then `just check`.
- [ ] **Step 4: Run** — `just test-file` on the new/neighbor test file. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(knowledge): list a novel's relations` + `User-visible:` + trailer.

### Task 1: Deterministic layout (pure function)

**Files:**
- Create: `app/capabilities/knowledge/web/graphLayout.ts`, `graphLayout.test.ts`
- Test: the new unit test only.

- [ ] **Step 1: Failing tests** — fixed seed graph (5 entities, 2 types, 4 relations incl. a cycle + an isolated node): same input → byte-identical positions (run twice, deep-equal); all nodes inside the viewport box; isolated node placed, not dropped; edges reference existing node ids.
- [ ] **Step 2: Implement** — pure function, no DOM, no randomness (seeded PRNG if jitter is needed); groups by entity type, layered/radial arrangement that fits `viewBox`; cap: function takes `maxNodes`/`maxEdges` and reports truncation counts (page renders the "showing N of M" note).
- [ ] **Step 3: Run** — `pnpm --dir=web vitest run ../app/capabilities/knowledge/web/graphLayout.test.ts`, typecheck. Expected: PASS.
- [ ] **Step 4: Commit** — `feat(knowledge): deterministic graph layout` + `User-visible:` (none user-facing yet — say so) + trailer.

### Task 2: The canvas page + route + entry

**Files:**
- Create: `app/capabilities/knowledge/web/GraphPage.tsx`, `GraphPage.test.tsx`
- Modify: `app/capabilities/knowledge/web/routes.tsx`, `KnowledgePage.tsx`, i18n catalogs (capability-locales).
- Test: component test (select → detail, empty states) + knowledge E2E node.

- [ ] **Step 1: Read the route + page patterns** — knowledge `routes.tsx` lazy pattern, `KnowledgePage.tsx` entry-point placement, dock deep-link search contract (for later, not this slice).
- [ ] **Step 2: Failing component tests** — seeded store: nodes render with names, edges render between them; click node → detail panel shows content; empty novel → empty state; failed read → Notice + retry.
- [ ] **Step 3: Implement** — lazy page, SVG from Task 1's layout, fit-to-viewport (no pan/zoom — record as follow-up in code comment + report), select → detail panel (read-only; "edit in dock" link), entry link on KnowledgePage ("Im Graphen öffnen"), catalog keys en/de(/fr — capability-locales: check which locales exist).
- [ ] **Step 4: E2E** — knowledge suite: seed 2 entities + 1 relation, open `/knowledge/graph`, nodes + edge visible, click → detail, German labels. Plus 1280px no-overflow assert (canvas owns the page — assert `document` has no horizontal scrollbar).
- [ ] **Step 5: Run** — component tests, typecheck, `just test-e2e knowledge`. Expected: PASS.
- [ ] **Step 6: Commit** — `feat(knowledge): the entity graph as a full-page canvas` + real `User-visible:` + trailer.

### Task 3: Specimen, re-shoot, gates

**Files:**
- Modify: `DesignGallery.tsx` (+ test), `scripts/screenshots.py`, `assets/screenshots/*`
- Test: gallery unit test (new specimen section), settings E2E node still green, full gates.

- [ ] **Step 1: Specimen + failing test** — graph specimen (mini static render from real primitives/shape, clearly marked built-state vs the Target draft which stays as the fork record) — RED, then GREEN.
- [ ] **Step 2: Re-shoot** — graph light+dark + gallery; read all four (graph readable, selected node detail, dark differs, no expanded rail over gallery).
- [ ] **Step 3: Full gates** — `just check`, frontend suite, `just test-e2e knowledge settings`, web build with clean chunks.
- [ ] **Step 4: Commit** — `docs(screenshots): the graph canvas pinned in both themes` + `User-visible:` + trailer. Report, no code.

---

## Self-Review

**Spec coverage.** KB-008 canvas→T0–T3 (route, edge, entry, specimen); P12 lens explicitly later (dock follows in its own slice); capacity rules hold (one more canvas under Wissen, no new area, no new token); read-only scope keeps the docks as the editing surface.

**Type consistency.** Layout input/output shapes defined once in T1 and consumed in T2; endpoint shape from T0's test travels into the page's hook.

**Review Focus.** Five lines, each with its owning task + test: 200-entity cap→T1+T2; empty→T2; refusal→T2; pan/zoom OUT→T2 comment+report; dark→T3.

**Proportion.** Decisions and values named; bodies only where the shape is the decision (layout determinism, route pattern, E2E idioms).
