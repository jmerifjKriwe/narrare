# PLAN-001 "Scene Planning" — Binding Design Spec (v1)

> **Status:** BINDING — ratified by PO decisions 2026-10-09; architecture
> gate passed (ADR-096). Implementation deviates from this spec only via a
> documented deviation in the task report.
> **ADR:** [ADR-096](../../architecture/decisions/ADR-096-scene-planning.md)
> **Plan:** `docs/superpowers/plans/2026-10-09-plan001-scene-planning.md`
> **Feature:** `docs/features/planning/PLAN-001-scene-planning.md`

---

## 1. Scope

**In (v1, PO-ratified):** scene-plan storage + aggregate CRUD with
diff-sync; scene-driven storyboard sync; AI assist (chapter-level draft +
single-scene refine, zero DB writes); write integration (explicit toggle +
structured `scenes` on the writing request consumed by
`stream_scene_by_scene`); FE: Planning tab `ScenePlanEditor` + compact
editor scene-plan panel; migration of `planned_beats` into scene rows with
column drop.

**Out (v1):** automatic scene-status transitions (manual only); scene-level
SSE streaming for the AI generators (one-shot REST proposals by design);
plan-vs-actual comparison (PLAN-005); CLI surface (feature file's stale
`cli` promise is amended away); `SceneService.next_scene`/`accept_scene`
changes (verified stub/recording-only — untouched); changes to
structure-adapter template beats (`BeatDef` in adapters — PLAN-003 surface).

---

## 2. Verified ground truth (2026-10-09)

Consumer list of `planned_beats` beyond the mission's (all incorporated):

| Area | Files |
|---|---|
| API planning | `models.py`, `repository.py`, `schemas.py` (BeatSchema), `contracts.py`, `service.py`, `_helpers.py` (`to_outline_response`, `build_outline_data` — reads `required`), `kb_lifecycle_consumer.py` (`_beat_texts` scans `planned_beats[].text`) |
| API cross-domain | `consistency/ref_index_helpers.py` (name-scan over `planned_beats[].text` + `outline_notes`), `writing/_outline_render.py` (story-suggest `chapter_outline` slot) |
| Core | `planning/models.py` (`ChapterOutlineData.planned_beats`), `planning/sync.py` (rule 4 reads `BeatDef.required`), `planning/__init__.py` (BeatDef export), `context/integration_contracts/_planning_consumer.py` (RULE-03 integration contract) |
| FE | `types/planning.ts` (OutlineBeat + OutlineResponse/UpdateRequest), `types/index.ts` (re-export), `lib/api/planning.ts`, `lib/hooks/usePlanning.ts`, `components/studio/planning/OutlineEditor.tsx` (+ test), `lib/api/__tests__/planning.test.ts` |
| Tests/fakes | `tests/factories.py`, `tests/fakes/fake_outline_repo.py`, `tests/integration/planning/{test_outline_repository,test_planning_api}.py`, `tests/unit/api/planning/test_planning_repository.py`, `tests/unit/api/test_planning_contract.py`, `tests/unit/api/consistency/*` (3), `tests/unit/api/writing/test_story_suggest_chapter_outline.py`, `tests/unit/core/context/test_integration_contracts.py`, `tests/unit/core/planning/{test_sync,test_beat_def,test_adapters_registry}.py`, `tests/unit/core/writing/test_scene_parsing.py`, `tests/unit/planning/test_kb_lifecycle_consumer.py` |

**Write-path defect (load-bearing for §8):** `GenerateRequest.outline`
(REST SSE path) is accepted at `POST /writing/chapters/{id}/generate` but
never persisted (`create_request_row` stores mode+tone only) and never
threaded (`build_pipeline_request` omits it; the stream router passes no
context kwargs). `stream_scene_by_scene` therefore parses
`context.chapter_outline == ""` → one empty scene. The scenes transport
(§8) closes this class of gap for the structured path.

