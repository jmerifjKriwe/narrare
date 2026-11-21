---
id: PLAN-001
title: "Scene Planning"
status: stable
area: planning
mvp: false

ui_tooltip: "Plan scenes with goals, conflicts, and AI drafts before writing."
ui_help_short: |
  Plan each scene — POV, characters, purpose, conflict, beats — with AI
  draft and refine. Plans feed the storyboard.
ui_help_long: |
  Plan a chapter scene by scene before you write it. Each scene plan holds
  what a writer actually needs at the keyboard: who tells the scene (POV),
  where it happens, which characters are present and what they want, what
  the scene is for, its conflict, how it resolves, and its beats in order.
  Plans live in the studio's Planning tab ("Scenes"), and a compact version
  sits right beside the editor while you write.

  Staring at an empty list? "Draft with AI" proposes a scene breakdown for
  the whole chapter, and every scene can be refined with its own
  instruction. AI proposals are suggestions only — nothing touches your
  novel until you save, so undoing a draft is as simple as not saving it.

  Plans aren't just notes: you mark scenes in progress or complete
  yourself, and the storyboard reads those statuses to tell you where the
  chapter stands. When you generate in scene-by-scene mode, Narrare writes
  from your scene plans directly (the generation panel toggles this on by
  default when plans exist) — what you planned is what gets written.

ui_available_in: [editor]

service: planning/scene_service.py
contract: planning/contracts.py#ScenePlanRepositoryProtocol, planning/contracts.py#SceneAIServiceProtocol
router: planning/router_scenes.py
prompt: core/prompts/_bundled/planning/en/scene_plan_{draft,refine}
requires: [KB-001]
---

# PLAN-001 — Scene Planning

> **Status:** ✅ Stable — v1 (scene-plan substrate + AI generators + write
> integration) implemented 2026-10-09 → 2026-10-11 (commits
> `0bf569da..42c49c10`) per
> [ADR-096](../../architecture/decisions/ADR-096-scene-planning.md)
> (✅ Implemented). Design:
> [scene-planning spec](../../superpowers/specs/2026-10-09-plan001-scene-planning-design.md),
> plan: [2026-10-09-plan001](../../superpowers/plans/2026-10-09-plan001-scene-planning.md).

## What it does

First-class scene planning for chapters: a dedicated `scene_plans` table
(stable per-scene identity) holding title, position, POV + location (hybrid
KB refs), present characters with goals, purpose, conflict, resolution,
ordered beats, and a manual status (`planned` / `in_progress` / `complete`).
Chapters get an aggregate read/save API with server-side diff-sync, two
zero-write AI generators (chapter-level draft, single-scene refine),
scene-status-driven storyboard sync, and a persisted structured scene
snapshot that feeds scene-by-scene generation.

## Why it exists

The predecessor — a JSONB `planned_beats` list on `chapter_outlines` — had
no scene concept, no stable identity, and two verified defects: its
`required`/`completed` flags drifted (sync read a field nobody wrote), and
the free-text outline never reached scene-by-scene generation at all. Scene
plans replace the stored-beat concept with one substrate that serves the
storyboard, the AI assist, and the writer (ADR-096 Context).

## How it works (User perspective)

1. Open a chapter and go to the **Planning** tab → **Scenes** (or open the
   compact **scene plan** panel beside the editor).
2. Add scenes, reorder them, and fill in as much or little as you want —
   title, POV, location, present characters (with goals), purpose,
   conflict, resolution, beats.
3. "Draft with AI" proposes scenes for the chapter (3–8 is prompt-level
   guidance, not a validated limit — the model chooses the count); each
   scene has a "Refine with AI" action that rewrites it per your
   instruction. Proposals
   land in the editor as unsaved changes — save applies them, discarding
   them changes nothing.
4. Mark scenes in progress / complete yourself (status is manual). The
   storyboard (PLAN-005) reads these statuses: all scenes complete and the
   chapter has content ⇒ COMPLETED; partially worked ⇒ ON_TRACK.
5. In the generation panel, "Write from scene plans" (default ON when the
   chapter has plans) attaches your current plans to scene-by-scene
   generation — each scene is rendered into its writing step. Turning it
   off sticks for the session.

