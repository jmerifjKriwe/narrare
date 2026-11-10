# UI Command-Fokus, Slice 5 — Timeline-Landing (P1) + Planen-Nav-Area — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Planen nav area opens with a Timeline landing canvas: manually curated story events in chronological and by-chapter views, backed by a new `timeline_events` table with CRUD — no AI extraction, no character ages, no consistency engine (follow-ups).

**Architecture:** `planning` capability gains `nav: true` (5th rail area, new `--area-planning` token measured ≥3:1) + `TimelineEvent` model/migration + per-novel CRUD + lazy `/planning` landing with chronological/by-chapter views + gallery specimen + shots.

**Tech Stack:** Python 3.14 · FastAPI · SQLAlchemy async · Alembic · Vite · React 19 · TanStack Router · Vitest · Playwright E2E.

**Spec:** `docs/superpowers/specs/2026-11-06-narrare-ui-command-fokus-design.md` (§5.3 canvas, §5.7 P1: Timeline landing under Nav-Area Planen, Storyboard/Struktur later siblings) + v1 `docs/features/planning/PLAN-004-architecture.md` (table definition `timeline_events`, CRUD shape) — v1 AI phases explicitly out of scope here.

## Global Constraints

- English in code, tests and developer documentation; user-visible text en/de/fr in the capability catalog (`app/capabilities/planning/web/i18n/*.json`). A missing key is a build error.
- One capability is one folder; no cross-capability imports; shared UI via `@shell/*`.
- Tokens only from `web/globals.css`; the new `--area-planning` hue must clear ≥3:1 vs `--panel` in both themes (measured, recorded); no other new token, no new primitive.
- Table scope (v1 trimmed): id, novel_id (FK CASCADE + index, user-scoped), chapter_id nullable (FK SET NULL), title/name, description, temporal position (order integer + optional free-text date — exact columns mirror v1 §"New Table" minus AI/consistency columns), character refs as free-text names for now (hybrid KB refs deferred with the scene refs); created/updated. No AI columns, no age columns.
- Every `feat` commit carries a real `User-visible:` line and the trailer `Assisted-by: OpenCode (<model>)` via `git commit --trailer`. Nothing committed before the task's review is green.
- Gates: `just check` · `just test-file <path>` · `pnpm --dir=web vitest run <path>` · `just generate` after facts change · `just test-e2e planning` (ports 8100/3200 if needed) · web build at the end.
- E2E contexts use locale de-DE.

## Review Focus

1. **A novel with no events / no chapters** — honest empty states naming the next step, not an empty canvas. (Task 2.)
2. **Undated events** — order position always renders; free-text date is optional garnish, never the sort key. (Tasks 1–2.)
3. **A failed write/delete** — Notice + retry, no silent loss. (Task 2.)
4. **200 events** — cap with "showing N of M", no unbounded render. (Task 2.)
5. **The 5th rail area** — hue measured ≥3:1 both themes; rail still fits (max-7 rule: this is entry 5 of 7). (Task 2.)

---

## File Structure

| File | Responsibility |
| --- | --- |
| `app/capabilities/planning/models.py`, migration | `timeline_events` table |
| `app/capabilities/planning/{timeline_schemas,timeline_service,timeline_repository,router_timeline}.py` (v1 file split honored where the repo's shape demands it; single-module if the repo's capability shape prefers it — read writing/knowledge first) | per-novel CRUD, chapter filter |
| `app/capabilities/planning/capability.yaml` | `nav: true`, path `/planning` (title key exists) |
| `web/globals.css`, `web/ui/typeScale.test.ts` (census) | `--area-planning` token + census coverage |
| `app/capabilities/planning/web/{PlanningPage,routes}.tsx` + tests, i18n | landing canvas: chronological + by-chapter views, add/edit/delete |
| `app/capabilities/settings/web/DesignGallery.tsx` (+ test), scripts/screenshots | specimen + shots |

---

### Task 0: Timeline substrate + CRUD API

**Files:** model + migration; service/router/repository (or single-module per repo shape — read first, then follow the shape); tests; `just generate` artifacts.

- [ ] **Step 1: Read the v1 table + repo shape** — `PLAN-004-architecture.md` §"New Table" for columns/indexes; `app/capabilities/writing` or `knowledge` for where service/router/repository live in v2 (mirror, do not invent).
- [ ] **Step 2: Failing tests** — CRUD round-trip per novel (create with order+chapter, list ordered, update, delete), cross-novel isolation (foreign novel ≡ empty/404 per sibling convention), validation (empty title rejected), timestamps server-owned.
- [ ] **Step 3: Implement** — model, migration (`just db-revision`), service, router, `just generate`, `just check`.
- [ ] **Step 4: Run** — `just test-file` on the new tests + affected suite. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(planning): timeline events substrate and CRUD` + real `User-visible:` + trailer.

### Task 1: Planen nav area + Timeline landing canvas

**Files:** `capability.yaml` (`nav: true`), `web/globals.css` (+ census), `PlanningPage.tsx` (+ test), `routes.tsx` (root-parented `/planning`), i18n keys, entry link (shelf or workspace — follow the atlas cross-link rule; if none exists yet, the nav entry is the entry).

- [ ] **Step 1: Failing component tests** — empty novel (empty state names the next step); seeded events render in chronological order; by-chapter grouping; add/edit/delete flow through the mocked API; failed write → Notice + retry.
- [ ] **Step 2: Token + census** — add `--area-planning` (light/dark, measured ≥3:1 vs `--panel` both themes; record ratios in the report), extend the area-hue census to the new area the way Task B3 did it (read that test first).
- [ ] **Step 3: Implement** — lazy page, two views (chronological / by chapter), add/edit/delete dialogs on existing primitives, no new token/component; 200-event cap with "showing N of M"; rail entry appears via generated `nav` (no hand-written nav).
- [ ] **Step 4: E2E** — planning suite: seed novel + chapters + events, open `/planning`, both views render German labels, add → persists after reload, 1280px no horizontal page scroll.
- [ ] **Step 5: Run** — component tests, typecheck, `just test-e2e planning`. Expected: PASS.
- [ ] **Step 6: Commit** — `feat(planning): timeline landing canvas under a Planen area` + real `User-visible:` + trailer.

### Task 2: Specimen, re-shoot, gates

**Files:** `DesignGallery.tsx` (+ test), `scripts/screenshots.py`, `assets/screenshots/*` (new timeline shots; re-shoot only what changed).

- [ ] **Step 1: Specimen + failing test** — timeline specimen (inert, real primitives), RED → GREEN.
- [ ] **Step 2: Re-shoot + read** — new shots present, dark differs, no expanded rail over gallery; revert noise-only rewrites of other shots.
- [ ] **Step 3: Full gates** — `just check`, frontend suite, `just test-e2e planning settings`, web build with clean chunks.
- [ ] **Step 4: Commit** — `docs(screenshots): the timeline canvas pinned in both themes` + `User-visible:` + trailer. Report, no code.

---

## Self-Review

**Spec coverage.** P1→T0–T2 (landing + manual CRUD; AI extraction/consistency/ages explicitly out — no backend for them in this slice); nav-area rule satisfied (5th entry, max-7 holds); canvas rules from §5.3 honored (full-page route, entry via nav, gallery specimen).

**Type consistency.** Event shape defined once in T0's schemas, consumed by T1's page and T2's specimen.

**Review Focus.** Five lines, each with its owning task + test: empty→T1; undated→T0/T1; failed write→T1; 200-cap→T1; rail hue→T1.

**Proportion.** Decisions and API shapes named; bodies only where the shape is the decision (column set, nav flip, view split).