Also verified: Alembic head = `0046_writing_goals` (0047 free); ADR head =
095 (096 free); planning prompt templates are **EN-only**
(`_bundled/planning/en/{outline,timeline,temporal_consistency,timeline_extraction,character_arc}/system.md`);
PLAN intent profile = `("balanced", "creative")`; PLAN already carries five
governed context modes (ADR-049 D11 mechanism); FE hard limits: component
200 / hook 150 / page 100 / other-ts 400 lines (`scripts/check_frontend_file_size.py`,
new violations fail); `EditorRightPanelId` union +
`EDITOR_RIGHT_PANEL_PRIORITY` drive the editor right panel.

---

## 3. Data model

### 3.1 Table `scene_plans` (Alembic 0047)

```python
class ScenePlan(Base):
    __tablename__ = "scene_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # consecutive 1..N
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # Hybrid KB refs (TimelineEvent / AD-1 pattern): {"id": "<uuid>", "name": "..."} or null
    pov_character_ref: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    location_ref: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    # List, NOT dict[UUID,str]: [{"id": "...", "name": "...", "goal": "..."}]
    present_characters: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    purpose: Mapped[str] = mapped_column(Text, nullable=False, default="")
    conflict: Mapped[str] = mapped_column(Text, nullable=False, default="")
    resolution: Mapped[str] = mapped_column(Text, nullable=False, default="")
    beats: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)  # ordered key events, plain strings
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")  # planned|in_progress|complete
    created_at / updated_at  # DateTime(timezone=True), server_default now(), onupdate — ChapterOutline pattern
```

No unique constraint on `(chapter_id, position)` — renumbering happens in
one transaction; consecutive positions are an application invariant
enforced by the diff-sync (and asserted in tests), not by a DB constraint
that would fight reordering.

### 3.2 Core pure models (`narrare_core/planning/models.py`)

```python
class SceneStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"

@dataclass(frozen=True, slots=True)
class ScenePresence:          # one present_characters entry, name-resolved
    name: str
    goal: str = ""

@dataclass(frozen=True, slots=True)
class ScenePlanData:
    id: UUID
    position: int
    title: str
    pov_character_name: str = ""   # resolved from hybrid ref at the API boundary
    location_name: str = ""
    present_characters: tuple[ScenePresence, ...] = ()
    purpose: str = ""
    conflict: str = ""
    resolution: str = ""
    beats: tuple[str, ...] = ()
    status: SceneStatus = SceneStatus.PLANNED
```

`ChapterOutlineData` gains `scenes: tuple[ScenePlanData, ...] = ()`.
Rationale for name-strings in Core: hybrid refs exist so display survives
KB deletion — sync/render need names, not KB linkage; resolving at the API
boundary keeps Core pure (no JSONB ref semantics in sync rules). During
the transition tasks the `planned_beats: list[BeatDef]` field remains
(default `[]`); it is removed in the Core removal task, after which
`BeatDef` leaves the `narrare_core.planning` package exports (it survives
in `adapters/` as the PLAN-003 template-beat concept — ADR-096 D9).

### 3.3 Migration semantics