## How it works (Technical)

**Entry point:** `planning/router_scenes.py` (thin delegates, RULE-06):
`GET/PUT /api/v1/planning/scenes/{novel_id}/{chapter_id}` (chapter
aggregate) + `POST …/{novel_id}/{chapter_id}/draft` +
`POST …/{novel_id}/{chapter_id}/refine`.
**Services:** `ScenePlanService` (`planning/scene_service.py`, CRUD +
diff-sync) and `SceneAIService` (`planning/scene_ai_service.py`, AI
generators). **Contracts:** `ScenePlanRepositoryProtocol` /
`SceneAIServiceProtocol` in `planning/contracts.py` (RULE-03).

**Scene plan structure (as built):**

```python
class ScenePlan:  # apps/api/narrare/planning/models.py
    id: UUID                    # stable diff-sync / AI-addressing key
    chapter_id: UUID            # FK CASCADE + index
    position: int               # renumbered 1..N per payload order
    title: str
    pov_character_ref: dict | None   # hybrid {"id": uuid|None, "name": str}
    location_ref: dict | None        # hybrid — survives KB deletion (RULE-22)
    present_characters: list[dict]   # [{id, name, goal}] — a list, never UUID-keyed
    purpose: str
    conflict: str
    resolution: str
    beats: list[str]
    status: "planned" | "in_progress" | "complete"   # manual only in v1
    created_at / updated_at
```

**Aggregate API + diff-sync:** `GET` returns `{chapter_id, scenes[],
version_updated_at}` ordered by position (no auto-create). `PUT` takes the
whole aggregate and server-side diffs by stable scene id: known id ⇒
update, id unknown to the chapter ⇒ 422 `unknown scene id` (client UUIDs
for new scenes; PK collision surfaced as the same 422), duplicate id ⇒ 422
`duplicate scene id` before any write, absent id ⇒ delete; positions
renumbered 1..N by payload order. Ownership is uid-scoped — foreign novel
≡ unknown → 404.

