# Phase 0 Architecture Report — PLAN-001 Scene Planning

> **Date:** 2026-10-09 · **Gate:** pre-implementation (Architecture layer)
> **Branch:** `feature/plan001-scene-planning` (from main 9482c220) — docs only, no production code
> **ADR:** ADR-096 · **Spec:** `docs/superpowers/specs/2026-10-09-plan001-scene-planning-design.md` · **Plan:** `docs/superpowers/plans/2026-10-09-plan001-scene-planning.md`

## STATUS: OK

## Deliverables (evidence)

| File | Content |
|---|---|
| `docs/architecture/decisions/ADR-096-scene-planning.md` | Full ADR (ADR-095 structure: Context / Drivers / Options A–H / Decision 1–10 / Rationale / Consequences / Sustainability / Implementation Notes / Review Triggers) |
| `docs/superpowers/specs/2026-10-09-plan001-scene-planning-design.md` | Binding design: data model, sync rules table, API wire shapes, diff-sync algorithm, AI routing + serialization format, write-integration transport, FE architecture, RULE-22 coherence, testing strategy, RULE-XX mapping |
| `docs/superpowers/plans/2026-10-09-plan001-scene-planning.md` | 17 tasks (T1–T17, sub-sliced from the 12-task skeleton — no merges), writing-plans format, per-task Files/Interfaces/test-first steps, report paths `reports/2026-10-09-plan001-T<NN>.md` |
| `docs/architecture/decisions/INDEX.md` | ADR-096 row added (status: ✅ Accepted — spec, implementation pending) |

## Decisions resolved (spec §§ referenced)

- **(a) LLM routing** — adopted PO recommendation: reuse `LLMIntent.PLAN` + two new governed context modes `scene_plan_draft`/`scene_plan_refine` (ADR-049 D11 mechanism; PLAN already carries 5 modes, no semantic overlap — RULE-22 §3 checked); `ScenePlanAgent` in `core/agents/`; advisory PLAN profile reused; `LazyModelResolution(PLAN)` cascade; no hardcoded routing. No new LLMIntent (would touch enums/profiles/intent-maps for zero benefit). Spec §6.1.
- **(b) Scene serialization** — exact compact format (spec §6.3): `Scene N: {title}` header, `POV:/Location:/Characters: name (goal)/Purpose:/Conflict:/Resolution:/Beats:` numbered; empty sections omitted; ONE Core renderer `scene_render.py::render_scene_for_prompt` shared by AI endpoints and the writing pipeline; category-3 run-prompt channel, XML-wrapped (`<scene_plan>`, `<chapter_context>`, `<instruction>`).
- **(c) Diff-sync** — client-generated UUIDs (`crypto.randomUUID()`) for new scenes (reorder + refine-addressing before first save; AI proposals carry NO id — FE assigns on insert); payload id known ⇒ update, absent ⇒ delete, unknown/duplicate ⇒ 422 ValidationError (payload integrity; chapter-level 404 covers ownership); positions renumbered 1..N by payload order; no optimistic concurrency in v1 (outline-PUT semantics). Spec §5.3.
- **(d) Editor panel** — new `EditorRightPanelId "scene_plan"` (priority slot after `generation`) + case in `EditorPanelContent` rendering compact `ScenePlanPanel`; opened from the generation-config link and command palette; full management stays in the Planning tab. Spec §8.2.
- **(e) draft vs refine** — TWO templates (distinct tasks/outputs: divergent N-scene draft vs constrained single-scene rewrite; one conditional template ⇒ union output + mode-switching — rejected). Spec §6.2.

## Sequencing (binding constraint — resolved)

**Additive-first, drop-last**: T1–T13 add the full scene machinery alongside the beat path (sync dispatches on data shape; 0047 only creates + backfills); T14–T16 remove beat consumers (planning → cross-domain → Core); T17 drops the column (0049). Every per-task commit green; the mission's naive-order hazard (early beat-drop breaking `_helpers.py` / FE) is eliminated. Justification in plan header + ADR-096 D10.

## VERIFICATIONS (additional duties)

