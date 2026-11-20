# Planning Rebuild W6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The planning capability's three surfaces — Chronologie, Storyboard, Kausalitätsleiste — on the complete existing backend, ported from owner-approved harmonized Stitch drafts.

**Architecture:** Same shape as W5: Stitch harmonization first (edit rounds for timeline/storyboard, a fresh generate for the causality strip), then per-surface SDD tasks with the house dialog/focus/state families, one capability-local fan-out hook for novel-wide scene data, an E2E suite, and the wave's gap ledger. Three PRs: A (opener fixes + timeline), B (storyboard + scene drill-in), C (causality strip + E2E + ledger + gate).

**Tech Stack:** React + TanStack Router/Query, Tailwind on the shell tokens, i18n catalogs (de/en/fr), Vitest, Playwright E2E; backend untouched.

**Spec:** `docs/superpowers/specs/2026-11-20-planning-rebuild-w6-design.md` — the plan argues from it; executors read both.

## Global Constraints

- No new backend: the planning API is the boundary; missing endpoints are honest disabled doors + gap rows (W5's create-entity ruling).
- Rule 1 (`docs/_shared/CONSTRAINTS.md`): no cross-capability imports; knowledge chips/badges only if the shell exposes them — else out, disclosed.
- Stitch alone designs: only owner-approved harmonized drafts are ported; deviations disclosed per task.
- i18n: three catalogs, sorted parity, du-tone; no invented copy.
- Commits: conventional grammar; feat/fix/docs carry real `User-visible:` lines; every agent commit ends `Assisted-by: OpenCode (<model>)`; nothing merges before green reviews; merge commits, non-conventional PR titles.
- Dispatches name models: both seats ride `zai-coding-plan/glm-5.3` until 2026-12-13 (qwencloud quota), disclosed each time.
- E2E: de-DE contexts, two xdist workers max, stack DOWN after runs, root-cause rule for flakes.
- Branch hygiene: switching away from a branch that tracks a capability's `e2e/` leaves an ignored `__pycache__` behind — the phantom suite turns the kernel discovery test red and blocks pushes. After every branch switch: remove the leftover `app/capabilities/{knowledge,planning}/e2e` if the target branch doesn't track it.
- Findings fixed in-task; survivors become `follow-up` issues under the wave index with `area:` labels before merge.

## Review Focus

1. **Stale scene-aggregate version** (two surfaces editing one chapter's scenes): the PUT's version stamp must not silently clobber — pin the refused/conflict face the API actually serves (read the service first). — Task 4.
2. **Remap to an unknown structure id**: `UnknownStructureError` must surface as the API's refusal, never a bricked switcher. — Task 4.
3. **Timeline event whose linked chapter was deleted**: honest row face, no dead navigation. — Task 3.
4. **Empty novel on every surface**: honest empty states, sibling doors stay reachable (W5 #923's lesson). — Tasks 3–5.
5. **Five-structure switcher with a remapped novel**: stage assignments follow the API's remap semantics exactly; three-act is the default every unremapped novel reads. — Tasks 4, 6.

---

### Task 1: Harmonization rounds (gate — coordinator + Stitch + owner, no porting)

Real-field briefings from the design's delta table: edit rounds for `chronology-timeline` (strip syuzhet semantics, check/sync buttons, gap counter, attachments, priority flags) and `three-act-storyboard` (chapters-in-stages model, five structures incl. three-act default, scene drill-in; retire version tags, beat-sheet export, findings badges); a FRESH generate for the causality strip (scenes' conflict→resolution chain). Archive as `planning/*-2.html` (+ the new strip). Owner approves before Task 3 starts. **Fallback pre-authorized:** if the strip draft is rejected as too thin, PR C drops the strip surface and the wave ships two surfaces + gap rows.

### Task 2: Wave opener — #910 and #911 (PR A)

**Files:** `app/capabilities/knowledge/web/EntityDossier.tsx` (survivor chain when the emptied list unmounts its focus target — the dossier aside fallback, per #910), `web/components/TopBar.tsx` (mobile overflow at 390 px, per #911). Each closes its issue from its own commit (`Closes #910` / `Closes #911`); vitest pins first; live mobile capture for #911.

### Task 3: Chronologie page (PR A)

**Files:** Create `app/capabilities/planning/web/` (routes.tsx, TimelinePage.tsx, timeline dialogs, i18n/{de,en,fr}.json), `web/lib/query.ts` additions (`useTimelineEvents`, `useNovelScenes` fan-out hook over the chapters list — per-chapter aggregate queries, cached, invalidated per chapter), generated tables via `just generate`.

**Interfaces:** `useNovelScenes(chapters: Chapter[]): UseQueryResult<SceneAggregateRead[]>` — parallel `useQueries`, per-chapter keys `["planning","scenes",chapterId]`, invalidated by the aggregate save; the timeline's status counters and Task 5's strip both consume it. Routes root-parented: `/novels/$novelId/planning/timeline`, `.../storyboard`, `.../causality` registered now, surfaces landing per task.

Event CRUD per the house dialog family (create/edit/delete, honest busy/refusal, focus contracts); grouping/order per the harmonized draft; character_names as free text (no KB linkage); chapter link as a door; the dock/rail area door follows the drafts' sub-nav mechanism. **The rail's Planung door goes live with this first surface** (W5's Wissen ruling): link to the timeline route, active face on all planning routes — and the writing chrome E2E's disabled-door loop drops "Planung" the same commit (the a77386ac pattern).

### Task 4: Storyboard page + scene drill-in (PR B)

**Files:** `app/capabilities/planning/web/StoryboardPage.tsx`, scene drill-in component + aggregate editor, dialogs.

Structure switcher over the five real ids (`three-act` default); chapter cards in stages (word count and sync status from `StoryboardChapterRead`); stage assignment PUT; remap with the unknown-id refusal face; scene drill-in edits the chapter aggregate (title, purpose, conflict, resolution, beats, status, position) with the stale-version conflict face per Review Focus 1.

### Task 5: Kausalitätsleiste (PR C — gated on Task 1's approved strip draft)

**Files:** `app/capabilities/planning/web/CausalityPage.tsx`, i18n keys.

The chain strip over `useNovelScenes` (conflict→resolution per scene, chapter-grouped, honest empty state); the what-if scope (branches, divergence, twist parameters, anchors, paradox counters) as the draft's honest disabled areas or gap rows per the harmonized draft's ruling; gap rows carry the ledger references.

### Task 6: Planning E2E suite (PR C)

`app/capabilities/planning/e2e/` — CRUD round-trips through the real stack (no LLM fake needed: pure CRUD + deterministic structure math), structure-switch and remap legs, drill-in with the stale-version path, strip leg, sibling doors, de-DE, per-suite DB, two workers. The kernel discovery expectation grows to include `"planning"` in the SAME commit as the e2e directory.

### Task 7: Gap ledger + follow-up children (PR C)

`docs/design/stitch/gaps/2026-11-20-planning.md` per the W4/W5 shape (every retired draft element with trigger + home); child issues under a new W6 index issue (`follow-up-index` label; children `follow-up` + `area:` planning + `kind:` where fitting); `docs/superpowers/follow-ups.md` row.

### Task 8: Wave gate + PRs

`just verify` green; whole-branch review; PRs A→B→C as merge commits; owner merges. PR A opens after Task 3, B after Task 4, C after Tasks 5–7 (fallback shape if the strip was dropped: C = Tasks 6–7).
