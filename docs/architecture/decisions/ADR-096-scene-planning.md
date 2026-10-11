# ADR-096 — Scene Planning (PLAN-001 v1)

> **Status:** ✅ Implemented (per Gate 12 — implementation complete
> 2026-10-11: branch `feature/plan001-scene-planning`, commits
> `0bf569da..42c49c10`; binding spec
> `docs/superpowers/specs/2026-10-09-plan001-scene-planning-design.md`, plan
> `docs/superpowers/plans/2026-10-09-plan001-scene-planning.md` — see the
> Implementation Report below)
> **Date:** 2026-10-09
> **Deciders:** Architecture Agent; Project Owner (ratified 2026-10-09:
> full v1 scope · dedicated table · hybrid KB refs · scene-driven sync ·
> explicit write toggle · zero-write AI generators · ScenePlanEditor ·
> manual-only status)
> **Related:** `docs/features/planning/PLAN-001-scene-planning.md` (feature),
> `docs/features/planning/PLAN-005-storyboard.md` (sync consumer),
> ADR-049 D11 (PLAN context_modes mechanism), ADR-054 (inline-prompt
> migration precedent), ADR-086 (lazy model resolution), ADR-093/094
> (usage/cost flows through the registry), Q-018 (schema-mutating tests),
> binding spec `docs/superpowers/specs/2026-10-09-plan001-scene-planning-design.md`,
> plan `docs/superpowers/plans/2026-10-09-plan001-scene-planning.md`

---

## Context

Writers currently plan a chapter via `chapter_outlines.planned_beats` — a
JSONB list of `{title, description, completed}` with no scene concept, no
per-scene POV/location/goals, and no connection to the scene-by-scene
writing mode (which parses free-text outlines via `***`/numbered markers,
`parse_scenes()` in `core/writing/pipeline_scene.py`).

Two verified defects motivate the redesign:

1. **Beat-field drift (root cause).** `StructuralSyncChecker` rule 4 reads
   `BeatDef.required` (`core/planning/sync.py`), which nobody writes — the
   API writes `completed` (`to_outline_response`), which sync never reads.
   One `BeatDef` type served two distinct concepts: *structure-template*
   beats (adapters' `get_beat_expectations`) and *user-authored stored*
   beats. The stored-beat concept dies; the adapter-template concept
   (PLAN-003 surface) stays.
2. **Outline never reaches scene generation.** `GenerateRequest.outline` is
   accepted at `POST /writing/chapters/{id}/generate` but neither persisted
   on the `generation_requests` row (`create_request_row` stores only
   mode+tone) nor threaded into the core request (`build_pipeline_request`
   omits it). `stream_scene_by_scene` therefore parses
   `context.chapter_outline`, which is `""` on the REST SSE path — the
   free-text outline field is silently dead for REST scene generation.
   Structured scenes must not repeat this: what the user approves at
   generate-time is what streams.

Verified consumer surface of `planned_beats` (complete, from
`rg "planned_beats"` 2026-10-09): planning `models/repository/schemas/
contracts/service/_helpers/kb_lifecycle_consumer`, consistency
`ref_index_helpers`, writing `_outline_render` (story-suggest slot), Core
`planning/models.py`, `planning/sync.py`, `context/integration_contracts/
_planning_consumer.py`, FE `types/planning.ts`, `types/index.ts`,
`lib/api/planning.ts`, `OutlineEditor.tsx` (+ its tests), migration 0013
(history), plus 14 test/fake/factory files.

---

## Decision Drivers

- PLAN-001 v1 PO scope (binding, 2026-10-09): scene-plan CRUD + AI assist
  (chapter-level draft AND single-scene refine) + write integration.
- Scene plans are the planning substrate the storyboard and the writer both
  consume — one storage shape must serve sync status, AI context, and
  per-scene prompt rendering.
- RULE-01b/02/02b (agent + governed prompt paths), RULE-03 (contract first),
  RULE-14 (migration per model change), RULE-17 (API-FE contract), RULE-22
  (cross-feature coherence, hybrid refs are USER CONTENT — never rewritten),
  RULE-20 (no half-implementations; SSE where backend supports it — REST
  CRUD + one-shot AI generators are the correct non-streaming surface here).
- Every per-task commit on the feature branch must stay green (per-commit
  gates: pytest, check_architecture, prompt-surface, FE vitest/tsc/biome).

---

## Options Considered

### A — Storage: dedicated `scene_plans` table (chosen) vs JSONB column on `chapter_outlines`

JSONB column repeats the `planned_beats` failure mode (untyped shape drift,
no stable per-scene identity for diff-sync/AI addressing, no indexable
chapter FK). A dedicated table gives stable row ids, per-row updates, and
CASCADE semantics. **PO-ratified (decision 2).**

### B — KB references: hybrid `{id, name}` refs (chosen) vs hard FKs

Hard FKs break on KB deletion (scenes are plans, not KB data); hybrid refs
survive deletion with the display name intact — the `TimelineEvent`
`character_refs`/`location_ref` pattern (AD-1). `present_characters` is a
**list** of `{id, name, goal}` — never `dict[UUID, str]` (UUID keys die on
KB deletion). **PO-ratified (decision 3).**

### C — Sync semantics: scene status drives storyboard (chosen) vs repaired beat flags

Repairing `required`/`completed` would keep a dead concept alive. Instead:
scenes exist ∧ all `complete` ∧ has content ⇒ COMPLETED; scenes exist ∧
partially worked ⇒ ON_TRACK; no scenes ⇒ existing rules. The stored-beat
`completed` field and the sync-side `required` reading both die.
Adapter-template `BeatDef` (PLAN-003) is out of scope and stays.
**PO-ratified (decision 4).**

### D — Write integration transport: persisted structured `scenes` on the generation row (chosen) vs stream-time rehydration vs status quo (free-text)

Status quo (`parse_scenes` over an outline that never arrives — defect 2)
is unacceptable. Stream-time rehydration (writing service reads
`scene_plans` at GET /stream) couples writing→planning at stream time and
can drift from what the user saw when clicking Generate. Persisting a JSON
snapshot of the scenes on `generation_requests` (new `scenes` JSONB NULL
column; presence = the explicit toggle) makes the row the single state
carrier between POST and stream — snapshot semantics: what you approved is
what streams. FE computes the "use scene plans" default (ON when the
chapter has plans) and sends the effective scene list; no backend coupling
needed for the default. **PO-ratified (decision 5); snapshot detail
resolved here.**

### E — AI write policy: pure generators (chosen) vs AI persists drafts

AI endpoints return proposals; the FE applies them via the normal aggregate
PUT — one write path, single ownership surface, undo = don't save.
Mirrors the kb-resolution analyze-only pattern. **PO-ratified (decision 6).**

### F — LLM routing: PLAN intent + two new context modes (chosen) vs new LLMIntent vs reuse `outline` mode

A new intent would touch `llm/intents/_enums.py`, `INTENT_PROFILES`,
`INTENT_TO_CATEGORY/MODE` for zero benefit — the PLAN context_modes
mechanism (ADR-049 D11) exists exactly for this (`outline`,
`temporal_consistency`, `timeline`, `character_arc`, `timeline_extraction`
precedents; no semantic overlap with any of them — RULE-22 §3 checked).
Advisory profile reuses PLAN ("balanced"/"creative"); the concrete model
resolves via the per-user cascade (`LazyModelResolution(PLAN)`, ADR-086) —
no hardcoded routing (RULE-18). Two governed EN-only templates
(`scene_plan_draft`, `scene_plan_refine`) under
`prompts/_bundled/planning/en/` — planning templates are EN-only today;
output language is controlled by content/variables, not template locale
duplicates (RULE-22 §5).

### G — Scene serialization: single Core renderer (chosen) vs per-caller formatting

One pure function (`core/planning/scene_render.py::render_scene_for_prompt`)
defines the exact compact format (spec §6) and serves both the AI endpoints
and the writing pipeline's per-scene prompt input — one format, no drift.

### H — Task sequencing: additive-first (chosen) vs big-bang removal

See Decision 10.

---

## Decision

1. **Data model.** New `scene_plans` table (spec §3): stable UUID PK,
   `chapter_id` FK CASCADE + index, `position` (consecutive; reorder =
   renumber — house pattern), `title`, `pov_character_ref`/`location_ref`
   hybrid JSONB, `present_characters` JSONB list, `purpose`/`conflict`/
   `resolution` text, `beats` JSONB list[str], `status` ∈
   `planned|in_progress|complete` (manual only in v1 — PO decision 8),
   timestamps. `ChapterOutline` keeps `stage_assignment` + `outline_notes`
   only; `planned_beats` column is data-migrated into scene rows (one
   scene per old beat: `title→title`, `description→purpose`,
   `completed ? complete : planned`, list order ⇒ `position`) and DROPPED.
   Core gains `SceneStatus` + `ScenePlanData` (names resolved from hybrid
   refs at the API boundary — Core stays pure); `ChapterOutlineData`
   becomes scene-based; `BeatDef` survives only as the adapter-template
   concept and leaves the `narrare_core.planning` package exports.
2. **API surface** (mirrors `/planning/outlines/{novel_id}/{chapter_id}`):
   `GET/PUT /planning/scenes/{novel_id}/{chapter_id}` (chapter aggregate;
   whole-aggregate save, server diff-syncs by stable scene id:
   known id ⇒ update, id unknown to the chapter ⇒ 422, absent id ⇒ delete;
   positions renumbered 1..N by payload order; client-generated UUIDs for
   new scenes so reorder/refine can address scenes before first save),
   `POST …/scenes/draft` (chapter-level AI draft), `POST …/scenes/refine`
   (single-scene refinement; carries the full scene so unsaved drafts are
   refinable). Ownership: uid-scoped guards, foreign ≡ unknown → 404.
3. **AI assist.** `ScenePlanAgent` (`core/agents/scene_plan_agent.py`,
   RULE-01b; structured output: draft → list of scene proposals, refine →
   one proposal), governed routes per Option F, prepared-triple
   `(agent, model_settings, usage_limits)` pass-through (19009e17
   convention), graceful no-provider degradation (AI-optional policy),
   zero DB writes. Usage/cost flows through the existing registry emission
   points (ADR-093/094) — no extra wiring.
4. **Sync rewrite.** `StructuralSyncChecker`: rules EMPTY/PLANNED/DEVIATED
   (+ summary rule) unchanged; rule 4 scene-driven per Option C. The
   storyboard/sync paths feed scenes into `ChapterOutlineData`.
5. **Write integration.** `GenerateRequest.scenes` (API schema, optional,
   list of scene objects) persisted as `generation_requests.scenes` JSONB;
   `build_pipeline_request` threads it into Core
   `GenerationRequest.scenes`; `stream_scene_by_scene` renders each scene
   via `render_scene_for_prompt` instead of `parse_scenes()` when scenes
   are present (free-text `parse_scenes` fallback retained for
   scene-less clients). No `***` roundtrip. Explicit FE toggle in
   GenerationConfig ("use scene plans", default ON when the chapter has
   plans — FE-computed). `SceneService.next_scene`/`accept_scene` stay
   untouched (verified stub/recording-only).
6. **FE.** Planning tab: `OutlineEditor` becomes `ScenePlanEditor`
   (management, ordering, all scenes; split into sub-components under the
   200-line component limit). Editor: compact read/edit scene-plan panel
   (new `scene_plan` right-panel id) for the current chapter while writing,
   plus the generation toggle.
7. **Cross-feature coherence (RULE-22).** Hybrid refs are user content —
   KB rename/deprecate/delete NEVER rewrites scene plans; the planning
   KB-lifecycle consumer and the consistency ref-index scan scene text
   fields (`title`, `purpose`, `conflict`, `resolution`, `beats`,
   character/location names) instead of `planned_beats[].text`. The Core
   integration contract (`_planning_consumer.py`) is updated to the same
   semantics.
8. **Migrations.** 0047: create `scene_plans` + backfill from
   `planned_beats` (+ index). 0048: `generation_requests.scenes` JSONB.
   0049: DROP `chapter_outlines.planned_beats` (lands with the ORM column
   removal, RULE-14). Round-trip tests under the enforced two-phase serial
   convention (Q-018: `@pytest.mark.schema_mutating`, downgrade to the
   parent revision only). Downgrade of 0049 reverse-migrates scenes → beats
   and is documented lossy for fields with no old-shape equivalent
   (conflict/resolution/beats-of-scene/refs) — the 0046 "explicit user
   action drops data" stance.
9. **BeatDef scoping ruling.** The drift fields that die are the
   *stored-beat* fields (`completed` in the JSONB shape; `required` as
   read by sync). Adapter-template `BeatDef` (six structure adapters,
   ~55 declarations, PLAN-003 surface) is NOT part of the drift and stays;
   it stops being exported from the planning package root.
10. **Sequencing.** Additive-first: all scene machinery (models, sync
    dispatch on data shape, table, repo, routes, AI, write integration,
    FE) lands alongside the beat path; the beat path is removed in the
    final Backend/FE removal tasks; the column drop is last. Every
    per-task commit stays green.

---

## Rationale

Root-cause chain (2× why):

1. **Symptom:** storyboard COMPLETED detection is a word-count heuristic
   over a beat field nobody writes; scene-by-scene writing ignores plans.
2. **Why?** The planning substrate (stored beats) predates both consumers
   and was never a scene model — no identity, no status that tracks work,
   no rendering contract into prompts.
3. **Why?** Two consumers (storyboard sync, scene writer) need a shared
   unit of narrative work with stable identity and lifecycle — that is a
   scene plan, and it must be first-class storage, not JSONB fragments.
4. **Design:** dedicated table + stable ids + manual status driving sync +
   one Core renderer feeding both the AI assist and the writer. The write
   side gets a persisted structured field so the POST→stream gap that
   silently kills the free-text outline cannot recur.

---

## Consequences

**Positive:** one planning substrate for storyboard sync, AI assist, and
scene-by-scene writing; drift class eliminated; hybrid refs survive KB
deletion; AI proposals ride the single aggregate write path (undo = don't
save); FE gains plan-while-write without new transports.

**Negative / Trade-offs:** three migrations instead of one (per-commit
greenness + RULE-14 same-task pairing — the column drop cannot share a
commit with ~20 file adaptations); scene JSONB snapshot on
`generation_requests` duplicates plan data per generation row (bounded,
one chapter's scenes per row — accepted for snapshot semantics);
downgrade of 0049 is lossy for scene-only fields (documented); manual-only
status means the FE must set `in_progress`/`complete` (auto transitions =
review trigger).

**Constraints touched:** RULE-01b/02/02b/03/04/06/07/08/10/11/14/16/17/
18/20/22/23 (mapping in the spec §12).

---

## Sustainability Check

1. **Correct in 3 months?** Yes — scene plans are the durable planning
   concept (PLAN-005 storyboard, WRITE-002 generate-from-plan build on
   them); the sync rules are total and testable.
2. **Hard-to-undo coupling?** None one-way: planning → writing consumes
   Core types; writing API owns only its snapshot column; KB integration
   is name-scan only (no rewrites).
3. **Simplest correct solution?** Yes per axis — table over JSONB (typed,
   addressable), context-modes over new intent (mechanism exists), one
   renderer over per-caller formatting, snapshot over rehydration
   (no cross-domain stream-time dependency).
4. **Intent clear?** This ADR + the binding spec (wire shapes, sync rules,
   diff-sync algorithm, serialization format, migration/downgrade
   semantics) + the task plan.

---

## Implementation Notes

- Module homes: `apps/api/narrare/planning/{repository_scenes,scene_service,
  scene_ai_service,router_scenes,schemas_scenes,_scene_ai_factory}.py`
  siblings (RULE-04/06 split; `kb/bulk_extraction/` sibling precedent);
  Core: `planning/{scene_render}.py`, `agents/scene_plan_{types,agent}.py`;
  FE: `components/studio/planning/ScenePlan{Editor,Card,Form}.tsx`,
  editor `ScenePlanPanel.tsx`.
- Prompt governance: ROUTE_CONFIGS PLAN `allowed_context_modes` += both
  modes; manifest `context_modes` entries; PROMPT-L2-HEADERS (only
  `## System Prompt` / `## First Message` use `## `); INFRA-013 adoption
  contract with static AND runtime evidence (plan step: run one real
  composition per mode in a test and record the resolved route).
- Q-018: round-trip tests carry `@pytest.mark.schema_mutating` (serial
  phase 2; the collection guard fails unmarked DDL tests loudly).
- FE file-size gates: components ≤200 lines (`check_frontend_file_size.py`
  ratchet — new violations fail); `ScenePlanEditor` is a family, not a
  monolith. i18n: `studio` namespace keys en/de/fr (RULE-16/17).
- Per-task implementer reports under `docs/superpowers/plans/reports/`
  (paths designated in the plan).

**ADR Implementation Completeness Gate:** flip INDEX to "✅ Implemented"
only when table + migrations 0047/0048/0049, scene CRUD + AI endpoints,
sync rewrite, write integration, FE (ScenePlanEditor + editor panel +
toggle), consumer adaptations, i18n, and tests are complete.

---

## Implementation Report (2026-10-11)

Implemented on branch `feature/plan001-scene-planning`, commits
`0bf569da..42c49c10` (Phase 0 + T1–T17a — the 17 planned tasks landed as
19 commits: T4 split a/b on the LOC cap, plus one type-ignore-ratchet prep
commit before T8). Every task passed its per-task review gate (APPROVED or
fix-round → re-review clean). Mapping to the decisions above:

- **D1 (data model):** `planning/models.py::ScenePlan` + Alembic
  `0047_scene_plans` — hybrid JSONB refs (TimelineEvent AD-1 pattern),
  `present_characters` a list, `status` default `"planned"`, chapter FK
  CASCADE + index. Backfill is tolerant of arbitrary legacy JSONB shapes
  (non-dict beats skipped); `gen_random_uuid()` verified available
  (PostgreSQL 17, PG 13+ builtin). Core gains `SceneStatus` /
  `ScenePresence` / `ScenePlanData` + `ChapterOutlineData.scenes`.
- **D2 (API surface):** `GET/PUT /planning/scenes/{novel_id}/{chapter_id}`
  + `POST …/draft` + `POST …/refine` (`planning/router_scenes.py`, thin
  delegates); diff-sync exactly as decided (known id ⇒ update, unknown ⇒
  422 `unknown scene id`, duplicate ⇒ 422 `duplicate scene id` pre-write,
  absent ⇒ delete, renumber 1..N); uid-scoped 404 foreign ≡ unknown.
- **D3 (AI assist):** `ScenePlanAgent` with a deterministic output guard
  (title and purpose both empty → `ModelRetry`); both governed modes
  resolve at runtime (INFRA-013 evidence in the route tests + adoption
  registry + probes, `check-adoption` green); prepared-triple run;
  `LazyModelResolution(PLAN)`; graceful `ai_unavailable: true` HTTP 200 on
  `ConfigurationError`; ZERO DB writes (enforced behaviorally — see
  follow-ups).
- **D4 (sync rewrite):** `StructuralSyncChecker` rule 4 scene-driven; the
  legacy beat branch is deleted (T16); storyboard/sync fetch scenes via
  `ScenePlanRepository.list_by_novel` and thread a scene map
  (`_to_core_scene` resolves hybrid-ref names, unknown status strings
  degrade to `PLANNED` with a warning).
- **D5 (write integration):** `GenerateRequest.scenes` persisted on
  `generation_requests` (Alembic `0048`) and threaded into Core
  `GenerationRequest.scenes` (`SceneSpec`, identity-free);
  `stream_scene_by_scene` renders scenes via `render_scene_for_prompt`
  when present, `parse_scenes` fallback retained; FE toggle default-ON
  when plans exist, explicit-off persisted for the session.
- **D6 (FE):** Planning-tab "Scenes" tab with the `ScenePlanEditor` family
  (`SceneCard` / `SceneForm` / `SceneListEditors` — the fourth component
  is the RULE-04 split that keeps `SceneForm` ≤200 lines); editor
  `scene_plan` right panel (`ScenePlanPanel`, reusing `SceneCard`/
  `SceneForm`) + generation toggle + "Plan scenes" link; i18n
  `studio.planning.scenes.*` + `studio.generationPanel.*` en/de/fr.
- **D7 (coherence):** kb lifecycle consumer, consistency ref-index, and
  story-suggest all read scene text via the shared `iter_scene_texts`
  helper (public re-export on the planning package surface, RULE-05);
  locations `scene_plans[{id}].{field}`; never rewritten (pinned by
  tests).
- **D8 (migrations):** 0047 create + backfill, 0048 scenes column, 0049
  drop — all three with Q-018 round-trip tests (serial phase 2,
  downgrade-to-parent only).
- **D9 (BeatDef scoping):** as decided — `BeatDef` survives only in
  `planning/adapters/base.py` and left the `narrare_core.planning`
  exports (`rg "class BeatDef" packages/core/` → exactly one match).
- **D10 (sequencing):** as decided — additive-first, every per-task commit
  green (`just test` / `just check-architecture` per task; FE
  vitest/tsc/biome per FE task).

**Where the implementation refined the decision text (factual):**

1. **Router prefix:** the plan's sketch `APIRouter(prefix="/planning/
   scenes")` included under the `/planning` parent would have mounted
   `/planning/planning/scenes/…`; the child prefix is `/scenes` (sibling
   convention of `router_timeline`), yielding the decided surface — proven
   by the integration tests (T5).
2. **OutlineEditor → Scenes tab, not an in-place swap:** `OutlineEditor`
   was already unmounted before T12 (orphan since an earlier cycle), so
   the FE lands as a new tab with the `planningTab=scenes` URL-state
   coupling (`planningUrlState.ts`) instead of a component substitution —
   the decided UX outcome is identical.
3. **0049 downgrade repopulates scene-derived beats** rather than leaving
   the recreated column literally empty: only populate-on-downgrade
   satisfies the round-trip contract ("beats reverse-migrated, column
   back") and gives spec §3.3's lossy-field list a defined source of
   truth. The real loss (historical beat-only content, scene-only fields)
   is documented in the migration docstring; downgrade stays an explicit
   user action (T17a).
4. **The scenes snapshot is identity-free at generation time:** the FE maps
   aggregate `ScenePlan` rows to the wire's `GenerateSceneSchema` (no
   ids/refs/timestamps — the writer needs names and beats, not identity),
   matching Core's `SceneSpec` (T13/T9).
5. **Explicit-off toggle persistence uses sessionStorage**, not hook
   state: the generation panel unmounts on every right-panel switch, which
   would silently reset an explicit-off to default-ON (spec §8.1
   "persists for the session" honored; T13).
6. **Fifth planning-module file `_scene_ai_support.py`** (run-prompt
   assembly + output mapping as pure functions) — RULE-04 modularize over
   the 300-line service gate; plus an optional `run_limit_resolver` ctor
   seam mirroring `StorySuggestService` (T8).

**Honest residuals / open follow-ups (documented, not hidden — RULE-11):**

- **`consistency/ref_index.py` line-count overage is pre-existing** (313
  lines before T15, 337 after; the ≤300 service guideline passes via the
  architecture checker's exception handling). Follow-up recommended:
  extract `_check_timeline_refs` / `_check_chapter_frontmatter_refs` into
  a helpers module (T15).
- **The FE file-size gate is not wired into `just check-architecture`:**
  `scripts/check_frontend_file_size.py` runs in pre-commit but is not
  among the justfile recipe's scripts — FE tasks run it directly. Wiring
  follow-up flagged so gate pairing stays honest (T13).
- **Pre-existing FE flake (NOT PLAN-001):**
  `importing/ImportPreviewPanel.test.tsx` "publishes the v2 selection
  shape" failed 1-of-3 full-suite runs — a test-side assertion race
  (asserts the publish without `waitFor`); passes in isolation. Fix
  recommended: wrap the assertion in `waitFor` (T13).
- **AI zero-write is enforced behaviorally, not statically** — fake repos
  record every call and the integration suite pins the aggregate
  unchanged; nothing statically forbids a future repo write inside
  `SceneAIService` (T8).
- **`SceneAIService.scene_repo` is an injected-but-unused seam** —
  draft/refine are fully stateless; the parameter pins the protocol shape.
  Revisit trigger: the first AI feature that needs scene reads at
  generation time (T8, carried through T14).
- **Story-suggest scene fetch sits nested under the outline-existence
  gate** — contract-consistent and test-pinned; hoisting the fetch above
  the gate would render scene blocks for outline-less chapters. Only if
  desired (T15).
- **`_ref_name`/`_scene_spec` are tolerance twins** (hybrid-ref name
  resolution + JSONB-tolerant presences in planning `_helpers` vs writing
  `_outline_render`). Export a public mapper if a third consumer appears
  (T15).

Gate 12 satisfied — table + migrations 0047/0048/0049, scene CRUD + AI
endpoints, sync rewrite, write integration, FE (editor family + panel +
toggle), consumer adaptations, i18n, and tests are complete; INDEX flipped
to ✅ Implemented in the same docs pass. PR pending.

---

## Review Triggers

- [ ] Scene status auto-transitions requested (e.g. mark `in_progress` on
      first generation against the chapter) → new decision; v1 is manual.
- [ ] PLAN-005 plan-vs-actual comparison → consumes `scene_plans` read-only;
      do not add written plan/actual duplication.
- [ ] Adapter-template `BeatDef` is ever surfaced in UI/AI → then (and only
      then) revisit whether it converges with scene beats.
- [ ] Scene-level SSE streaming AI (incremental draft) → current draft
      endpoint is one-shot REST by design (proposals, not prose); streaming
      prose stays in the writing pipeline.
- [ ] Multi-scene reorder performance at ≥100 scenes/chapter → position
      renumbering is O(n) UPDATEs today; batch if it ever shows.
- [ ] The `outline` free-text REST dead-drop (defect 2) is fixed only for
      the scenes path — if free-text outline is ever revived, persist it on
      the row the same way or delete the field (do not leave a third path).
