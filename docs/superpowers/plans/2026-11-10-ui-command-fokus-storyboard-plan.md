# UI Command-Fokus, Slice 6 — Storyboard-Canvas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A storyboard canvas under the Planen area: chapters grouped into structure stages with sync badges, move-between-stages, and a structure-switch remap preview — no drag&drop, no AI modes.

**Architecture:** Two small planning-owned tables (`planning_novel_settings`, `chapter_stages`) + migration; read aggregate + granular stage PUT + remap preview/confirm POST; data-driven structure registry (Three-Act, Hero's Journey); lazy `/planning/storyboard` sibling route (?novel= picker pattern reused); gallery specimen + shots.

**Tech Stack:** Python 3.14 · FastAPI · SQLAlchemy async · Alembic · Vite · React 19 · TanStack Router · Vitest · Playwright E2E.

**Spec:** `docs/superpowers/specs/2026-11-06-narrare-ui-command-fokus-design.md` §5.3 canvas, §5.7 storyboard row (Canvas-Route unter Planen; Timeline-Landing als Sibling; Auswahl per Stage-Menü statt Drag&Drop als Slice-Entscheid) + v1 `docs/features/planning/PLAN-005-storyboard.md` (5-Level-Sync, Remap-Workflow — AI-Modi explizit draußen).

## Global Constraints

- English in code, tests and developer documentation; user-visible text en/de/fr in the capability catalog (`app/capabilities/planning/web/i18n/*.json`). A missing key is a build error.
- One capability is one folder; no cross-capability imports; shared UI via `@shell/*`.
- Tokens only from `web/globals.css`; no new primitive, no new token, no new gate.
- New tables allowed (migration, reversible, CASCADE semantics below); no other schema touch.
- v1 scope for this slice, explicitly: manual stage assignment + position-ratio suggestion + remap preview/confirm; sync from scene plans + word counts. OUT (follow-ups, not dropped): drag&drop (HTML5 or lib — needs its own a11y story), AI remap modes, per-scene sync, Save-the-Cat/Five-Act adapters.
- Every `feat` commit carries a real `User-visible:` line and the trailer `Assisted-by: OpenCode (<model>)` via `git commit --trailer`. Nothing is committed before the task's review is green.
- Gates: `just check` · `just test-file <path>` · `pnpm --dir=web vitest run <path>` · `just generate` after API change · `just test-e2e planning` (ports 8100/3200 if needed) · web build at the end.
- E2E contexts use locale de-DE.

## Review Focus

1. **A chapter with no assignment** — suggested stage shown as suggestion, not silently assigned; nothing written until the writer acts. (Task 0.)
2. **Remap confirm writes exactly the previewed mapping** — preview response and applied result agree chapter-by-chapter (asserted in test). (Task 0.)
3. **A failed stage PUT** — card snaps back, Notice + retry, no silent divergence. (Task 1.)
4. **200 chapters** — cap with "showing N of M" per column or canvas-wide; no unbounded render. (Task 1.)
5. **Dark theme + German labels on the new canvas.** (Tasks 1–2.)

---

## File Structure

| File | Responsibility |
| --- | --- |
| `app/capabilities/planning/models.py` (+ migration) | `planning_novel_settings` (novel_id PK FK novels CASCADE, story_structure, default three-act) + `chapter_stages` (chapter_id PK FK chapters CASCADE, stage_key, updated_at), both user-scoped like `timeline_events` |
| `app/capabilities/planning/{service,router}.py` (+ schemas as the file needs) | `GET /novels/{id}/storyboard` (structure id, stages with chapters incl. sync + assignment source), `PUT .../chapters/{cid}/stage` {stage_key}, `POST .../remap` {structure_id, confirm} → preview mapping or apply |
| `app/capabilities/planning/web/StoryboardPage.tsx` (+ test), routes entry | lazy `/planning/storyboard` (`?novel=` picker pattern reused), stage columns, chapter cards, move control, structure switcher + remap dialog |
| `app/capabilities/settings/web/DesignGallery.tsx` (+ test), scripts/screenshots.py | specimen + new shots |

## Data Contract (binding)

- Structures registry (backend constant, mirrored in UI copy): `three-act` (Setup 0–0.25, Confrontation 0.25–0.75, Resolution 0.75–1.0), `heros-journey` (12 stages, even twelfths). Stage = `{key, titleKey, from, to}`; suggestion = stage whose range contains `position / max(1, chapter_count - 1)` (single-chapter novel → first stage).
- Sync rule priority (first match wins): EMPTY (no scenes, words==0) → PLANNED (scenes, words==0) → DEVIATED (assigned ≠ suggested) → COMPLETED (all scenes complete AND words>0) → ON_TRACK (else). Word count reuses the writing repository's counting (same function the shelf uses — read it, do not reimplement).
- Assignment source is explicit in the aggregate: `assigned` (writer-set) vs `suggested` (never persisted until acted on).
- Remap preview returns `{chapter_id, from_stage, to_stage}[]` WITHOUT writing when `confirm: false`; `confirm: true` writes assignments + novel setting in one transaction.

## Tasks

### Task 0: Storyboard substrate + read/write API

- [ ] **Step 1: Read the v1 contract + the v2 house rules** — PLAN-005 §§ sync/remap (AI parts skipped), `timeline_events` model + repository for ownership/migration idioms, planning `service.py`/`router.py` error mapping (404/409/422 conventions from the timeline slice).
- [ ] **Step 2: Failing tests** — empty novel aggregate (all chapters suggested, none assigned); PUT stage persists + returns assigned; unknown chapter/stage → 422 with nothing written (refetch-compare); foreign novel ≡ 404; remap preview is pure (no rows written); remap confirm writes exactly the previewed mapping.
- [ ] **Step 3: Implement** — models + migration (`just db-revision`), service (thin router, logic in service), `just generate`, `just check`.
- [ ] **Step 4: Run** — `just test-file` on the new tests + affected suite. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(planning): storyboard substrate and read API` + real `User-visible:` + trailer.

### Task 1: Storyboard canvas page + route + entry

- [ ] **Step 1: Read the canvas + entry patterns** — knowledge GraphPage (route shape, canvas page chrome, `?novel=` picker), PlanningPage (?novel= pattern reuse), NovelPage workspace route for chapter deep-links.
- [ ] **Step 2: Failing component tests** — columns render from mocked aggregate; card shows title + word count + sync badge; move control changes stage (PUT called, refetch); structure switch opens remap dialog with before/after; confirm applies; failed PUT snaps back with Notice + retry.
- [ ] **Step 3: Implement** — lazy page, stage columns, chapter cards (Button as link to the chapter — read how chat/doc links navigate; no raw anchors), move-to-stage menu per card (NO drag&drop — record as follow-up in a code comment), structure switcher + remap preview dialog with confirm/cancel, entry link from the timeline landing (`?novel=` carried over), 200-chapter cap with note, empty states naming the next step.
- [ ] **Step 4: E2E** — planning suite: seed novel + 3 chapters + scenes, open canvas, columns + badges visible in German, move a chapter via the control → persists after reload, remap preview → confirm changes stages, 1280px no horizontal page scroll.
- [ ] **Step 5: Run** — component tests, typecheck, `just test-e2e planning`. Expected: PASS.
- [ ] **Step 6: Commit** — `feat(planning): storyboard canvas with stages and remap preview` + real `User-visible:` + trailer.

### Task 2: Specimen, re-shoot, gates

- [ ] **Step 1: Specimen + failing test** — inert storyboard specimen from real primitives (stage columns miniaturized, one moved card state), RED → GREEN.
- [ ] **Step 2: Re-shoot + read** — new shots present, dark differs, no expanded rail over gallery; revert noise-only rewrites of other shots.
- [ ] **Step 3: Full gates** — `just check`, frontend suite, `just test-e2e planning settings`, web build with clean chunks.
- [ ] **Step 4: Commit** — `docs(screenshots): the storyboard canvas pinned in both themes` + `User-visible:` + trailer. Report, no code.

---

## Self-Review

**Spec coverage.** Atlas storyboard row→T0–T2 (canvas, manual moves, remap preview/confirm; DnD/AI/extra adapters explicitly out); dock already landed; timeline sibling untouched.

**Type consistency.** Aggregate + remap shapes defined once in T0, consumed by T1's page and T2's specimen.

**Review Focus.** Five lines, each with its owning task + test: unassigned→T0; preview==apply→T0; failed PUT→T1; 200-cap→T1; dark+de→T1/T2.

**Proportion.** Decisions and API shapes named; bodies only where the shape is the decision (storage split, sync rule, remap contract, entry pattern).
