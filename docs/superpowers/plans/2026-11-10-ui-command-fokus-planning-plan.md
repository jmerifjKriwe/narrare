# UI Command-Fokus, Slice 4 — Planen-Area: Scene Plans (P2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Planen area's first foothold: chapter scene plans with a versioned substrate plus the workspace dock tab that edits them beside the manuscript — no AI generation yet (zero-write draft/refine is the follow-up slice).

**Architecture:** New `planning` capability (scaffold + `scene_plans` table + migration), chapter-aggregate GET/PUT with server-side diff-sync on stable scene ids (v1 PLAN-001 semantics, ported), dock tab via `dockRoutes` (picked up by the generated registry, no generator change), gallery specimen + screenshots.

**Tech Stack:** Python 3.14 · FastAPI · SQLAlchemy async · Alembic · Postgres · Vite · React 19 · TanStack Router · Vitest · Playwright E2E.

**Spec:** `docs/superpowers/specs/2026-11-06-narrare-ui-command-fokus-design.md` (§5.3 dock, §5.7 P2: Dock statt Canvas; P1 timeline canvas explicitly later) + v1 `docs/features/planning/PLAN-001-scene-planning.md` (substrate + diff-sync contract) + `docs/_shared/CONSTRAINTS.md` (capability shape).

## Global Constraints