**AI assist (zero-write):** `ScenePlanAgent`
(`core/agents/scene_plan_agent.py`, RULE-01b) produces structured outputs —
draft → `SceneDraftOutput` (list of proposals), refine →
`SceneRefineOutput` (one proposal); an output validator rejects proposals
with both title and purpose empty (`ModelRetry`). System prompts come from
two governed EN templates on `LLMIntent.PLAN` (`scene_plan_draft`,
`scene_plan_refine` — ADR-049 D11 context modes); chapter/scene data rides
the run prompt XML-wrapped (`<chapter_context>` / `<scene_plan>` /
`<instruction>`), scenes rendered by the single Core renderer
`render_scene_for_prompt` (`core/planning/scene_render.py`). Model
resolution is lazy (ADR-086); no provider configured ⇒ HTTP 200 with
`ai_unavailable: true` — never a 5xx. Endpoints write nothing: proposals
carry no id, and the FE applies them via the normal aggregate PUT (one
write path; undo = don't save).

**Migrations:** `0047_scene_plans` (create table + index; tolerant backfill
— one scene per old dict beat: `title→title`, `description→purpose`,
`completed→status`, order ⇒ position; non-dict entries skipped) ·
`0048_generation_scenes` (`generation_requests.scenes` JSONB snapshot) ·
`0049_drop_planned_beats` (column dropped; upgrade reverse-migrates
scenes → beats first, downgrade recreates the column from scene-derived
beats — documented lossy for scene-only fields). Round-trip tests run
under Q-018 (schema-mutating, serial phase, downgrade-to-parent only).

**Write integration:** `GenerateRequest.scenes` (optional list) is
persisted on the `generation_requests` row (0048) and threaded into Core
`GenerationRequest.scenes` (`SceneSpec` — identity-free: names and beats,
no ids/refs). `stream_scene_by_scene` renders each scene via
`render_scene_for_prompt` when scenes are present — no `parse_scenes` call;
the free-text fallback is retained for scene-less clients. What you
approved at generate-time is what streams.

**Frontend:** Planning tab gains a "Scenes" tab — `ScenePlanEditor` family
(`SceneCard` / `SceneForm` / `SceneListEditors`, each under the 200-line
component gate). The editor gains the compact `scene_plan` right panel
(`ScenePlanPanel`: read + edit + save, "Open full planner") and the
generation toggle + "Plan scenes" link (`GenerationConfig` /
`useGenerationConfig` — scenes attach only in scene-by-scene mode;
explicit-off persists in sessionStorage for the session). i18n:
`studio.planning.scenes.*` + `studio.generationPanel.*` (en/de/fr).

**Cross-feature coherence (RULE-22):** hybrid refs are user content — KB
rename/deprecate/delete never rewrites scene plans. The planning KB
lifecycle consumer and the consistency ref-index scan scene text fields
via the shared `iter_scene_texts` helper (exported on the planning public
surface), reporting locations as `scene_plans[{id}].{field}`; story-suggest
renders stage + numbered scene blocks + notes.

## Constraints & Edge Cases

- **Status is manual in v1** — the FE sets `in_progress`/`complete`; no
  auto-transitions (ADR-096 review trigger: auto status ⇒ new decision).
- **AI endpoints have zero DB writes** — enforced behaviorally (fake repos
  record every call; integration pins the aggregate unchanged), not by a
  static checker rule.
- **No provider configured is a normal state** — draft/refine answer 200
  with `ai_unavailable: true` (AI-optional policy); a missing composer is
  a loud `ConfigurationError` (RULE-11), not an inline fallback.
- **Diff-sync integrity:** duplicate and unknown scene ids are rejected
  with 422 before mutation; saves round-trip the fetched aggregate (the
  server owns timestamps — payload timestamps are ignored).
- **The 0049 downgrade is lossy by design** — scene-only fields
  (conflict/resolution/per-scene beats/refs) have no old-shape equivalent;
  downgrade is an explicit user action.
- **The generation scenes snapshot is ephemeral request state** — durable
  plans live in `scene_plans`; a 0048 downgrade drops the snapshot column
  with its data (documented).
- Very detailed plans may slow discovery writing; not every scene needs
  equal planning — all fields are optional.

## Related Features

- [PLAN-003](PLAN-003-structure.md) — Chapter-level structure (adapter
  beats are a separate, surviving concept)
- [PLAN-005](PLAN-005-storyboard.md) — Storyboard reads scene statuses for
  sync
- [WRITE-002](../writing/WRITE-002-new-chapter.md) — Scene-by-scene
  generation consumes plans via the scenes toggle
- [ASSIST-001](../ai_assist/ASSIST-001-plot-check.md) — Plot guidance

## Status & History

- `project-init` — Added to registry as planned feature (v0 sketch: CLI
  access, `character_goals` dict, `POST /planning/scenes`).
- `2026-10-09` — Re-scoped and ratified as v1:
  [ADR-096](../../architecture/decisions/ADR-096-scene-planning.md)
  (dedicated table, hybrid refs, scene-driven sync, pure AI generators,
  persisted scenes snapshot, ScenePlanEditor, manual-only status); binding
  spec `2026-10-09-plan001-scene-planning-design.md`, 17-task plan. The v0
  CLI promise is retired (no CLI substrate exists, mirroring the
  STATS-001 ruling) — `ui_available_in` is `[editor]`.
- `2026-10-11` — **v1 implemented** (branch `feature/plan001-scene-planning`,
  commits `0bf569da..42c49c10`; Phase 0 + T1–T17a — 17 tasks landed as 19
  commits: T4 split a/b, one type-ignore ratchet prep commit before T8;
  every task passed its review gate, fix rounds re-reviewed clean):
  `scene_plans` table + migrations 0047/0048/0049, aggregate GET/PUT with
  diff-sync, AI draft/refine (zero-write, graceful), scene-driven sync,
  write integration, FE Scenes tab + editor panel + generation toggle,
  consumer adaptations (KB / ref-index / story-suggest), i18n en/de/fr,
  Q-018 round-trips for all three migrations. **Status → `stable`.**