- `rg planned_beats`: consumer list **larger than the mission's** — additionally found and incorporated: `consistency/ref_index_helpers.py`, `planning/kb_lifecycle_consumer.py`, `writing/_outline_render.py` (story-suggest slot), Core `context/integration_contracts/_planning_consumer.py`, FE `types/index.ts`, `lib/api/__tests__/planning.test.ts`, `OutlineEditor.test.tsx`, and 14 test/fake/factory files (full table in spec §2). All have plan tasks (T14/T15/T16/T12c/T13c).
- `SceneService.next_scene` = stub (returns current state), `accept_scene` = feedback recording — **untouched in v1** (plan states this).
- Planning prompt templates **EN-only** (5 files under `_bundled/planning/en/`) — new templates follow (EN-only, RULE-22 §5).
- Next Alembic = **0047** (head 0046_writing_goals ✓); next ADR = **096** (head 095 ✓).
- **NEW load-bearing finding:** the REST SSE scene path silently drops the FE `outline` — `create_request_row` persists only mode+tone and `build_pipeline_request` omits it, so `stream_scene_by_scene` parses an empty `context.chapter_outline`. The scenes design (persisted `generation_requests.scenes` snapshot, migration 0048) closes this defect class; documented in ADR-096 Context + spec §2/§8.1.
- FE enforced limits found: `scripts/check_frontend_file_size.py` — component 200 / hook 150 / page 100 / other-ts 400, baseline-ratcheted (new violations fail).
- Q-018 read + baked in: `@pytest.mark.schema_mutating`, serial phase 2, collection guard, downgrade-to-parent-only (0037 pattern).
- Prompt governance chain verified: ROUTE_CONFIGS (route_table.py:178) + manifest context_modes + templates land together (T7); INFRA-013 runtime-evidence step planned (T7 Step 2); ADR-093/094 usage/cost needs no extra wiring (registry emission points cover agent runs).

## DEVIATIONS

1. **Migration split into 0047 (create+backfill) / 0048 (generation_requests.scenes) / 0049 (drop)** instead of a single 0047 doing all three. Justification: RULE-14 (migration lands with its model change in the SAME task) + per-commit greenness + the ≤3-file task cap make a combined create+drop migration a ~20-file commit. 0047 remains the feature's anchor migration as the mission expected.
2. **BeatDef survives in `adapters/`** (six structure adapters, ~55 declarations, PLAN-003 surface). The mission's "BeatDef dies" is scoped precisely: the *stored-beat* fields (`completed` in JSONB; `required` as read by sync) and `ChapterOutlineData.planned_beats` die; the adapter-template `BeatDef` was never part of the drift and is only de-exported from the planning package root (ADR-096 D9).
3. **Task count 17 (sub-sliced) from the 12-task skeleton** — permitted ("sub-slice, do not merge"); the skeleton's T4-early-drop is re-ordered to T14/T17 per the mission's own additive-first recommendation.
4. **Task-cap interpretation**: ≤3 *production* files per task; test-file adaptations excluded from the file count (a model+migration task otherwise cannot fit). Declared in plan Global Constraints.
5. **AI-unavailable responses are HTTP 200 with `ai_unavailable: true`** (graceful AI-optional policy, remap precedent) — not specified by the mission; spec §5.2.

## CONCERNS

- T15 (`_outline_render.py` scene rendering + `_story_suggest_support.py` call site) may touch a 4th file — plan pre-authorizes a sub-slice there.
- `gen_random_uuid()` in the 0047 backfill must be verified against the project's PG version (fallback: Python `uuid4` per row) — flagged in T2 Step 2.
- `ScenePlanAgent` output-type generic parameterization has two valid shapes (union `output_type` vs class-level `OutputT`) — T6 instructs the implementer to pick whichever passes pyright strict (RULE-23).
- Transient branch-internal wire mismatch (BE outline responses keep `planned_beats` until T14; FE drops the field at T13c) is test-green both sides and resolves within the single PR; RULE-17 alignment completes at merge — documented in T13 Step 4.