- English in code, tests and developer documentation; user-visible text en/de/fr in the capability catalog (`app/capabilities/planning/web/i18n/*.json` per scaffold). A missing key is a build error.
- One capability is one folder (`app/capabilities/planning/`); never imports another capability; shared UI via `@shell/*`; shell reaches it only through generated tables.
- Tokens only from `web/globals.css`; no new primitive, no new token.
- New table + migration allowed (this slice's explicit scope); no other schema touch; no second store.
- v1 field scope for this slice: title, status (`planned|in_progress|complete`, manual only), purpose, conflict, resolution, beats (plain text). DEFERRED with reason: hybrid KB refs (pov/location/present-characters with id+name, RULE-22 lifecycle) — needs the ref-index consumer contract; and AI draft/refine (zero-write) — needs the v2 LLM path decision. Both recorded as follow-ups, not silently dropped.
- Diff-sync law (from v1): known id → update; unknown id → 422; duplicate id → 422 before any write; absent id → delete; positions renumbered 1..N by payload order; ownership uid-scoped (foreign novel ≡ 404). Timestamps server-owned.
- Every `feat`/`fix` commit carries a real `User-visible:` line and the trailer `Assisted-by: OpenCode (<model>)` via `git commit --trailer`. Author and committer stay human.
- Nothing is committed before the task's review is green.
- Gates: `just check` · `just test-file <path>` · `pnpm --dir=web vitest run <path>` · `just generate` after facts change · `just test-e2e planning` (ports 8100/3200 if 8000/3100 held) · web build at the end.
- E2E contexts use locale de-DE.

## Review Focus

1. **A PUT with unknown/duplicate ids** — 422 before ANY write (aggregate untouched, proven by refetch). (Task 1.)
2. **A foreign novel's chapter id** — 404, indistinguishable from unknown (no oracle). (Task 1.)
3. **Two editors saving concurrently** — last-writer-wins on positions is accepted and documented; no silent field merge is claimed. (Task 1, documented, not tested.)
4. **A chapter with 50 scenes in the dock** — list scrolls inside the dock column, page doesn't grow. (Task 2, E2E height assert.)
5. **Dark theme + German labels on every new surface.** (Tasks 2–3.)

---

## File Structure

| File | Responsibility |
| --- | --- |
| `app/capabilities/planning/` | scaffold: `__init__`, `capability.yaml` (`nav: false` — dock-only for now), router/service/repository/schemas, `models.py`, migration, tests, e2e |
| `app/capabilities/planning/web/` | `routes.tsx` (dockRoutes only), `SceneDock.tsx` (+ test), `web/i18n/{en,de,fr}.json`, `commands.ts` (only if a palette row is needed — default: none) |
| `app/capabilities/settings/web/DesignGallery.tsx` (+ test) | Target-vs-Specimen: planning dock specimen |
| `scripts/screenshots.py`, `assets/screenshots/*` | dock specimen shot if the script covers docks (else gallery-only) |

---

### Task 0: Capability scaffold + substrate

**Files:**
- Create: `app/capabilities/planning/` via `just new-capability planning`, then `capability.yaml` (`nav: false`), `models.py` (`scene_plans` per v1 §ScenePlan minus hybrid-ref columns: keep `pov_name`, `location_name` free-text columns? NO — deferred entirely; columns: id, chapter_id FK CASCADE + index, position, title, purpose, conflict, resolution, beats JSONB, status, created/updated_at), migration via `just db-revision`, tests + e2e conftest (scaffold), `web/i18n/*.json` translated.

**Interfaces:**
- Produces: `ScenePlan` row shape; `capability.yaml` facts for `just generate`.

- [ ] **Step 1: Scaffold + facts** — Run `just new-capability planning`; set `nav: false`, path `/planning` (dock-only; no top-level route yet — the dock factory parents under the workspace); translate the three heading keys properly (no English placeholders left).
- [ ] **Step 2: Model + migration** — `models.py` per the column list above (user_id scoping per rule 4 — check how sibling capabilities scope rows and mirror it); `just db-revision "add scene_plans"`; read the migration file, confirm only the new table + index.
- [ ] **Step 3: Generate + check** — `just generate` (registry must name the capability before the app boots), `just check`. Expected: green.
- [ ] **Step 4: Commit** — `feat(planning): scene-plan substrate` + `User-visible:` (none user-facing yet — say so) + trailer.

### Task 1: Aggregate API with diff-sync

**Files:**
- Create/modify: `schemas.py`, `service.py`, `router.py`, tests beside existing capability tests.
- Test: aggregate tests (seed 3 scenes; PUT reorder+edit+delete+add; unknown/duplicate id 422 with aggregate unchanged; foreign novel 404; timestamps server-owned).

- [ ] **Step 1: Failing tests** — RED: 404 on the aggregate route (no router yet).
- [ ] **Step 2: Implement** — `GET /novels/{id}/chapters/{cid}/scenes` (aggregate read, no auto-create) + `PUT` with diff-sync law; service delegates immediately per capability shape; validator rejects duplicate/unknown ids before any write.
- [ ] **Step 3: Run** — `just test-file` on the new test + `just check`. Expected: PASS.
- [ ] **Step 4: Commit** — `feat(planning): chapter scene aggregate with diff-sync` + real `User-visible:` + trailer.

### Task 2: Dock tab beside the editor

**Files:**
- Create: `app/capabilities/planning/web/routes.tsx` (dockRoutes factory only), `SceneDock.tsx` (+ test), i18n keys.
- Test: component test (list renders, status cycles planned→in_progress→complete, add/reorder/delete mark dirty, save → PUT, refused save → Notice + retry); knowledge-style E2E node in `app/capabilities/planning/e2e/`.

- [ ] **Step 1: Read the dock contract** — knowledge `dock.tsx` + generated `docks.ts` + `NovelPage` tab rendering (how tabs mount, search params, 1280px behavior).
- [ ] **Step 2: Failing component tests** — list from mocked aggregate; status advance writes through the mocked PUT; dirty-guarded close (reuse the LeaveGuard/prompt pattern — check what writing/prompts use; do NOT invent a third guard).
- [ ] **Step 3: Implement** — panel on `Notice`/`Button`/`Row` (no new primitive/token); dirty state vs server snapshot; save → aggregate PUT → invalidate; 50-scene scroll containment (dock-internal scroll, `min-h-0`/`overflow-y-auto` per the workspace column pattern).
- [ ] **Step 4: E2E** — planning suite: seed novel+chapter+2 scenes, open dock, edit title, advance status, save, reload → persisted; German labels (de-DE); 1280px rail-expanded: dock column scrolls internally (`scrollHeight > clientHeight` allowed inside, page `document` fits).
- [ ] **Step 5: Run** — component tests, typecheck, `just test-e2e planning`. Expected: PASS.
- [ ] **Step 6: Commit** — `feat(planning): scene plans dock beside the editor` + real `User-visible:` + trailer.

### Task 3: Specimen, re-shoot, gates

**Files:**
- Modify: `DesignGallery.tsx` (+ test), `scripts/screenshots.py` (only if it shoots docks — else gallery-only + note why), `assets/screenshots/*`
- Test: gallery test (new section), full gates.

- [ ] **Step 1: Specimen + failing test** — planning-dock specimen (inert, from real primitives; Target drafts untouched).
- [ ] **Step 2: Re-shoot + read** — new shots present, dark differs, no expanded rail over the gallery.
- [ ] **Step 3: Full gates** — `just check`, frontend suite, `just test-e2e planning settings` (settings only if gallery changed), web build with clean chunks.
- [ ] **Step 4: Commit** — `docs(screenshots): the planning dock pinned` + `User-visible:` + trailer. Report, no code.

---

## Self-Review

**Spec coverage.** P2→T0–T3 (dock tab + substrate; hybrid refs + AI explicitly deferred with reasons); P1 canvas explicitly later (needs timeline backend); capacity rules hold (no new nav area yet — rail stays at 6/7; the dock gains one tab under the max-6 rule).

**Type consistency.** Aggregate shape defined once in T1's schemas, consumed by T2's hook; dock registration automatic via `dockRoutes` export.

**Review Focus.** Five lines, each with its owning task + test: 422-before-write→T1; foreign-404→T1; concurrent-save documented→T1; 50-scene scroll→T2; dark+de→T2/T3.

**Proportion.** Decisions and API shapes named; bodies only where the shape is the decision (diff-sync law, guard reuse, scroll containment).