- **0047 (`0047_scene_plans`, task T2):** create table + index; backfill —
  for each `chapter_outlines` row, for each old beat
  `{title, description, completed}` at list index i: insert one scene
  (`position=i+1`, `title=beat.title`, `purpose=beat.description`,
  `status="complete" if beat.completed else "planned"`, everything else
  empty). Tolerant of arbitrary JSONB shapes (skip non-dict beats; missing
  keys → defaults — the `planned_beats` shape "is not locked down across
  all creators"). Downgrade = drop table (lossless: `planned_beats` still
  exists at 0047's parent).
- **0048 (`0048_generation_scenes`, task T10):** add
  `generation_requests.scenes JSONB NULL`.
- **0049 (`0049_drop_planned_beats`, task T17):** reverse-migrate scenes →
  beats (`title→title`, `purpose→description`,
  `status=="complete"→completed`), then DROP `chapter_outlines.planned_beats`.
  Downgrade recreates the column (empty) — documented **lossy** for
  scene-only fields (conflict/resolution/beats-of-scene/refs/positions
  beyond first title-purpose pairs) — the ADR-095/0046 "downgrade is an
  explicit user action" stance; the migration docstring says so.
- All three round-trip tests carry `@pytest.mark.schema_mutating` (Q-018
  enforced two-phase serial; downgrade only to the parent revision — the
  0037 pattern).

---

## 4. Sync rules (Core `StructuralSyncChecker` rewrite)

Statuses and priority unchanged (`EMPTY, PLANNED, ON_TRACK, DEVIATED,
COMPLETED`, first match wins):

```
1. not stage_assignment and not has_content                  → EMPTY     (unchanged)
2. stage_assignment and not has_content                      → PLANNED   (unchanged)
3. stage_assignment != suggested_stage                       → DEVIATED  (unchanged)
3b. has_summary and has_content                              → COMPLETED (unchanged)
4. scenes and all(s.status == COMPLETE for s in scenes)
   and has_content                                           → COMPLETED (scene-driven; replaces beat heuristic)
5. scenes and any(s.status in (IN_PROGRESS, COMPLETE)
   for s in scenes)                                          → ON_TRACK  (partially worked against a plan)
6. fallback                                                  → ON_TRACK  (unchanged)
```

Notes: all-`planned` scenes with content fall through to rule 6 (honest
ON_TRACK — content exists, plan untouched). `word_count` no longer feeds
COMPLETED. The legacy rule-4 beat reading is deleted with the Core removal
task; until then the checker dispatches on data shape: `scenes` non-empty ⇒
scene rules (4/5); else legacy beat rule 4 (frozen, tests deleted at
removal). `ensure_outlines`/storyboard aggregation fetch scenes per novel
(one query) and thread them into `ChapterOutlineData`.

---

## 5. API surface

All under the existing `/api/v1/planning` router prefix; ownership =
uid-scoped novel guard (`novel_repo.get_by_id(novel_id, uid)` → 404,
foreign ≡ unknown), exactly the outline endpoints' pattern.

### 5.1 Schemas (`planning/schemas_scenes.py`)

```python
class SceneRefSchema(BaseModel):        # hybrid KB ref
    id: uuid.UUID | None = None        # None = name-only ref (KB id unknown/dead)
    name: str = Field(min_length=1, max_length=300)

class ScenePresenceSchema(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=300)
    goal: str = ""

class SceneSchema(BaseModel):
    id: uuid.UUID
    position: int = Field(ge=1)
    title: str = Field(default="", max_length=500)
    pov_character_ref: SceneRefSchema | None = None
    location_ref: SceneRefSchema | None = None
    present_characters: list[ScenePresenceSchema] = []
    purpose: str = ""
    conflict: str = ""
    resolution: str = ""
    beats: list[str] = []
    status: Literal["planned", "in_progress", "complete"] = "planned"
    created_at: datetime          # response only
    updated_at: datetime          # response only

class ScenePlanAggregateResponse(BaseModel):
    chapter_id: uuid.UUID
    scenes: list[SceneSchema]     # ordered by position; [] when none exist
    version_updated_at: datetime  # max(updated_at) or chapter-independent now()

class ScenePlanSaveRequest(BaseModel):
    scenes: list[SceneSchema]     # whole aggregate; see diff-sync below
```

RULE-17: FE types mirror these field names exactly (`SceneRef`,
`ScenePresence`, `ScenePlan`, `ScenePlanAggregate`, `ScenePlanSaveRequest`).

### 5.2 Endpoints

| Method/Path | Behavior |
|---|---|
| `GET /planning/scenes/{novel_id}/{chapter_id}` | Chapter-guarded aggregate read. **No auto-create** (empty aggregate is a valid state — unlike outlines, nothing needs ensuring); scenes ordered by position. |
| `PUT /planning/scenes/{novel_id}/{chapter_id}` | Whole-aggregate save; server diff-syncs by stable scene id (§5.3); renumbers positions 1..N by payload order; returns the fresh aggregate. |
| `POST /planning/scenes/{novel_id}/{chapter_id}/draft` | AI chapter-level draft. Request `{structure_type: str = "", outline_notes: str = "", chapter_summary: str = "", neighbor_summaries: str = "", instruction: str = "", scene_count: int = 0}` (0 = model chooses, 3–8 enforced). Response `{proposals: list[SceneProposalSchema]}` — **proposals carry NO id** (client assigns UUIDs on insert). Generator only: ZERO DB writes. |
| `POST /planning/scenes/{novel_id}/{chapter_id}/refine` | AI single-scene refinement. Request `{scene: SceneSchema, prev_scene_summary: str = "", next_scene_summary: str = "", chapter_summary: str = "", instruction: str = ""}`. Response `{proposal: SceneProposalSchema}`. Carrying the full scene (not just an id) keeps refine stateless and makes unsaved drafts refinable. ZERO DB writes. |

`SceneProposalSchema` = `SceneSchema` minus `id/position/created_at/
updated_at/status` (title, refs, presences, purpose, conflict, resolution,
beats). The FE applies proposals via the aggregate PUT — single write path
(kb-resolution analyze-only pattern; undo = don't save).

AI endpoints degrade gracefully when no provider is configured:
HTTP 200 with `{"proposals": [], "ai_unavailable": true}` /
`{"proposal": null, "ai_unavailable": true}` (adds an explicit
`ai_unavailable: bool = False` field on both responses) — logged
(`no_ai_provider_configured`), never 5xx (AI-optional feature; remap
precedent).

### 5.3 Diff-sync algorithm (aggregate PUT)

```
existing = repo.list_by_chapter(chapter_id)          # ordered
payload_ids = {s.id for s in request.scenes}
if any id appears twice in payload            → 422 ValidationError("duplicate scene id")
for s in request.scenes:
    if s.id in {e.id for e in existing}       → update row (all editable fields replaced)
    else                                      → insert (client-supplied id becomes PK)
for e in existing where e.id not in payload_ids → delete
renumber: position = 1..N in payload order    # single UPDATE per row
return GET aggregate (fresh read)
```

- **Client-generated UUIDs** (`crypto.randomUUID()` in FE) for new scenes:
  reorder UX and refine-addressing need stable ids before first save; the
  server accepts them as PKs (validated as UUIDs by the schema).
- Unknown-but-well-formed id (exists in another chapter / not at all) ⇒
  **422 ValidationError** (`"unknown scene id"`), not 404 — it is a payload
  integrity error; the chapter-level 404 already covers ownership. A
  malicious id probing another chapter's scene cannot read or mutate it
  (insert would collide on PK → 422; update matches only within this
  chapter's rows).
- Deletion: absent id ⇒ delete (chapter CASCADE covers chapter deletion).
- No optimistic concurrency in v1 (outline-PUT semantics: last write wins);
  FE mutation invalidates its own queries — documented conscious scope.

### 5.4 Module homes (RULE-04/06)

`apps/api/narrare/planning/`: `schemas_scenes.py`, `repository_scenes.py`
(`ScenePlanRepository`), `scene_service.py` (aggregate GET + diff-sync),
`scene_ai_service.py` (+`_scene_ai_factory.py`), `router_scenes.py`
(included from `router.py`; router stays ≤150 lines), protocol additions
in `contracts.py`. Pattern reference: `StoryboardService` wiring +
`_service_factory.py` (lazy `LazyModelResolution`), `AIRemapService` +
`ai_suggest_stage` (prepared-triple kwargs), `StorySuggestService`
(governed-template + graceful-no-provider).

---

## 6. AI assist design

### 6.1 Routing (decision a — resolved)

- **Intent:** reuse `LLMIntent.PLAN` (advisory profile
  `("balanced", "creative")`); **two new context modes**:
  `scene_plan_draft`, `scene_plan_refine` — added to `ROUTE_CONFIGS[PLAN]`
  `allowed_context_modes` and to the manifest's PLAN `context_modes`.
  No new LLMIntent (ADR-096 Option F). RULE-22 §3 check: no existing PLAN
  mode shares the semantics (outline = stage classification; timeline* =
  temporal; character_arc = arc phases).
- **Agent:** `ScenePlanAgent` in `narrare_core/agents/scene_plan_agent.py`
  (extends `NarrareAgent`; RULE-01b), output types in
  `scene_plan_types.py`: `SceneDraftOutput(scenes: list[SceneProposal])`,
  `SceneRefineOutput(scene: SceneProposal)` (pydantic, exported from
  `agents/__init__.py`). Structured output via pydantic-ai output types.
- **Runtime:** API-side `_scene_ai_factory.py` wires
  `LazyModelResolution(LLMIntent.PLAN, uid, novel_id)`; the prepared triple
  `(agent, model_settings, usage_limits)` is built lazily on first use via
  `ModelRegistry.prepare()` (19009e17 kwargs convention) — mirror
  `build_remap_agent`. Usage/cost events flow through the registry
  emission points (ADR-093/094) — no extra wiring.

### 6.2 Templates (decision e — resolved: TWO templates, EN-only)

`prompts/_bundled/planning/en/scene_plan_draft/system.md` and
`.../scene_plan_refine/system.md`. Frontmatter + only `## System Prompt`
(`## First Message` optional) — PROMPT-L2-HEADERS. Required variables:
none (all chapter context is category-3 runtime data on the run prompt);
optional: `project_title`, `genre`, `writing_language` (match
`temporal_consistency` mode). Manifest entries mirror the `character_arc`
mode shape, `fallback_policy: fail_loudly_if_bundled_missing`.

Two templates because draft and refine are different tasks with different
output contracts (N scenes divergent vs 1 scene constrained rewrite) —
one conditional template would need union output + mode-switching
instructions (rejected: worse prompts, more code).

### 6.3 Scene serialization (decision b — resolved)

One pure renderer, `narrare_core/planning/scene_render.py`:

```python
def render_scene_for_prompt(scene: ScenePlanData, number: int | None = None) -> str:
    """Compact scene block; empty sections omitted (the _outline_render style)."""
```

Exact format (each line omitted when its value is empty):

```
Scene 2: The Ambush at the Gate
POV: John Smith
Location: The Castle
Characters: John Smith (wants to warn the guard); Mara (wants to stop him)
Purpose: John must reach the gate before dawn.
Conflict: Mara blocks the path; loyalty vs duty.
Resolution: John talks his way past but at a cost.
Beats:
  1. John reaches the gate
  2. Mara confronts him
  3. The horn sounds
```

- Header line `Scene {number}: {title}` (number omitted when `None`);
  `Characters:` joins presences as `name (goal)` / `name`.
- Category-3 runtime data: passed as the agent run prompt (user channel) —
  remap/coreference precedent. User-authored content is XML-wrapped by the
  caller per RULE-22 §6: the run prompt embeds the renderer output inside
  `<scene_plan>…</scene_plan>` (refine: `<scene_plan>` current +
  `<chapter_context>` neighbors/summary + `<instruction>`; draft:
  `<chapter_context>` summary/notes + `<instruction>`). The wrapping
  lives in the service call-site (data assembly, not prompt-template
  assembly — the `_outline_render` precedent), while all task framing
  stays in the governed templates.
- The same renderer feeds the writing pipeline (§8) — one format, no drift.

---

## 7. Storyboard / consumer adaptations

- `compute_sync`/`build_outline_data` (`_helpers.py`) populate
  `ChapterOutlineData.scenes` from a novel-scoped scene fetch;
  `get_storyboard`/`get_sync_status` thread a `scene_map` alongside
  `outline_map`.
- KB lifecycle consumer + consistency ref-index: scan scene text fields —
  `title`, `purpose`, `conflict`, `resolution`, each `beats[]` entry,
  `present_characters[].name/goal`, `pov_character_ref.name`,
  `location_ref.name` — replacing `planned_beats[].text` scanning.
  Location strings in issues:
  `scene_plans[{id}].purpose` etc. NEVER rewrite (RULE-22 §7 — user
  content).
- Core integration contract `_planning_consumer.py` is updated to document
  the scene-scan semantics (RULE-03 cross-feature contract).
- `writing/_outline_render.py` (story-suggest `chapter_outline` slot):
  renders stage + scenes (title/purpose/beats via the Core renderer,
  compact) + notes; beats section replaced by per-scene blocks.
- Outline GET/PUT keep working, minus `planned_beats` (BeatSchema and the
  request/response fields die in the removal task; unknown request fields
  are ignored by Pydantic default — documented).
- `docs/reference/openapi.json` regenerated at closure.

---

## 8. Write integration

### 8.1 Transport (decision — resolved: persisted snapshot)

1. FE: explicit toggle in `GenerationConfig` — "use scene plans" — shown
   when the current chapter has scene plans; **default ON when plans
   exist** (FE-computed; the FE already has the aggregate for the editor
   panel). Effective scene list goes into the generate request.
2. API schema: `GenerateRequest.scenes: list[GenerateScene] | None = None`
   (`GenerateScene` = SceneSchema minus id/timestamps + `status` — the
   writer needs identity-free plan data). Persisted verbatim to
   `generation_requests.scenes` (JSONB, migration 0048) at
   `start_generation` — the row is the single state carrier between POST
   and stream (closes the dead-outline defect class; snapshot semantics:
   what you approved is what streams).
3. Core: `GenerationRequest.scenes: tuple[SceneSpec, ...] | None = None`
   (`SceneSpec` dataclass in `writing/requests.py`: title, pov, location,
   characters, purpose, conflict, resolution, beats, status). threaded by
   `build_pipeline_request`.
4. `stream_scene_by_scene`: when `request.scenes` is non-empty, iterate
   scenes, render each with `render_scene_for_prompt` (scene number /
   total from the tuple), pass as `author_instructions` — **no
   `parse_scenes()`** on this path. Scene-less requests keep the existing
   `parse_scenes(request.outline or context.chapter_outline)` fallback
   (old clients). `***` separators between scenes unchanged. No template
   change needed (scene text flows through the existing
   `scene_by_scene` mode variables).

### 8.2 FE editor integration (decision d — resolved)

- **Generation toggle**: `GenerationConfig` grows a
  `useScenePlans: boolean` + `hasScenePlans: boolean` prop pair; when
  `hasScenePlans`, render a switch (default on) above the input fields;
  `useGenerationConfig.buildRequest` attaches `scenes` (from the fetched
  aggregate) when `mode === "scene_by_scene" && useScenePlans`. A
  "Plan scenes" link opens the editor scene-plan panel.
- **Editor panel**: new `EditorRightPanelId` member `"scene_plan"` (+
  `EDITOR_RIGHT_PANEL_PRIORITY` slot after `"generation"`); new case in
  `EditorPanelContent` rendering `ScenePlanPanel` (compact: current
  chapter's scenes, status chips, inline edit of
  title/purpose/conflict/resolution/beats/status, save via aggregate PUT,
  AI refine button). Opened from the generation toggle link and the
  command palette panel map. Full management (ordering, characters,
  locations, draft) lives in the Planning tab `ScenePlanEditor`.

---

## 9. Frontend architecture

- `types/planning.ts`: add `SceneStatus`, `SceneRef`, `ScenePresence`,
  `ScenePlan`, `ScenePlanAggregate`, `ScenePlanSaveRequest`,
  `SceneProposal`, draft/refine request/response types; remove
  `OutlineBeat` + `planned_beats` fields in the FE removal task (after
  `OutlineEditor` is replaced).
- `lib/api/planning.ts`: `getScenePlans`, `saveScenePlans`,
  `draftScenes`, `refineScene` (typed wrappers; components never fetch).
- `lib/hooks/usePlanning.ts`: `useScenePlans(novelId, chapterId)`,
  `useSaveScenePlans(novelId)` (invalidates scene + storyboard + sync
  queries), `useDraftScenes(novelId, chapterId)`, `useRefineScene(...)`.
- `components/studio/planning/`: `ScenePlanEditor.tsx` (≤200 lines:
  list + ordering + aggregate save + draft/refine orchestration),
  `SceneCard.tsx` (compact scene display + status chip + expand),
  `SceneForm.tsx` (field editing, character/location name+goal rows,
  beats editor) — a family under the component limit, replacing
  `OutlineEditor.tsx` in `PlanningPanel` (swap + delete old component +
  its test).
- Editor: `components/studio/editor/ScenePlanPanel.tsx` (≤200 lines).
- i18n: `studio` namespace keys under `studio.planning.scenes.*` and
  `studio.generationPanel.useScenePlans*`; en/de/fr parity (RULE-16).

---

## 10. Governance constraints baked into the plan

- **Q-018**: schema-mutating tests carry `@pytest.mark.schema_mutating`;
  the collection guard fails unmarked DDL patterns loudly.
- **FE size gates**: components ≤200, hooks ≤150 lines —
  `check_frontend_file_size.py` ratchet; new violations fail the gate.
- **Prompt governance**: route_table + manifest + templates land together
  (T7); PROMPT-L2-HEADERS; **INFRA-013 adoption contract — runtime
  evidence step**: a test composes each new mode through the real
  PromptComposer (cascade) and asserts the resolved route/template
  version (static manifest presence is not enough); render-test
  convention per template.
- **ADR-093/094**: no extra usage/cost wiring (confirmed — registry
  emission points cover agent runs).
- **Ownership**: uid-scoped guards everywhere; foreign ≡ unknown → 404.
- **Task caps**: ≤3 production files changed / ≤250 new LOC per plan task
  (test files adaptations excluded from the file cap, included in
  review); sub-slicing mandatory where exceeded.
- **Reports**: per-task implementer reports at
  `docs/superpowers/plans/reports/2026-10-09-plan001-T<NN>*.md`
  (status, evidence, gate results, deviations).

---

## 11. Testing strategy (per area)

- **Core sync** (`tests/unit/core/planning/test_sync.py`): scene rules 4/5
  truth table incl. all-planned-with-content fallback; shape dispatch
  during transition; no-behavior-change for scene-less outlines.
- **Renderer** (`test_scene_render.py`): exact format golden tests
  (omitted sections, numbering, presences with/without goal).
- **Migration round-trips** (Q-018): 0047 backfill fidelity (beat list →
  scenes; tolerant shapes); 0049 reverse-migration + documented loss;
  downgrade-to-parent only.
- **Repo/service**: diff-sync matrix (update/insert/delete/duplicate id →
  422/unknown id → 422/renumbering); aggregate GET ordering; fake repo
  twin (`tests/fakes/fake_scene_repo.py`).
- **Router integration** (uid-scoped): 404 foreign/unknown novel; happy
  path GET/PUT/draft/refine; AI endpoints perform ZERO repo writes
  (fake repo call-count assertions); graceful `ai_unavailable`.
- **Agent** (`tests/unit/core/agents/`): TestModel structured output for
  draft/refine.
- **Prompt surface**: composition test per mode (runtime evidence,
  INFRA-013); manifest/route gate green in CI.
- **Writing pipeline**: scenes path renders per-scene prompts (no
  `parse_scenes`), fallback retained; separators/final-usage unchanged.
- **Write API**: scenes persisted at start; threaded at stream; absent →
  old behavior.
- **FE**: hooks (query keys, invalidation), ScenePlanEditor family
  (render + save + draft apply + refine apply), toggle in buildRequest,
  editor panel switch; i18n namespace test coverage (en/de/fr files
  exist); `planning.test.ts` client wrappers.
- **Consumers**: kb-lifecycle + ref-index scan scene fields
  (`stale_name_ref` over `scene_plans[x].purpose` locations);
  story-suggest outline slot renders scenes; integration-contract test
  updated.

---

## 12. RULE-XX mapping (ADR-096 constraints-touch list)

| Rule | How respected |
|---|---|
| 01b/02/02b | ScenePlanAgent in core/agents; prompts only via governed PLAN modes + composer; no app-layer assembly beyond category-3 run data (renderer is data, wrapping is data assembly) |
| 03 | `ScenePlanRepositoryProtocol`, `SceneAIServiceProtocol` (contracts.py) before implementations; integration contract updated |
| 04/06 | sibling-file split (§5.4); FE component family; routers thin |
| 07 | router→service→repo→DB one-way; writing API owns only its snapshot column (no planning repo import in writing) |
| 08 | SQLAlchemy only in repositories |
| 10 | tests per area (§11); coverage thresholds |
| 11 | graceful AI-unavailability logged; empty aggregates legitimate |
| 14 | migrations 0047/0048/0049 land with their model changes, same task |
| 16/17 | FE i18n en/de/fr; TS mirrors schemas field-exactly |
| 18/18b | no hardcoded routing; PLAN cascade resolves per user (effect = resolved config reaches the agent — covered by existing routing tests) |
| 20 | full v1 scope; SSE untouched where REST is correct (AI = proposals, not prose streams) |
| 22 | hybrid refs = user content, never rewritten; name-scan consumers updated; no semantic mode overlap; no new template variables (runtime data channel) |
| 23 | no new type suppressions; fakes implement protocols |
