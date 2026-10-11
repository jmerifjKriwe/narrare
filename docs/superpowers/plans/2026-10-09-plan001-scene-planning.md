# PLAN-001 Scene Planning — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `chapter_outlines.planned_beats` with a first-class `scene_plans` substrate: aggregate CRUD with diff-sync, AI draft/refine (zero DB writes), scene-driven storyboard sync, and structured scene input for scene-by-scene writing.

**Architecture:** Additive-first. All scene machinery (Core models + sync dispatch, table + backfill, repo/service/router, governed AI routes, write integration, FE) lands alongside the beat path; the beat path is then removed consumer-by-consumer; the column drop is last. Every per-task commit stays green (ADR-096 D10).

**Tech Stack:** FastAPI · SQLAlchemy async · Alembic · pydantic-ai (NarrareAgent) · governed PLAN context modes · Next.js · TanStack Query · vitest.

**Binding docs:** Spec `docs/superpowers/specs/2026-10-09-plan001-scene-planning-design.md` (wire shapes, algorithms) · ADR-096. Where this plan and the spec disagree, the spec wins; report the deviation.

## Global Constraints

- ≤3 production files changed / ≤250 new LOC per task (test-file edits excluded from the file cap). Sub-slice (a/b) rather than exceed.
- Project language: English everywhere (code, comments, tests, docs). i18n message files are the only exception.
- RULE-14: model change + its Alembic migration land in the SAME task.
- Q-018: schema-mutating tests carry `@pytest.mark.schema_mutating`; round-trips downgrade ONLY to the parent revision (0037 pattern); run via `just test` (serial phase 2).
- Prompt governance: templates EN-only under `prompts/_bundled/planning/en/`; only `## System Prompt` / `## First Message` may use `## ` headers (PROMPT-L2-HEADERS); manifest + route_table + templates land together.
- FE hard limits: components ≤200 lines, hooks ≤150 (`scripts/check_frontend_file_size.py` — new violations fail the gate). i18n: every new `useTranslations` key in en/de/fr (RULE-16); TS mirrors backend field names exactly (RULE-17).
- Ownership: uid-scoped guards; foreign ≡ unknown → 404. AI endpoints: ZERO DB writes.
- No `pydantic_ai.Agent` outside `core/agents/` (RULE-01b); no prompt assembly outside `core/prompts/` except category-3 run-prompt data (RULE-02).
- Gates per task: `just test-unit` (or scoped pytest), `just check-architecture`, FE: `cd packages/web && pnpm test && pnpm type-check && pnpm lint:check`.
- Per-task report: `docs/superpowers/plans/reports/2026-10-09-plan001-T<NN>.md` (sub-task reports fold into the parent letter file). Report contract: status, evidence (commands + results), gate results, deviations.
- Do NOT commit with `--no-verify`. Commits are routed through the Platform specialist by the coordinator.

---

### Task 1: Core scene models, scene-driven sync, scene renderer

**Files:**
- Modify: `packages/core/narrare_core/planning/models.py`
- Modify: `packages/core/narrare_core/planning/sync.py`
- Create: `packages/core/narrare_core/planning/scene_render.py`
- Test: `tests/unit/core/planning/test_sync.py`, `tests/unit/core/planning/test_scene_render.py`
- Modify: `packages/core/narrare_core/planning/__init__.py` (exports only)

**Interfaces:**
- Consumes: existing `ChapterOutlineData`, `SyncStatus`, `BeatDef` (still present — additive task).
- Produces (later tasks rely on these exact names):
  - `SceneStatus(StrEnum)` with `PLANNED="planned"`, `IN_PROGRESS="in_progress"`, `COMPLETE="complete"`
  - `ScenePresence` dataclass: `name: str`, `goal: str = ""`
  - `ScenePlanData` frozen dataclass (slots): `id: UUID`, `position: int`, `title: str`, then defaults `pov_character_name: str = ""`, `location_name: str = ""`, `present_characters: tuple[ScenePresence, ...] = ()`, `purpose: str = ""`, `conflict: str = ""`, `resolution: str = ""`, `beats: tuple[str, ...] = ()`, `status: SceneStatus = SceneStatus.PLANNED`
  - `ChapterOutlineData.scenes: tuple[ScenePlanData, ...] = ()` (new field AFTER existing fields, default — old constructors stay valid)
  - `render_scene_for_prompt(scene: ScenePlanData, number: int | None = None) -> str`
  - `StructuralSyncChecker.calculate_sync_status(outline, suggested_stage) -> SyncStatus` (signature unchanged — behavior adds scene dispatch)

- [ ] **Step 1: Write failing sync tests** — add to `tests/unit/core/planning/test_sync.py`:

```python
def _scene(status: SceneStatus, cid: UUID | None = None) -> ScenePlanData:
    return ScenePlanData(id=cid or uuid.uuid4(), position=1, title="S", status=status)

def test_all_complete_scenes_with_content_is_completed() -> None:
    outline = _outline(has_content=True, scenes=(_scene(SceneStatus.COMPLETE),))
    assert check(outline, "act-1") is SyncStatus.COMPLETED

def test_partial_scenes_is_on_track() -> None:
    outline = _outline(has_content=True, scenes=(
        _scene(SceneStatus.COMPLETE), _scene(SceneStatus.IN_PROGRESS)))
    assert check(outline, "act-1") is SyncStatus.ON_TRACK

def test_all_planned_scenes_with_content_falls_back_on_track() -> None:
    outline = _outline(has_content=True, scenes=(_scene(SceneStatus.PLANNED),))
    assert check(outline, "act-1") is SyncStatus.ON_TRACK

def test_all_complete_scenes_without_content_is_not_completed() -> None:
    # no content → rule 2 PLANNED fires before scene rules
    outline = _outline(has_content=False, scenes=(_scene(SceneStatus.COMPLETE),), stage="act-1")
    assert check(outline, "act-1") is SyncStatus.PLANNED

def test_no_scenes_legacy_path_unchanged() -> None:
    # beats path still applies while planned_beats exists (transition)
    outline = _outline(has_content=True, word_count=500, beats=(BeatDef("b", "d", True),))
    assert check(outline, "act-1") is SyncStatus.COMPLETED
```

(`_outline` = existing local helper, extended with `scenes=()` / `beats=()` kwargs.)

- [ ] **Step 2: Run** `uv run --all-packages pytest tests/unit/core/planning/test_sync.py -v` — expect FAIL (`ScenePlanData` missing).

- [ ] **Step 3: Implement** — `models.py`: add `SceneStatus`, `ScenePresence`, `ScenePlanData`, `ChapterOutlineData.scenes` field + export. `sync.py`: replace rule 4 with shape dispatch:

```python
# Rule 4 (scene-driven, ADR-096): scenes present ⇒ scene rules
if outline.scenes:
    if (all(s.status is SyncStatus.COMPLETE or s.status is SceneStatus.COMPLETE for s in outline.scenes)
            and outline.has_content):
        return SyncStatus.COMPLETED
    if any(s.status is not SceneStatus.PLANNED for s in outline.scenes):
        return SyncStatus.ON_TRACK
# Legacy rule 4 (frozen during transition; dies with the Core removal task)
required_beats = [b for b in outline.planned_beats if b.required]
if required_beats and outline.word_count > 0:
    return SyncStatus.COMPLETED
```

(use `SceneStatus.COMPLETE` only — fix the sketch's first clause to `s.status is SceneStatus.COMPLETE`.)

- [ ] **Step 4: Write failing renderer tests** — `tests/unit/core/planning/test_scene_render.py` golden tests: full scene renders the exact spec §6.3 block; empty sections omitted; `number=None` omits the `Scene N:` prefix; presences render `name (goal)` / `name`.

- [ ] **Step 5: Implement** `scene_render.py::render_scene_for_prompt` per spec §6.3 (join with `"\n"`, beats numbered `  1. …`).

- [ ] **Step 6: Run both test files + exports** — `uv run --all-packages pytest tests/unit/core/planning/ -v`; `just check-architecture`.

- [ ] **Step 7: Commit** `feat(core): scene plan data model, scene-driven sync dispatch, scene prompt renderer (PLAN-001 T1)` — report `reports/2026-10-09-plan001-T01.md`.

---

### Task 2: `scene_plans` table + Alembic 0047 (create + backfill)

**Files:**
- Modify: `apps/api/narrare/planning/models.py` (add `ScenePlan`)
- Create: `apps/api/alembic/versions/0047_scene_plans.py`
- Test: `tests/integration/test_migration_0047_round_trip.py`

**Interfaces:**
- Consumes: `Base` from `narrare._app.database`; migration parent `0046_writing_goals`.
- Produces: ORM `ScenePlan` (spec §3.1 — exact columns); revision id `"0047_scene_plans"`. **No drop of `planned_beats` here** (that is 0049 / T12).

- [ ] **Step 1: Add the ORM model** per spec §3.1 (hybrid JSONB refs like `TimelineEvent`; `status` default `"planned"`; index on `chapter_id`; CASCADE).

- [ ] **Step 2: Write the migration** — docstring documents backfill mapping + downgrade (drop table; lossless — `planned_beats` still exists at parent). Upgrade:

```python
def upgrade() -> None:
    op.create_table(
        "scene_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("pov_character_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("location_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("present_characters", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default="[]"),
        sa.Column("purpose", sa.Text(), nullable=False, server_default=""),
        sa.Column("conflict", sa.Text(), nullable=False, server_default=""),
        sa.Column("resolution", sa.Text(), nullable=False, server_default=""),
        sa.Column("beats", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="planned"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scene_plans_chapter_id", "scene_plans", ["chapter_id"])
    # Backfill: one scene per old beat (tolerant of arbitrary JSONB shapes)
    conn = op.get_bind()
    outlines = conn.execute(
        sa.text("SELECT id, chapter_id, planned_beats FROM chapter_outlines")
    ).mappings()
    for row in outlines:
        for i, beat in enumerate(row["planned_beats"] or [], start=1):
            if not isinstance(beat, dict):
                continue
            conn.execute(
                sa.text(
                    "INSERT INTO scene_plans (id, chapter_id, position, title, purpose, status)"
                    " VALUES (gen_random_uuid(), :chapter_id, :position, :title, :purpose, :status)"
                ),
                {
                    "chapter_id": row["chapter_id"],
                    "position": i,
                    "title": str(beat.get("title", "") or "")[:500],
                    "purpose": str(beat.get("description", "") or ""),
                    "status": "complete" if beat.get("completed") else "planned",
                },
            )
```

(`gen_random_uuid()` — pgcrypto/pg13+ builtin; verify availability on the project PG version, else use Python `uuid4()` per row.)

- [ ] **Step 3: Write the round-trip test** (`@pytest.mark.schema_mutating`, subprocess alembic like `test_migration_0037_round_trip.py`, `_PARENT_REVISION = "0046_writing_goals"`): seed a `chapters` + `chapter_outlines` row with beats `[{title,description,completed:true},{title,description,completed:false}, "garbage"]` at head; downgrade to 0046 (table gone); re-upgrade to head; assert 2 scene rows (garbage skipped) with `position` 1,2 and mapped `status`/`purpose`.

- [ ] **Step 4: Run** `uv run --all-packages pytest tests/integration/test_migration_0047_round_trip.py -v -m schema_mutating` then full `just test` (two-phase serial runs it).

- [ ] **Step 5: Commit** `feat(api): scene_plans table + planned_beats backfill (Alembic 0047, PLAN-001 T2)` — report T02.

---

### Task 3: Scene repository + contract

**Files:**
- Create: `apps/api/narrare/planning/repository_scenes.py`
- Modify: `apps/api/narrare/planning/contracts.py` (+`ScenePlanRepositoryProtocol`, +`SceneAIServiceProtocol` placeholder-free — add it in T7 instead; here only the repo protocol)
- Test: `tests/unit/api/planning/test_scene_repository.py` (+ integration rows in existing `tests/integration/planning/` if convenient)
- Create: `tests/fakes/fake_scene_repo.py`

**Interfaces:**
- Consumes: `ScenePlan` (T2), `BaseRepository` (`narrare._app.base_repository`).
- Produces:

```python
class ScenePlanRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None: ...
    async def list_by_chapter(self, chapter_id: uuid.UUID) -> list[ScenePlan]: ...          # ORDER BY position
    async def list_by_novel(self, novel_id: uuid.UUID) -> list[ScenePlan]: ...              # join chapters, ORDER BY chapter.position, scene_plans.position
    async def get(self, scene_id: uuid.UUID) -> ScenePlan | None: ...
    async def bulk_replace(self, chapter_id: uuid.UUID, rows: list[ScenePlan]) -> list[ScenePlan]:
        """Delete rows absent from `rows` (by id), insert new ids, update
        existing ids' fields, renumber position 1..N in `rows` order, flush+refresh."""
```

`ScenePlanRepositoryProtocol` in `contracts.py` mirrors these signatures (RULE-03). `FakeScenePlanRepository` implements the Protocol in-memory (RULE-23 — no MagicMocks).

- [ ] **Step 1: Write failing unit tests** with a fake session or the existing repo-test harness (`tests/unit/api/planning/test_planning_repository.py` pattern): bulk_replace update/insert/delete/renumber matrix; ordering.
- [ ] **Step 2: Run** — expect FAIL (module missing).
- [ ] **Step 3: Implement** repository + protocol + fake. `bulk_replace` does the delete/insert/update/renumber in one flush (`session.add`/`delete`, `setattr`).
- [ ] **Step 4: Run tests + `just check-architecture`** (RULE-19: constructor takes `AsyncSession` directly — repo, not a dependency factory; SessionDep rule applies to deps files only).
- [ ] **Step 5: Commit** `feat(api): scene plan repository + protocol + fake (PLAN-001 T3)` — report T03.

---

### Task 4: Scene schemas + aggregate service (diff-sync)

**Files:**
- Create: `apps/api/narrare/planning/schemas_scenes.py`
- Create: `apps/api/narrare/planning/scene_service.py`
- Test: `tests/unit/planning/test_scene_service.py`

**Interfaces:**
- Consumes: `ScenePlanRepositoryProtocol` (T3), `ScenePlan` (T2), `narrare.novels` repo (ownership), `narrare.chapters` repo.
- Produces (exact, spec §5.1):
  - Schemas: `SceneRefSchema`, `ScenePresenceSchema`, `SceneSchema`, `ScenePlanAggregateResponse`, `ScenePlanSaveRequest` (+ `SceneProposalSchema`, `SceneDraftRequest/Response`, `SceneRefineRequest/Response` — defined now so T7/T8 only wire them), field-for-field per spec.
  - `ScenePlanService(outline-less; ctor: scene_repo: ScenePlanRepositoryProtocol, chapter_repo: ChapterRepositoryProtocol, novel_repo: NovelRepositoryProtocol)`:
    - `async def get_aggregate(self, chapter_id: UUID, user_id: UUID, *, novel_id: UUID) -> ScenePlanAggregateResponse` — uid-scoped novel guard (`get_by_id(novel_id, user_id)` → `NotFoundError`), chapter must belong to novel, scenes ordered by position. No auto-create.
    - `async def save_aggregate(self, chapter_id: UUID, request: ScenePlanSaveRequest, user_id: UUID, *, novel_id: UUID) -> ScenePlanAggregateResponse` — diff-sync per spec §5.3: duplicate payload id → `ValidationError("duplicate scene id")`; id not in chapter's rows → treated as insert (PK collision ⇒ DB IntegrityError → `ValidationError("unknown scene id")`); absent ⇒ delete; renumber; return fresh `get_aggregate`.
  - Mapping helpers (`_to_schema(row)`, `_from_schema(schema) -> ScenePlan`) live in `scene_service.py` (module-private, RULE-06).

- [ ] **Step 1: Write failing tests** (FakeScenePlanRepository + fake novel/chapter repos from existing fakes): get_aggregate ordering + 404 foreign novel; save matrix — insert (client UUID), update, delete-by-absence, renumbering, duplicate id → 422-ish `ValidationError`, foreign scene id → `ValidationError`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** schemas + service (mapping + guards + `bulk_replace` call).
- [ ] **Step 4: Run** `uv run --all-packages pytest tests/unit/planning/test_scene_service.py -v` + `just check-architecture`.
- [ ] **Step 5: Commit** `feat(api): scene plan aggregate schemas + diff-sync service (PLAN-001 T4)` — report T04.

---

### Task 5: Scene routes (GET/PUT) + factory wiring

**Files:**
- Create: `apps/api/narrare/planning/router_scenes.py`
- Modify: `apps/api/narrare/planning/router.py` (include only)
- Modify: `apps/api/narrare/planning/_service_factory.py` (+`get_scene_plan_service`)
- Test: `tests/integration/planning/test_scenes_api.py`

**Interfaces:**
- Consumes: `ScenePlanService` (T4), `CurrentUserIdDep`/`SessionDep`, ownership → `NotFoundError` → existing 404 handler (foreign ≡ unknown).
- Produces: `GET /planning/scenes/{novel_id}/{chapter_id}` and `PUT …` (spec §5.2) — thin routers, immediate delegation (RULE-06). Router file ≤150 lines.

```python
router_scenes = APIRouter(prefix="/planning/scenes", tags=["planning"])

@router_scenes.get("/{novel_id}/{chapter_id}", response_model=ScenePlanAggregateResponse)
async def get_scene_plans(novel_id: uuid.UUID, chapter_id: uuid.UUID,
                          user_id: CurrentUserIdDep, session: SessionDep) -> ScenePlanAggregateResponse:
    service = get_scene_plan_service(session)
    return await service.get_aggregate(chapter_id, uuid.UUID(user_id), novel_id=novel_id)
```

(`get_scene_plan_service(session)` — plain repo wiring, no model routing; the factory function mirrors `get_storyboard_service`'s eager-repo style minus resolution.)

- [ ] **Step 1: Write failing integration tests** — happy GET (seeded scenes), empty aggregate `{"chapter_id": …, "scenes": []}`, PUT diff-sync round-trip, foreign novel → 404, foreign user's novel → 404.
- [ ] **Step 2: Run** `uv run --all-packages pytest tests/integration/planning/test_scenes_api.py -v` — FAIL (404s from missing routes).
- [ ] **Step 3: Implement** router + include (`router.include_router(router_scenes)`) + factory; update `tests/unit/api/test_planning_contract.py` with the new response schema shape if it enumerates planning schemas.
- [ ] **Step 4: Run** integration file + `just check-architecture` (router purity + size gates).
- [ ] **Step 5: Commit** `feat(api): scene plan aggregate GET/PUT routes (PLAN-001 T5)` — report T05.

---

### Task 6: Core `ScenePlanAgent` + output types

**Files:**
- Create: `packages/core/narrare_core/agents/scene_plan_types.py`
- Create: `packages/core/narrare_core/agents/scene_plan_agent.py`
- Modify: `packages/core/narrare_core/agents/__init__.py` (export)
- Test: `tests/unit/core/agents/test_scene_plan_agent.py`

**Interfaces:**
- Consumes: `NarrareAgent` base (`model=`, `deps_type=`, `output_type=`, `system_prompt=` constructor kwargs — verified against `summary_agent.py`).
- Produces:
  - `SceneProposal(BaseModel)`: `title: str = ""`, `pov_character_name: str = ""`, `location_name: str = ""`, `present_characters: list[ScenePresenceModel] = []` (`ScenePresenceModel(name: str, goal: str = "")`), `purpose: str = ""`, `conflict: str = ""`, `resolution: str = ""`, `beats: list[str] = []`
  - `SceneDraftOutput(BaseModel)`: `scenes: list[SceneProposal] = []`
  - `SceneRefineOutput(BaseModel)`: `scene: SceneProposal`
  - `ScenePlanDeps`: `language: str = "en"`, `genre: str = ""`, `project_title: str = ""`
  - `ScenePlanAgent(model, output_type: type[SceneDraftOutput] | type[SceneRefineOutput], system_prompt: str | None = None)` — passes through to `NarrareAgent.__init__`.

```python
class ScenePlanAgent(NarrareAgent[ScenePlanDeps, SceneDraftOutput | SceneRefineOutput]):
    """Scene-planning agent — chapter draft (N scenes) or single-scene refine."""

    def __init__(self, model: Any,
                 output_type: type[SceneDraftOutput] | type[SceneRefineOutput],
                 system_prompt: str | None = None) -> None:
        super().__init__(model=model, deps_type=ScenePlanDeps,
                         output_type=output_type, system_prompt=system_prompt)
```

(If the base's generic parameterization rejects the union at typing level, parametrize the class over `OutputT` — `class ScenePlanAgent[OutputT](NarrareAgent[ScenePlanDeps, OutputT])` with `output_type: type[OutputT]`. Verify with pyright; pick whichever passes strict.)

- [ ] **Step 1: Write failing agent tests** (TestModel, mirror `summary_agent` tests): draft run returns `SceneDraftOutput` with ≥1 proposal; refine run returns `SceneRefineOutput`; output_validator-style guard (reject empty title+purpose both empty → `ModelRetry` or validator — follow `summary_agent`'s `_validate_output` pattern).
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** types + agent + export (`from narrare_core.agents.scene_plan_agent import ScenePlanAgent, ScenePlanDeps` in `agents/__init__.py`).
- [ ] **Step 4: Run** `uv run --all-packages pytest tests/unit/core/agents/test_scene_plan_agent.py -v` + `just check-architecture` (RULE-01b import scan).
- [ ] **Step 5: Commit** `feat(core): ScenePlanAgent with draft/refine structured outputs (PLAN-001 T6)` — report T06.

---

### Task 7: Governed prompt surface (2 templates + routes + manifest)

**Files:**
- Create: `packages/core/narrare_core/prompts/_bundled/planning/en/scene_plan_draft/system.md`
- Create: `packages/core/narrare_core/prompts/_bundled/planning/en/scene_plan_refine/system.md`
- Modify: `packages/core/narrare_core/prompts/route_table.py` (PLAN `allowed_context_modes` + comment)
- Modify: `scripts/architecture/prompt-surface-manifest.yaml` (PLAN `context_modes` entries)
- Test: `tests/unit/core/prompts/test_scene_plan_routes.py`

**Interfaces:**
- Consumes: ADR-049 D11 context-mode mechanism; existing PLAN route (`category="planning"`, default mode `outline`).
- Produces: modes `scene_plan_draft` and `scene_plan_refine` resolvable via `composer.build(LLMIntent.PLAN, PromptContext(language="en", mode="scene_plan_draft"))`. Template variables: none required; optional `project_title`, `genre`, `writing_language` (mirror `temporal_consistency`). Task framing (JSON-ish scene structure description matching `SceneProposal`) lives IN the templates; chapter/scene data is category-3 run-prompt (never templated).

- [ ] **Step 1: Write both templates** — frontmatter (`prompt_type: planning`, `prompt_language: en`, `prompt_version: "1.0.0"`), single `## System Prompt` section. Draft: role (story structure planner), input description (`<chapter_context>`, `<instruction>` XML tags on the run prompt), output contract = JSON array of scene objects (title, pov_character_name, location_name, present_characters[name,goal], purpose, conflict, resolution, beats), guidance 3–8 scenes, each scene must change something. Refine: single-scene constrained rewrite — preserve the scene's role/position intent, honor `<instruction>`, same object shape, no new scenes.
- [ ] **Step 2: Write failing route tests** (`test_scene_plan_routes.py`): real PromptComposer cascade resolves both modes (EN) and returns a non-empty system prompt containing the template's task marker; unknown-locale fallback per planning convention (EN-only); **INFRA-013 runtime evidence**: assert `composer.build(...)` for each mode succeeds AND record the resolved route (template path/version) in the test output — this is the runtime-adoption evidence, static manifest presence alone is insufficient.
- [ ] **Step 3: Wire ROUTE_CONFIGS** — add both modes to `LLMIntent.PLAN` `allowed_context_modes` with an ADR-096 comment.
- [ ] **Step 4: Add manifest entries** mirroring `character_arc`'s shape (`content_type: customizable_feature_prompt`, `required_variables: []`, `optional_variables: [project_title, genre, writing_language]`, `fallback_policy: fail_loudly_if_bundled_missing`).
- [ ] **Step 5: Run** route tests + `just check-architecture` (prompt-surface gate: manifest ↔ routes ↔ templates consistent; ORPHAN-TEMPLATE satisfied by declaration — ADR-049 D11 note).
- [ ] **Step 6: Commit** `feat(prompts): governed scene_plan_draft/refine PLAN modes (PLAN-001 T7)` — report T07.

---

### Task 8: AI service + endpoints (draft/refine, zero DB writes)

**Files:**
- Create: `apps/api/narrare/planning/scene_ai_service.py`
- Create: `apps/api/narrare/planning/_scene_ai_factory.py`
- Modify: `apps/api/narrare/planning/router_scenes.py` (+2 POST routes)
- Modify: `apps/api/narrare/planning/contracts.py` (+`SceneAIServiceProtocol`)
- Test: `tests/unit/planning/test_scene_ai_service.py`, `tests/integration/planning/test_scenes_api.py` (extend)

**Interfaces:**
- Consumes: `ScenePlanAgent` (T6), governed modes (T7), `render_scene_for_prompt` (T1), `LazyModelResolution` + `get_model_routing_resolver` (ADR-086 pattern from `_service_factory.py`), `DefaultRunLimitResolver` + `ModelRegistry.prepare` (prepared triple, `_remap_helpers.build_remap_agent` pattern), chapter/summary context from chapter repo (`Chapter.summary`).
- Produces:
  - `SceneAIService(scene_repo, chapter_repo, novel_repo, model_registry, *, model_resolution: ModelResolution, composer: PromptComposer | None)`:
    - `async def draft(self, chapter_id, request: SceneDraftRequest, user_id, *, novel_id) -> SceneDraftResponse`
    - `async def refine(self, chapter_id, request: SceneRefineRequest, user_id, *, novel_id) -> SceneRefineResponse`
  - Behavior: uid-scoped novel guard FIRST (gate-before-resolution); lazy resolve (`ConfigurationError` → log `no_ai_provider_configured`, return `ai_unavailable=True` response — HTTP 200, graceful); compose system prompt via `composer.build(LLMIntent.PLAN, PromptContext(language="en", mode=...))`; build run prompt = XML-wrapped category-3 data: draft → `<chapter_context>{structure_type, outline_notes, chapter_summary, neighbor_summaries}</chapter_context><instruction>{instruction}</instruction>`; refine → `<scene_plan>{render_scene_for_prompt(scene)}</scene_plan><chapter_context>{prev/next summaries, chapter_summary}</chapter_context><instruction>{instruction}</instruction>`; run agent with the prepared triple; map output → `SceneProposalSchema`; **ZERO repo writes** (the repos are read-only inputs — enforce by contract test: fake repo `call_count("write") == 0`).
  - Routes: `POST /{novel_id}/{chapter_id}/draft`, `POST /{novel_id}/{chapter_id}/refine` (schemas from T4) — thin delegates.
  - `_scene_ai_factory.get_scene_ai_service(session, user_id, novel_id)` — mirrors `get_storyboard_service` (lazy PLAN resolution; composer + registry eager).

- [ ] **Step 1: Write failing service tests** — happy draft (TestModel-backed fake agent run path via injected factory seam — follow `test_kb_lifecycle_consumer`-style fakes implementing `SceneAIServiceProtocol`), no-provider graceful (`ai_unavailable=True`, no raise), foreign novel 404, zero-write assertion, run-prompt content contains the XML tags + rendered scene block.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** service + factory + protocol + routes + response mapping (`SceneProposal` → `SceneProposalSchema`: names map 1:1; proposals carry NO id).
- [ ] **Step 4: Extend integration tests**: draft 200 shape `{proposals: [...], ai_unavailable: false}` (mocked registry seam or graceful in CI), refine 200, no repo writes in the handler path, foreign novel 404.
- [ ] **Step 5: Run** both files + `just check-architecture` + `just test-unit`.
- [ ] **Step 6: Commit** `feat(api): scene plan AI draft/refine generators (zero-write, PLAN-001 T8)` — report T08.

---

### Task 9: Core writing — `GenerationRequest.scenes` + pipeline consumption

**Files:**
- Modify: `packages/core/narrare_core/writing/requests.py` (+`SceneSpec`, +field)
- Modify: `packages/core/narrare_core/writing/pipeline_scene.py`
- Test: `tests/unit/core/writing/test_scene_parsing.py` (extend) or new `tests/unit/core/writing/test_pipeline_scene_plans.py`

**Interfaces:**
- Consumes: `render_scene_for_prompt` + `SceneStatus` (T1).
- Produces:
  - `SceneSpec` frozen dataclass in `requests.py`: `title: str = ""`, `pov_character_name: str = ""`, `location_name: str = ""`, `present_characters: tuple[tuple[str, str], ...] = ()` (name, goal pairs), `purpose: str = ""`, `conflict: str = ""`, `resolution: str = ""`, `beats: tuple[str, ...] = ()`, `status: str = "planned"` + module helper `scene_spec_from_plan(scene: ScenePlanData) -> SceneSpec` (Core-internal adapter; keeps API layer free of mapping logic).
  - `GenerationRequest.scenes: tuple[SceneSpec, ...] | None = None` (default keeps every existing constructor valid).
  - `stream_scene_by_scene`: when `request.scenes` is truthy → iterate it, `author_instructions=render_scene_for_prompt(spec_as_scene_data, number=idx)` (construct a `ScenePlanData` view or overload the renderer to accept `SceneSpec` — pick ONE: overload `render_scene_for_prompt` to accept `ScenePlanData | SceneSpec` via a small structural adapter, tested); `total_scenes = len(request.scenes)`; **no `parse_scenes` call**. Else existing `parse_scenes(request.outline or context.chapter_outline)` path unchanged.

- [ ] **Step 1: Write failing tests**: scenes present → per-scene prompt input rendered (capture via a stub registry asserting `author_instructions` per call — follow existing pipeline tests' seam), `***` separators + final usage unchanged, N scenes; scenes absent → `parse_scenes` fallback intact (existing tests still green).
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** (keep the dispatch minimal — the mode module stays ≤400 lines).
- [ ] **Step 4: Run** `uv run --all-packages pytest tests/unit/core/writing/ -v` + `just check-architecture`.
- [ ] **Step 5: Commit** `feat(core): structured scene input for scene-by-scene generation (PLAN-001 T9)` — report T09.

---

### Task 10: Write API — persist + thread scenes

**Files (sub-slice if >cap):**
- Modify: `apps/api/narrare/writing/models.py` (+`scenes` JSONB column)
- Create: `apps/api/alembic/versions/0048_generation_scenes.py`
- Modify: `apps/api/narrare/writing/schemas.py` (+`GenerateSceneSchema`, `GenerateRequest.scenes`)
- Modify: `apps/api/narrare/writing/_helpers.py` (`create_request_row` persists scenes; `build_pipeline_request` threads them)
- Test: `tests/unit/api/writing/test_generation_scenes.py`, `tests/integration/test_migration_0048_round_trip.py`

**Interfaces:**
- Consumes: `SceneSpec` (T9), migration parent `0047_scene_plans`.
- Produces:
  - ORM: `scenes: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB, nullable=True)`.
  - `GenerateSceneSchema(BaseModel)`: `title: str = ""`, `pov_character_name: str = ""`, `location_name: str = ""`, `present_characters: list[dict[str, str]] = []`, `purpose: str = ""`, `conflict: str = ""`, `resolution: str = ""`, `beats: list[str] = []`, `status: str = "planned"`; `GenerateRequest.scenes: list[GenerateSceneSchema] | None = None` (FE mirrors in T11).
  - `_helpers.py`: `create_request_row(..., scenes=[s.model_dump() for s in request.scenes] if request.scenes else None)` threaded from `start_generation_request`; `build_pipeline_request` maps row JSON → `tuple[SceneSpec, ...] | None` and passes `scenes=` to `CoreGenRequest`.

- [ ] **Step 1:** T10a — ORM column + migration 0048 (`op.add_column("generation_requests", sa.Column("scenes", postgresql.JSONB(...), nullable=True))` / symmetric drop) + Q-018 round-trip test (downgrade to `0047_scene_plans`).
- [ ] **Step 2:** T10b — schema field + `validate_generation_input` unchanged (scenes are optional input, not a required source) + persist/thread + unit tests: POST with scenes → row JSON; stream-time `build_pipeline_request` returns `request.scenes` tuple; absent → `None` → old behavior.
- [ ] **Step 3: Run** `just test` (round-trip hits serial phase 2) + `just check-architecture`.
- [ ] **Step 4: Commit** `feat(api): persist and thread structured scenes for generation (0048, PLAN-001 T10)` — report T10 (a+b sections).

---

### Task 11: FE 1 — types, API client, hooks

**Files:**
- Modify: `packages/web/types/planning.ts` (+scene types; `OutlineBeat`/`planned_beats` STAY until T12)
- Modify: `packages/web/lib/api/planning.ts` (+4 wrappers)
- Modify: `packages/web/lib/hooks/usePlanning.ts` (+4 hooks + key factory entries)
- Test: `packages/web/lib/api/__tests__/planning.test.ts` (extend), `packages/web/hooks/__tests__` equivalent if hooks are tested there (mirror existing `usePlanning` test placement)

**Interfaces:**
- Consumes: T5/T8 wire shapes (RULE-17 field-exact).
- Produces:
  - Types: `SceneStatus = "planned" | "in_progress" | "complete"`; `SceneRef { id: string | null; name: string }`; `ScenePresence { id: string | null; name: string; goal: string }`; `ScenePlan { id: string; position: number; title: string; pov_character_ref: SceneRef | null; location_ref: SceneRef | null; present_characters: ScenePresence[]; purpose: string; conflict: string; resolution: string; beats: string[]; status: SceneStatus; created_at: string; updated_at: string }`; `ScenePlanAggregate { chapter_id: string; scenes: ScenePlan[]; version_updated_at: string }`; `ScenePlanSaveRequest { scenes: ScenePlan[] }`; `SceneProposal` (ScenePlan minus id/position/status/timestamps); draft/refine request+response types incl. `ai_unavailable`.
  - API: `getScenePlans(novelId, chapterId): Promise<ScenePlanAggregate>`; `saveScenePlans(novelId, chapterId, data: ScenePlanSaveRequest): Promise<ScenePlanAggregate>` (PUT); `draftScenes(novelId, chapterId, body): Promise<SceneDraftResponse>`; `refineScene(novelId, chapterId, body): Promise<SceneRefineResponse>`.
  - Hooks: `useScenePlans(novelId, chapterId | null)` (key `["planning", "scenes", novelId, chapterId]`); `useSaveScenePlans(novelId)` (onSuccess invalidates scene key + storyboard + sync); `useDraftScenes(novelId)`; `useRefineScene(novelId)`.

- [ ] **Step 1: Write failing tests** — client wrappers hit the right URLs/methods/bodies (mock `fetchApi`, existing `planning.test.ts` style); hooks: query keys + invalidation set.
- [ ] **Step 2: Run** `cd packages/web && pnpm test -- planning` — FAIL.
- [ ] **Step 3: Implement** types + wrappers + hooks.
- [ ] **Step 4: Run** `pnpm test && pnpm type-check && pnpm lint:check` (RULE-16 not yet triggered — no new namespace).
- [ ] **Step 5: Commit** `feat(web): scene plan types, API client, hooks (PLAN-001 T11)` — report T11.

---

### Task 12: FE 2 — ScenePlanEditor family (Planning tab)

**Files (sub-slice):**
- Create: `packages/web/components/studio/planning/SceneForm.tsx`
- Create: `packages/web/components/studio/planning/SceneCard.tsx`
- Create: `packages/web/components/studio/planning/ScenePlanEditor.tsx`
- Modify: `packages/web/components/studio/planning/PlanningPanel.tsx` (swap OutlineEditor → ScenePlanEditor)
- Delete: `packages/web/components/studio/planning/OutlineEditor.tsx` (+ its test)
- Modify: `packages/i18n/messages/{en,de,fr}/*.json` (studio namespace keys)
- Test: `packages/web/components/studio/planning/__tests__/ScenePlanEditor.test.tsx` (+ component tests)

**Interfaces:**
- Consumes: T11 hooks/types; existing `SyncStatusBadge` styling idioms; `studio` namespace translations.
- Produces:
  - `ScenePlanEditor({ novelId, chapterId })` (≤200 lines): fetches `useScenePlans`; renders ordered `SceneCard`s; add-scene (client `crypto.randomUUID()`); move up/down (array reorder → save); aggregate save via `useSaveScenePlans`; "Draft with AI" → `useDraftScenes` → inserts proposals as new scenes (assigns UUIDs, positions appended); busy/empty states; per-scene "Refine" delegates to `SceneForm`.
  - `SceneCard({ scene, onEdit, onMoveUp, onMoveDown, onRemove })` (≤200): title, position, status chip (color map planned/in_progress/complete), compact purpose/beats preview, expand → `SceneForm`.
  - `SceneForm({ scene, onChange })` (≤200): fields title/purpose/conflict/resolution/beats (string list editor add/remove/reorder-up-down), POV + location (`SceneRef` name + optional id text), present characters rows (name/goal), status select; "Refine with AI" button → `useRefineScene` (sends current scene + instruction) → applies returned proposal to the local draft (not auto-saved).
  - i18n keys: `studio.planning.scenes.*` (title, addScene, draftWithAi, refineWithAi, statusPlanned/InProgress/Complete, purpose, conflict, resolution, beats, pov, location, characters, characterGoal, moveUp, moveDown, remove, empty, aiUnavailable…) — en/de/fr, identical key sets.

- [ ] **Step 1 (T12a):** Failing component tests for `SceneCard` + `SceneForm` (render + edit callbacks + refine apply) → implement both → green.
- [ ] **Step 2 (T12b):** Failing `ScenePlanEditor` tests (list render, reorder → save payload order, draft insert with UUID assignment, refine wiring) → implement → green.
- [ ] **Step 3 (T12c):** Swap in `PlanningPanel` (keep storyboard tabs untouched), delete `OutlineEditor.tsx` + `__tests__/OutlineEditor.test.tsx`, add i18n keys (all three locales — RULE-16 namespace test must stay green).
- [ ] **Step 4: Run** `pnpm test && pnpm type-check && pnpm lint:check` + FE size gate via `just check-architecture` (frontend gate included) — no new oversized files.
- [ ] **Step 5: Commit** `feat(web): ScenePlanEditor replaces OutlineEditor in Planning tab (PLAN-001 T12)` — report T12 (a/b/c).

---

### Task 13: FE 3 — generation toggle + editor scene-plan panel

**Files (sub-slice):**
- Modify: `packages/web/components/studio/editor/GenerationConfig.tsx` (+toggle + link)
- Modify: `packages/web/components/studio/editor/useGenerationConfig.ts` (+`useScenePlans` state + `buildRequest.scenes`)
- Modify: `packages/web/lib/stores/editorRightPanelState.ts` (+`"scene_plan"` id + priority entry)
- Create: `packages/web/components/studio/editor/ScenePlanPanel.tsx`
- Modify: `packages/web/components/studio/editor-view/EditorPanelContent.tsx` (+case) (+ command-palette panel map if the palette enumerates ids — `useEditorCommandPalette.ts`)
- Modify: `packages/web/types/planning.ts` (remove `OutlineBeat` + `planned_beats` fields — last FE consumers died in T12)
- Modify: `packages/i18n/messages/{en,de,fr}/*.json` (toggle + panel keys)
- Test: `__tests__` for `ScenePlanPanel`, `GenerationConfig` (extend), `useGenerationConfig` (extend), `EditorPanelContent` (extend)

**Interfaces:**
- Consumes: T11/T12; `useScenePlans` hook; `GenerateRequest.scenes` FE shape (`scenes?: ScenePlan[] | null` — T10's `GenerateSceneSchema` mirrored: name/status/pairs fields).
- Produces:
  - `useGenerationConfig` gains `useScenePlans: boolean`, `setUseScenePlans`, optional `scenePlans: ScenePlan[] | null` (injected by `GenerationPanel` from `useScenePlans(novelId, chapterId)`); `buildRequest` attaches `scenes` iff `mode === "scene_by_scene" && useScenePlans && scenePlans?.length` (default ON when plans exist and user hasn't toggled off; explicit-off persists for the session).
  - `GenerationConfig` props + `useScenePlans: boolean; hasScenePlans: boolean; onOpenScenePlans: () => void`; renders the switch above `GenerationInputFields` only when `hasScenePlans`; link "Plan scenes" → opens the `scene_plan` panel.
  - `ScenePlanPanel({ novelId, chapterId, onClose })` (≤200): compact list of the current chapter's scenes (status chips, title, purpose), inline edit of title/purpose/status/beats via `SceneForm`-lite (reuse `SceneCard` in read mode + `SceneForm` on expand — import from `../planning/`), save via `useSaveScenePlans`, "Open full planner" → routes to the Planning tab (existing navigation pattern).
  - `"scene_plan"` inserted in `EDITOR_RIGHT_PANEL_PRIORITY` directly after `"generation"`.

- [ ] **Step 1 (T13a):** Failing tests for `useGenerationConfig` (scenes attached iff toggle+mode+data; default-on with plans) → implement state/buildRequest; extend `GenerationConfig` test (switch renders iff `hasScenePlans`; wire) → implement.
- [ ] **Step 2 (T13b):** Failing `ScenePlanPanel` test + `EditorPanelContent` case test + palette map (if enumerated) → implement panel + id + priority + case + i18n keys (en/de/fr).
- [ ] **Step 3 (T13c):** Remove `OutlineBeat` + `planned_beats` from `types/planning.ts` (+ `types/index.ts` re-export if it re-exports OutlineBeat); fix any residual FE references; `planning.test.ts` mocks updated.
- [ ] **Step 4: Run** `pnpm test && pnpm type-check && pnpm lint:check` + size gates. BE contract check: outline responses still carry `planned_beats` until T14 — FE type simply no longer declares it (extra runtime field harmless; RULE-17 alignment completes at T14; documented in the task report).
- [ ] **Step 5: Commit** `feat(web): scene plans in the editor — generation toggle + panel (PLAN-001 T13)` — report T13 (a/b/c).

---

### Task 14: BE removal 1 — planning domain de-beat

**Files (sub-slice):**
- Modify: `apps/api/narrare/planning/schemas.py` (remove `BeatSchema`, `planned_beats` request/response fields)
- Modify: `apps/api/narrare/planning/_helpers.py` (`to_outline_response` drops beats; `build_outline_data` populates `scenes` via a scene map param; `compute_sync(chapter, outline, suggested, scenes=())`)
- Modify: `apps/api/narrare/planning/service.py` (`update_outline` beats branch removed; `get_storyboard`/`get_sync_status` fetch scenes via `ScenePlanRepository.list_by_novel` and thread `scene_map`)
- Modify: `apps/api/narrare/planning/repository.py` (`create` drops `planned_beats` param — column still exists until T17; write empty list)
- Modify: `apps/api/narrare/planning/contracts.py` (protocol signatures follow)
- Modify: `tests/fakes/fake_outline_repo.py`, `tests/factories.py` (beat factories removed; scene factories added)
- Test updates: `test_planning_api.py`, `test_planning_contract.py`, `test_planning_repository.py`, `test_outline_repository.py`, `tests/unit/planning/test_kb_lifecycle_consumer.py` (beats fixtures → scenes)

**Interfaces:**
- Consumes: `ScenePlanRepository` (T3), `ScenePlanData` mapping (`_to_core_scene(row) -> ScenePlanData` — names resolved from hybrid refs: `pov_character_ref["name"]` when dict else `""`).
- Produces: outline GET/PUT responses WITHOUT `planned_beats` (BEAT-FREE WIRE — FE is clean since T13); storyboard sync computed over scenes; `ensure_outlines` unchanged (auto-create outlines still needed for stage assignment).

- [ ] **Step 1 (T14a):** Update BE tests first (failing): outline response has no `planned_beats`; PUT with `planned_beats` ignores it; storyboard sync uses scene statuses (integration seeds scenes). Then implement schemas/_helpers/service changes → green.
- [ ] **Step 2 (T14b):** Repository/contract/fakes/factories cleanup (create signature, no planned_beats anywhere in planning module except the ORM column itself) → `rg -n "planned_beats" apps/api/narrare/planning/` returns ONLY `models.py` (+ migration history).
- [ ] **Step 3: Run** `just test` + `just check-architecture`; FE suites still green (T13 removed FE consumers; FE api tests mock-based).
- [ ] **Step 4: Commit** `refactor(api)!: outline surface loses planned_beats; sync feeds scenes (PLAN-001 T14)` — report T14 (a/b). NOTE the `!`: wire-breaking within the branch; FE landed first.

---

### Task 15: BE removal 2 — cross-domain consumers

**Files:**
- Modify: `apps/api/narrare/planning/kb_lifecycle_consumer.py` (`_beat_texts` → scene text scan per spec §7; locations `scene_plans[{id}].{field}`)
- Modify: `apps/api/narrare/consistency/ref_index_helpers.py` (same field set, name-scan)
- Modify: `apps/api/narrare/writing/_outline_render.py` (story-suggest `chapter_outline` slot renders scenes via Core renderer + stage + notes)
- Test updates: `tests/unit/planning/test_kb_lifecycle_consumer.py`, `tests/unit/api/consistency/{test_ref_index_helpers,test_ref_index_branches}.py` (+`_ref_index_fakes.py`), `tests/unit/api/writing/test_story_suggest_chapter_outline.py`

**Interfaces:**
- Consumes: `ScenePlan` ORM (or `ScenePlanData`), `render_scene_for_prompt` (T1).
- Produces: scene text extraction helper — ONE shared function per module boundary: `planning/_helpers.py::iter_scene_texts(scene: ScenePlan) -> list[tuple[str, str]]` yielding `(location, text)` pairs over `title/purpose/conflict/resolution/beats[]/present_characters[].name+goal/pov_character_ref.name/location_ref.name` — kb consumer and consistency helper both import it from the planning module's public surface (cross-domain via public export — RULE-05). Story-suggest renders stage + numbered scene blocks + notes.

- [ ] **Step 1:** Failing tests: rename over scene purpose → `stale_name_ref` at `scene_plans[{id}].purpose`; ref-index name hits across all scene fields; story-suggest slot contains rendered scenes (golden).
- [ ] **Step 2:** Implement (keep each file under its RULE-04 limit; `_outline_render` gains a scene branch — takes `scenes: list[ScenePlan]` param from the suggest service call site; that one-line call-site change in `_story_suggest_support.py` may push this sub-task to 4 files — if so, sub-slice the render change out).
- [ ] **Step 3: Run** `just test` + `just check-architecture`.
- [ ] **Step 4: Commit** `refactor(api): KB/ref-index/story-suggest consumers read scene plans (PLAN-001 T15)` — report T15.

---

### Task 16: BE removal 3 — Core de-beat + integration contract

**Files:**
- Modify: `packages/core/narrare_core/planning/models.py` (remove `planned_beats` field + BeatDef import)
- Modify: `packages/core/narrare_core/planning/sync.py` (remove legacy rule-4 branch + BeatDef reading)
- Modify: `packages/core/narrare_core/planning/__init__.py` (remove `BeatDef` export; add scene exports)
- Modify: `packages/core/narrare_core/context/integration_contracts/_planning_consumer.py` (document scene-scan semantics, spec §7)
- Test updates: `tests/unit/core/planning/test_sync.py` (legacy tests deleted), `tests/unit/core/planning/test_beat_def.py` (kept only if it tests the ADAPTER BeatDef — else deleted), `tests/unit/core/context/test_integration_contracts.py`

**Interfaces:**
- Consumes: T14 (no API builder of `planned_beats` remains).
- Produces: `ChapterOutlineData` final shape (scene-based only); `BeatDef` no longer exported from `narrare_core.planning` (survives in `narrare_core.planning.adapters.base` — PLAN-003).

- [ ] **Step 1:** Failing→green loop: remove field → pyright + tests catch stragglers (adapters tests keep passing — they use `adapters.base.BeatDef` directly).
- [ ] **Step 2:** Update the integration contract docstring/protocol docs (scene fields, never-rewrite semantics, hybrid-ref rationale) + its test.
- [ ] **Step 3: Run** `just test` + `just check-architecture` + `uv run pyright` (strict — no new suppressions, RULE-23).
- [ ] **Step 4: Commit** `refactor(core): ChapterOutlineData is scene-based; BeatDef leaves planning exports (PLAN-001 T16)` — report T16.

---

### Task 17: Final drop — Alembic 0049 + closure

**Files:**
- Modify: `apps/api/narrare/planning/models.py` (remove `planned_beats` column)
- Create: `apps/api/alembic/versions/0049_drop_planned_beats.py`
- Modify: `docs/reference/openapi.json` (regenerate — new scene routes, outline without planned_beats)
- Modify: `docs/features/planning/PLAN-001-scene-planning.md` (status → implemented; stale `character_goals: dict` + `POST /api/v1/planning/scenes` sketches amended to the as-built surface; `ui_available_in: [editor]` — CLI promise removed)
- Modify: `docs/architecture/decisions/INDEX.md` + `ADR-096` status → ✅ Implemented
- Test: `tests/integration/test_migration_0049_round_trip.py`

**Interfaces:**
- Consumes: all previous tasks (zero `planned_beats` readers remain — verified by `rg -n "planned_beats"` returning only migration history `0013` + `0047` + docs).
- Produces: final schema; `rg -n "planned_beats" --glob '!docs/**' --glob '!**/alembic/versions/**'` → empty.

- [ ] **Step 1:** Migration 0049 (parent `0048_generation_scenes`): reverse-migrate scenes → beats per spec §3.3 (`INSERT INTO chapter_outlines` update path: build beats JSON per chapter from scene rows ordered by position, `UPDATE chapter_outlines SET planned_beats = :beats`), then `op.drop_column("chapter_outlines", "planned_beats")`. Docstring: downgrade recreates the column EMPTY (data loss documented — scene-only fields have no beat equivalent). Q-018 round-trip test: seed scenes at head → downgrade to 0048 (beats reverse-migrated, column back) → re-upgrade → beats re-migrated into scenes (title/purpose/status survive; lossy fields documented).
- [ ] **Step 2:** Remove the ORM column (same commit — RULE-14); run `just test`.
- [ ] **Step 3:** Docs closure: regenerate openapi (house generation command — check `justfile`/scripts for the openapi recipe; if none, hand-edit to match schemas); feature file amendment; ADR-096 + INDEX flip (Gate: table+migrations, CRUD+AI, sync, write integration, FE, consumers, i18n, tests — all complete).
- [ ] **Step 4:** Verification sweep: `rg -n "planned_beats|BeatDef|OutlineBeat|parse_scenes"` — expected: `BeatDef` only under `adapters/` + adapter tests + PLAN-003 docs; `parse_scenes` only as the retained fallback in `pipeline_scene.py` + its tests; `planned_beats` only in `alembic/versions/{0013,0047,0049}` + history docs.
- [ ] **Step 5:** Full gates: `just test`, `just check-architecture`, `cd packages/web && pnpm test && pnpm type-check && pnpm lint:check`.
- [ ] **Step 6: Commit** `refactor(api)!: drop planned_beats column (Alembic 0049) + PLAN-001 closure (T17)` — report T17.

---

## Self-Review (executed at plan time)

**Spec coverage:** table+migration (T2/T10a/T17) · backfill (T2) · drop (T17) · repo/contracts (T3) · aggregate GET/PUT + diff-sync (T4/T5) · AI draft/refine zero-write (T6/T7/T8) · sync rewrite (T1/T14a) · write integration (T9/T10b) · FE Planning tab (T12) · FE editor panel + toggle (T13) · consumer adaptations (T14/T15/T16) · i18n (T12c/T13b) · openapi/docs closure (T17) · Q-018 (T2/T10/T17) · INFRA-013 runtime evidence (T7 Step 2) · reports (every task). ✓

**Placeholder scan:** every code step carries concrete code or an exact spec-section reference; template content described by required sections + output contract (governed prompt content is authored at implementation time inside the described frame — the frame is complete). ✓

**Type consistency:** `ScenePlanData`/`SceneSpec`/`SceneSchema`/`ScenePlan` names cross-checked across T1/T4/T9/T10/T11. `render_scene_for_prompt` overloads resolved in T9 with a test. ✓

**Known tension (documented, not hidden):** T14 breaks the outline wire before... nothing — FE consumers were removed in T12/T13; branch-internal ordering keeps all suites green per commit; RULE-17 alignment completes at merge (single PR). The spec §8.1 toggle semantics ("default ON when plans exist", session-persisted off) is implemented in T13a exactly.
