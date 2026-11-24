# Assistant Sessions W9 — the entity interview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An interview on the lore-graph page that asks questions fitting the entity's type, takes «Keine Ahnung» and «Alles vorschlagen lassen», proposes relations, and ends in a create dialog that saves an entity with its relations — beside a real create-by-hand path — as W9 of the frontend rebuild.

**Architecture:** Chat owns two tables and five turn-based JSON endpoints and has no surface; knowledge hosts the panel on the graph page and owns the chrome, the catalogs and the E2E. The model's structured answer becomes a kernel helper; the interview is a registered prompt key that runs on the task `chat.ask`. Three PRs by theme under PR-für-PR: create by hand, the substrate with the editor's fifth key, the interview.

**Tech Stack:** React + TanStack Router/Query, Tailwind on the shell tokens, i18n catalogs (de/en/fr), Vitest, pytest, Playwright E2E; FastAPI + async SQLAlchemy + Alembic; the fake LLM provider at its boundary.

**Spec:** `docs/superpowers/specs/2026-11-20-assistant-sessions-design.md` (revised 2026-11-24) with the Stitch brief `docs/superpowers/specs/2026-11-24-entity-interview-stitch-brief.md` — the plan argues from both; executors read both.

## Global Constraints

- Standing rules (`docs/_shared/CONSTRAINTS.md`). Chat and knowledge never import each other; what they share lives in `app/kernel/`.
- **Lane A** end to end: design doc, this plan, one implementer and one reviewer per task, one whole-branch review per PR, a browser leg per PR. **PR für PR**: a PR is finished (`just verify` green, threads resolved, merged) before the next branch starts.
- Three branches off `narrare/main`, one per PR: `feat/knowledge-entity-create`, `feat/chat-sessions`, `feat/entity-interview`. Each in its own worktree; the SDD ledger lives in the main checkout at `.superpowers/sdd/2026-11-24-assistant-sessions-w9/progress.md`.
- Seats come from the local dispatch table: the Implementer seat implements, the Reviewer seat reviews. The plan names no models; the coordinator records the concrete ones in the ledger.
- Conventional commits; `feat` carries a real `User-visible:` line (each task gives it); a commit made through an agent ends with `Assisted-by: OpenCode (<model>)` via `git commit --trailer`. No `--no-verify`, no force push. Nothing is committed before the task's review is green.
- **Mode and acts.** `mode = "knowledge.entity"` is the only mode. `act` ∈ `accept-suggestion | no-idea | fill-all | reject-suggestion | drop-suggestions`; `accept-suggestion`, `no-idea` and `fill-all` call the model, the other two do not. `entity_type` is required and must be one of `ENTITY_TYPES`.
- **Limits, enforced by the server on what the model returned:** name, each alias, each tag and each relation target ≤ 200 characters; relation type ≤ 80; content ≤ 10,000 characters; at most 12 relations; a turn's `text` 1–4000. A string over its limit is cut, a list over its cap keeps its first entries, blank entries are dropped.
- **Bounds:** the model sees the last 20 turns and at most 200 roster entities.
- **Machine markers** (template renders them, the interview's contract requires them, the fake reads them): `PURPOSE: entity-interview`, `TYPE: `, `SLOTS: `, `RELATIONS: `, `TURNS:` then one `ASSISTANT: ` or `USER: ` line per turn oldest first, `ROSTER:` then one `name (type; aliases)` line per entity, `REQUEST: <act>` with `answer` on a plain turn.
- **Reasons on the wire**, shape `{"detail": {"code": …, "detail": …}}`: 404 `not-found` (absent and foreign identical), 409 `session-closed`, 422 `mode-unknown | entity-type-required | entity-type-unknown | entity-invalid | relation-target-invalid | relation-duplicate`, 502 `extraction-failed | provider-unavailable | provider-error`.
- **The turn never holds a transaction across the model call.** Audit rows are collected during the calls and written afterwards: with the turns on success, alone on failure. One row per provider attempt, `task_key` `chat.ask`, `prompt_key` `knowledge.entity-interview`.
- **Prompt key** `knowledge.entity-interview`: `task_key="chat.ask"`, `novel_scopable=True`. The editor's live test resolves on `spec.task_key` and records `task_key = spec.task_key`, `prompt_key = spec.key`.
- **Nothing is written by chat.** The entity and its relations land through `POST /api/knowledge/entities` in one transaction; duplicate names are allowed and a notice in the dialog.
- i18n: three catalogs, sorted, same keys, du-tone in German and tu in French. All interview chrome lives in knowledge's catalogs (chat has none). Transcript and proposal are user content, never localized.
- No invented facts on any face: no percentage, score, persona name or model badge; an open field says «noch offen».
- E2E: per-suite database, `de-DE` contexts, hand-made contexts repeat `locale: "de-DE"`, the fake provider at its boundary, `assert_accessible(page)` on every new face. A flake is fixed, never re-rolled.
- After any branch switch, remove leftover capability `e2e/__pycache__` directories the target branch does not track.

## Review Focus

1. **Another user's session** — a turn, a read or a close against a session id that exists for someone else answers the same 404 as an absent id. Pinned in Task 7.
2. **Nothing left to suggest** — «Alles vorschlagen lassen» on a complete proposal changes nothing and keeps every mark. Pinned in Task 7.
3. **A relation that matches two entities by alias** — the dialog offers the two and blocks nothing; save sends only resolved rows and says so. Pinned in Tasks 2 and 11.
4. **The panel hidden while the model answers** — the reply lands, reopening shows it, the composer is free again. Pinned in Task 10.
5. **Two turns racing on one session** — both land with distinct `seq`, the transcript stays monotonic, and neither erases the other's answer (the proposal is merged, not replaced). Pinned in Task 7.
6. **A model name of 250 characters** — it is cut to 200, the proposal becomes ready, the dialog shows the cut value. Pinned in Task 7.

---

### Task 1: The wave's record (gate — coordinator, no porting)

**Files:** Create `docs/superpowers/specs/2026-11-24-entity-interview-stitch-brief.md`, `docs/superpowers/plans/2026-11-24-assistant-sessions-w9.md`; Modify `docs/superpowers/specs/2026-11-20-assistant-sessions-design.md` (replaced by the revision); Create `docs/design/stitch/screens/knowledge/{entity-interview,entity-interview-dark,entity-interview-states,entity-interview-states-dark,entity-create-dialog,entity-create-dialog-dark}.{html,webp}`; Modify `docs/design/stitch/README.md`.

- [ ] **Step 1: Move the three documents** from `~/.opencode/plan/` into the repo (move, never copy), on `feat/knowledge-entity-create` as its first commit: `chore(docs): the W9 wave's design, brief and plan`.
- [ ] **Step 2: Archive the six screens** the owner approved from `~/.opencode/plan/w9-stitch/` (the `.html` as downloaded, the `.png` converted to WebP quality 82), add the six rows under «Knowledge and lore» with their German titles and heights, and mark the `entity-genesis-ai-dialog` row «überholt durch `entity-interview`». Commit: `chore(docs): the entity interview's six screens join the archive`.
- [ ] **Step 3: Open the SDD ledger** at the path above with the task table of this plan, then the pre-flight scan of shared seams (`crudDialogs.tsx`, `web/lib/query.ts`, `app/capabilities/prompts/router.py`, `chat/prompts.py`).

### PR 1 — create by hand (Tasks 1–3)

### Task 2: An entity can be created by hand, with its relations (PR)

**Files:**
- Create: `app/kernel/errors.py`; `app/capabilities/knowledge/web/entityCreate.ts`; `app/capabilities/knowledge/web/entityCreate.test.ts`; `app/capabilities/knowledge/tests/test_entity_create.py`; `app/capabilities/knowledge/e2e/test_entity_create_e2e.py`
- Modify: `app/capabilities/knowledge/schemas.py`, `service.py`, `router.py`; `app/capabilities/prompts/router.py:195-197`; `app/capabilities/knowledge/web/crudDialogs.tsx` (+ test), `LoreGraphPage.tsx:541-548`, `DossiersPage.tsx:238-245`, `web/i18n/{de,en,fr}.json`; `web/lib/query.ts`

**Interfaces:**
- Produces `coded_detail(code: str, detail: str = "") -> dict[str, str]` in `app/kernel/errors.py`; prompts' `_coded` builds its `HTTPException` with it.
- Produces `POST /api/knowledge/entities` — body `{"novel_id", "name", "type", "aliases": [], "tags": [], "content": "", "relations": [{"to_entity_id", "relation_type", "note": null}]}` → 201 `EntityRead`. Refusals in the coded shape: 404 `not-found` (the novel), 422 `entity-invalid` (detail names the field), 422 `relation-target-invalid` (detail names the row's index), 422 `relation-duplicate`.
- Produces `async def create_entity(self, payload: EntityCreate) -> Entity` on `KnowledgeService`: validates name (non-blank after strip, ≤ 200), type (in `ENTITY_TYPES`) and labels as `update_entity` does, writes the entity and every relation line in one transaction, then `touch_novel` and commit. `accept_suggestion` and `add_relation` call the two private pieces it is split into (`_create_entity_row`, `_place_relation`), so no second copy of the validation exists.
- Produces `resolveRelationTarget(target: string, entities: readonly Entity[]): {kind: "none"} | {kind: "one"; entity: Entity} | {kind: "many"; entities: Entity[]}` (name or alias, trimmed, case-insensitive), `findDuplicateName(name: string, entities: readonly Entity[]): Entity | null`, `buildEntityCreateBody(form: EntityCreateForm): EntityCreateBody` (rows without a resolved target are left out and counted).
- Produces `useCreateEntity(): UseMutationResult<Entity, WireError, EntityCreateBody>` — a `WireError` with `code` and `detail` beside the knowledge hooks, after the prompts' precedent (`app/capabilities/prompts/web/promptsQuery.ts:36-47`); on success invalidates `["knowledge", "entities"]`, `["knowledge", "relations"]` and calls `invalidateNovelShelf()`.
- Produces `EntityCreateDialog` with the props `{novelId, entities, openerId, onClose, onCreated?: (entity: Entity, relations: number) => void}`; Task 11 adds `source` and `prefill` for the interview. Built on the local `Modal` as the sibling dialogs are; the relation label input suggests the graph's known labels through the datalist `CreateRelationDialog` already uses.
- Consumes: the graph's `select(id)` seam and the `entity` search parameter (Task 11 reuses them).

- [ ] **Step 1: Write the failing API tests** in `test_entity_create.py`: `test_create_writes_entity_and_relations_in_one_transaction` (201, the `EntityRead`, each relation readable through `GET /entities/{id}/relations`); `test_foreign_novel_is_404`; `test_invalid_name_and_type_are_422_naming_the_field`; `test_relation_outside_the_novel_refuses_and_leaves_no_row` (entity count before == after); `test_duplicate_relation_line_is_422`; `test_accept_suggestion_still_creates_through_the_shared_core` (the existing extraction tests stay green).
- [ ] **Step 2: Run** `just test-file app/capabilities/knowledge/tests/test_entity_create.py` — FAIL (404 on the route).
- [ ] **Step 3: Implement** the schemas (`RelationLine`, `EntityCreate`), the service split and the route. Run Step 2's command — PASS.
- [ ] **Step 4: Write the failing unit tests** in `entityCreate.test.ts`: `resolves a name`, `resolves an alias`, `two entities sharing an alias give many`, `no match gives none`, `buildEntityCreateBody leaves unresolved rows out`, `findDuplicateName ignores case and surrounding space`. Run `pnpm --dir web vitest run app/capabilities/knowledge/web/entityCreate.test.ts` — FAIL.
- [ ] **Step 5: Implement** `entityCreate.ts`. Run Step 4 — PASS.
- [ ] **Step 6: Write the failing dialog tests** in `crudDialogs.test.tsx`: `save stays disabled until name and type are set`, `the duplicate-name notice shows and keeps save enabled`, `an added relation row is sent`, `a refused save shows code and detail and keeps the fields`. Run the suite — FAIL.
- [ ] **Step 7: Implement** `useCreateEntity`, `EntityCreateDialog` (manual), and make both doors real: «Neue Entität» on the graph and «Neues Dossier» on the dossiers page open it; the permanent-truth note leaves both titles and the catalogs (grep `newEntityNote` before deleting the key). Test ids: `entity-create-dialog`, `entity-create-name`, `entity-create-type`, `entity-create-aliases`, `entity-create-tags`, `entity-create-content`, `entity-create-add-relation`, `entity-create-relation-<n>-entity|label|note`, `entity-create-save`, `entity-create-cancel`, `entity-create-duplicate-note`, `entity-create-unresolved-note`, `graph-new-entity`, `dossiers-new-dossier`. Run Step 6 — PASS.
- [ ] **Step 8: Write the browser legs** in `test_entity_create_e2e.py`: `test_create_by_hand_from_the_graph` (seed canon, open the graph, «Neue Entität», name «Nevada-Trümmerfeld», type «Ort», one tag, one relation to «Forschungsstation 7» with the label «Liegt in», save; the entity is selected and its dossier lists the relation; `assert_accessible(page)`), `test_create_by_hand_from_the_dossiers`, `test_duplicate_name_is_a_notice_not_a_refusal`, `test_required_fields_keep_save_disabled`.
- [ ] **Step 9: Run** `just test-e2e-file app/capabilities/knowledge/e2e/test_entity_create_e2e.py` — PASS.
- [ ] **Step 10: Commit** — `feat(knowledge): an entity can be created by hand, with its relations`; `User-visible: «Neue Entität» on the lore graph and «Neues Dossier» on the dossiers page open a create dialog that saves an entity and its relations in one step; a name that exists already is a notice, not a refusal.`; `Closes #914`.

### Task 3: PR 1 gate

`just verify` green; `just test-e2e knowledge` and `just test-e2e prompts` green (the coded shape touches the prompts router); the whole-branch review; the PR «Entities can be created by hand from the graph and from the dossiers» ready, threads resolved, merged.

### PR 2 — the substrate and the editor's fifth key (Tasks 4–9)

### Task 4: The structured answer is the kernel's (PR)

**Files:** Move `app/capabilities/knowledge/structured.py` → `app/kernel/llm/structured.py` and `app/capabilities/knowledge/tests/test_structured.py` → `app/kernel/tests/test_structured.py`; Modify `app/capabilities/knowledge/jobs.py` (the import), `app/kernel/llm/__init__.py`.

**Interfaces:** Produces `async def ask_structured[T](provider: TextProvider, prompt: str, *, schema: dict[str, object], parse: Callable[[str], T], audit: Callable[[AuditedCall], Awaitable[None]]) -> T` — the only change is `list[T]` → `T`; `MalformedAnswerError` carries its reason as the exception's message and has no `.reason` attribute; `AuditedCall` moves with it. Knowledge's two callers pass their list-returning parse unchanged.

- [ ] **Step 1: Run** `just test-file app/capabilities/knowledge/tests/test_structured.py` — PASS (the baseline).
- [ ] **Step 2: Move and generalise**; add one kernel test `test_ask_structured_returns_an_object` (a stub provider answering `{"reply": "ok"}`, `parse=json.loads`). Run the moved file, the extraction and consistency suites — PASS.
- [ ] **Step 3: Commit** — `refactor(kernel): the structured answer is the kernel's`.

### Task 5: Sessions and turns are stored (PR)

**Files:** Create `app/capabilities/chat/models.py`, `app/capabilities/chat/repository.py`, `app/kernel/db/migrations/versions/<rev>_add_assistant_sessions_and_turns.py` (`down_revision = "9e4b21c7af50"`), `app/capabilities/chat/tests/test_interview_repository.py`.

**Interfaces:**
- Produces `AssistantSession(UserOwned)`, table `assistant_sessions`: `id` (UUID primary key), `novel_id` (FK `novels.id`, `ondelete="CASCADE"`, indexed), `mode` `String(40)`, `entity_type` `String(40)` nullable, `target_id` UUID nullable, `proposal` JSONB nullable, `closed_at`, `created_at`, `updated_at`.
- Produces `AssistantTurn(UserOwned)`, table `assistant_turns`: `id`, `session_id` (FK `assistant_sessions.id`, `ondelete="CASCADE"`, indexed), `seq` `Integer`, `role` `String(16)` (`user` | `assistant`), `text` `Text`, `act` `String(32)` nullable, `suggestion` `Text` nullable, `suggestion_state` `String(16)` nullable, `created_at`; unique `(session_id, seq)` as `uq_assistant_turns_seq`.
- Produces `AssistantSessionRepository(ScopedRepository[AssistantSession])`: `async create(novel_id: UUID, mode: str, entity_type: str | None, target_id: UUID | None) -> AssistantSession`; `async get(session_id: UUID) -> AssistantSession | None`; `async list_for_novel(novel_id: UUID) -> list[AssistantSession]` (newest first); `async lock(session_id: UUID) -> AssistantSession | None` (`SELECT … FOR UPDATE`, still user-scoped); `async last_turns(session_id: UUID, limit: int) -> list[AssistantTurn]` (oldest first); `async next_seq(session_id: UUID) -> int`; `async append_turn(session_id: UUID, seq: int, role: str, text: str, *, act: str | None = None, suggestion: str | None = None, suggestion_state: str | None = None) -> AssistantTurn`; `async set_proposal(session: AssistantSession, proposal: dict[str, object] | None) -> None`; `async set_suggestion_state(turn: AssistantTurn, state: str) -> None`; `async close(session: AssistantSession) -> None`.
- Produces `EntityRosterRepository(ScopedRepository[Entity])` with `async names_for_novel(novel_id: UUID, limit: int = 200) -> list[Entity]` (only `id`, `name`, `type`, `aliases`, ordered by name), and `NovelRepository(ScopedRepository[Novel])` with `async exists(novel_id: UUID) -> bool` and `async heading(novel_id: UUID) -> tuple[str, str | None]` (title, genre when the row carries one).

- [ ] **Step 1: Write the failing repository tests** (`test_interview_repository.py`, fixtures `two_users`, `empty_tables`, `schema`): `create_and_get`, `a_foreign_session_is_none`, `list_is_newest_first_and_own_only`, `last_turns_returns_the_newest_oldest_first`, `seq_is_unique_per_session`, `closing_a_novel_deletes_its_sessions`, `roster_lists_only_the_novel`.
- [ ] **Step 2: Run** `just test-file app/capabilities/chat/tests/test_interview_repository.py` — FAIL.
- [ ] **Step 3: Implement** models, migration and repositories. Run Step 2 — PASS; run the migration against the test database (`just test` for the kernel migration tests) — PASS.
- [ ] **Step 4: Commit** — `chore(chat): sessions and turns are stored`.

### Task 6: The interview prompt is the editor's fifth key (PR)

**Files:** Modify `app/kernel/prompts/registry.py` (`PromptSpec.task_key`, `register(..., task_key=None)`), `app/kernel/llm/contract.py` (marker constants), `app/kernel/llm/fake.py`, `app/capabilities/prompts/service.py:380`, `app/capabilities/prompts/router.py:330-337`, `app/capabilities/chat/prompts.py`, `app/capabilities/prompts/web/PromptsPage.tsx:46-51`, `PromptEditor.tsx:56-74`, `app/capabilities/prompts/web/i18n/{de,en,fr}.json`; Test: `app/kernel/tests/test_prompts_smoke.py`, `test_llm_resolution.py`, `test_fake*.py`, `app/capabilities/prompts/tests/test_prompts_api.py`, `test_prompts_preview_live.py`, `PromptsPage.test.tsx`, `app/capabilities/prompts/e2e/conftest.py:152-158`, `test_prompts_e2e.py:138-168`.

**Interfaces:**
- Produces `PromptSpec.task_key: str` (default: the key) and `register(key, *, template, sample_variables, contract=None, novel_scopable=True, assemble=None, task_key=None)`.
- Produces in `chat/prompts.py`: `INTERVIEW_KEY = "knowledge.entity-interview"`, `INTERVIEW_TEMPLATE`, `interview_contract(rendered: str) -> bool` (requires the `PURPOSE: entity-interview` line and every marker prefix), `interview_sample_variables() -> dict[str, object]`, `async def _assemble_interview(context: LiveTestContext) -> AssembledContext` (the sample beside the user's real roster when `novel_id` is set; facts `type`, `turns`, `roster`), registered with `novel_scopable=True, task_key="chat.ask"`.
- Template variables: `novel_title`, `novel_genre`, `entity_type`, `slots` (JSON), `relations` (JSON), `transcript`, `roster`, `request`. The template renders each on its marker line and carries **one question track per type**: character (name and role; appearance; want and fear; how they speak; who they trust and who they oppose; what they hide), location (name and kind of place; what it looks, sounds and smells like; who goes there; what happened there), faction (name and purpose; who leads it; who belongs; how it acts; friends and enemies), object (name and kind; what it does or opens; who made or owns it; where it comes from), system (name and purpose; how it works and its limits; who runs or relies on it; how it fails), timeline (name and span; what marks beginning and end; what it changes; who keeps it), event (name and when; what happened; who took part; what it caused), generic (name; what it is; what belongs to it). It asks one question per turn, proposes relations only to roster names or names the writer gave, never states a type, and says when nothing is left to ask.
- Produces in the fake: `PURPOSE_INTERVIEW = "entity-interview"` and `_interview_answer(prompt: str) -> str` reading the marker lines: the last `USER:` line `unparseable` → prose, not JSON; `REQUEST: no-idea` → `suggestion` set, `slots` as received; `REQUEST: fill-all` → every open slot filled with canned values and one relation to the first roster entry, type `related_to`; a `USER:` line `Name: X` / `Beschreibung: X` / `Schlagworte: a, b` / `Alias: a, b` / `Beziehung: <name> | <label>` sets that part; otherwise `reply` «Notiert.» with the slots as received. The answer is always the cumulative `slots`.
- Produces in the editor: the fifth key with icon `person`, labels `prompts.key.knowledge.entity-interview` (de «Entität-Interview», en «Entity interview», fr «Entretien d'entité») and `.desc`, `FACT_KEYS` plus `type`, `turns`, `roster`.

- [ ] **Step 1: Write the failing tests:** kernel smoke — the fifth golden (byte-exact sample render) and the key set; fake — `test_fake_interview_answers_each_act`, `test_fake_interview_unparseable_answers_prose`; prompts API — the key set has five; preview-live — `test_interview_live_test_resolves_and_audits_chat_ask` (`task_key == "chat.ask"`, `prompt_key == "knowledge.entity-interview"`); page suite — five cards.
- [ ] **Step 2: Run** `just test-file app/kernel/tests/test_prompts_smoke.py` and the others — FAIL.
- [ ] **Step 3: Implement** the registry field, the markers, the template, the contract, the sample, the assembly, the fake and the editor entry. Run Step 2 — PASS.
- [ ] **Step 4: Grow the prompts E2E** to five cards (both counts and the key loop) and add `test_interview_key_previews_and_tests_live` (the preview shows the `PURPOSE:` and `REQUEST:` lines; the live test against the fake answers a JSON `reply`). Run `just test-e2e-file app/capabilities/prompts/e2e/test_prompts_e2e.py` — PASS.
- [ ] **Step 5: Commit** — `feat(chat): the interview prompt is the editor's fifth key`; `User-visible: the prompts editor lists «Entität-Interview» beside the four keys; its preview shows the marked variables and its live test answers a sample turn.`

### Task 7: Five endpoints carry an interview turn (PR)

**Files:** Create `app/capabilities/chat/interviews.py`, `app/capabilities/chat/tests/test_interviews.py`; Modify `app/capabilities/chat/schemas.py`, `router.py`.

**Interfaces:**
- Produces the schemas: `SessionCreate {mode: str, novel_id: UUID, entity_type: str | None = None, target_id: UUID | None = None}`, `TurnCreate {text: str (1–4000), act: TurnAct | None = None}`, `Proposal {name, name_suggested, aliases, tags, content, suggested: {aliases, tags, content}, relations: [{target, type, note, suggested}]}`, `SessionRead {id, novel_id, mode, entity_type, target_id, proposal, closed_at, created_at, updated_at}`, `TurnRead {seq, role, text, act, suggestion, suggestion_state, created_at}`, `SessionDetail(SessionRead) {turns: [TurnRead]}`, `SessionList {items: [SessionRead]}`, `TurnReadback {reply: str | None, proposal: Proposal | None, suggestion: str | None, seq: int}`.
- Produces `InterviewService(session, user_id)` with `async open_session(payload: SessionCreate) -> AssistantSession`, `async list_sessions(novel_id: UUID) -> list[AssistantSession]`, `async read_session(session_id: UUID) -> AssistantSession` (with `turns` loaded), `async take_turn(session_id: UUID, payload: TurnCreate) -> TurnReadback`, `async close_session(session_id: UUID) -> AssistantSession`.
- Produces the routes under the existing `/api/chat` router: `POST /sessions` → 201 `SessionRead`; `GET /sessions?novel_id=` → `SessionList`; `GET /sessions/{session_id}` → `SessionDetail`; `POST /sessions/{session_id}/turns` → `TurnReadback`; `POST /sessions/{session_id}/close` → `SessionRead` (idempotent). Every refusal in the coded shape with the plan's reasons.
- `take_turn` in order: the short read (409 when closed; its transaction ends) → for the three model acts render `knowledge.entity-interview` and call `ask_structured` with the schema `{reply, slots{name, aliases, tags, content}, relations[{target, type, note}], suggestion}` and a collecting audit callback → the one transaction: `lock`, 409 when closed meanwhile, two turns with `seq` from `next_seq`, the model's changes merged into the proposal as it stands under the lock (output against its own input: changed is written, untouched is kept), audit rows via `record_call`. The two acts without a model write one user turn and the proposal or the suggestion state only. Provenance: new after `fill-all` → suggested; new or changed after any other act → the writer's own; unchanged → kept; `accept-suggestion` marks the pending suggestion `accepted`, `reject-suggestion` marks it `rejected`.
- Consumes: Task 5's repositories, Task 6's key and fake, Task 4's `ask_structured`.

- [ ] **Step 1: Write the failing API tests** (`test_interviews.py`, a stub `TextProvider` at the boundary): `test_open_requires_a_known_mode_and_type` (422 `mode-unknown`, `entity-type-required`, `entity-type-unknown`), `test_foreign_novel_is_404`; `test_a_turn_writes_two_rows_and_the_proposal`; `test_fill_all_marks_its_parts_and_a_plain_turn_does_not`; `test_no_idea_sets_a_pending_suggestion_and_keeps_the_proposal`; `test_accept_and_reject_settle_the_suggestion`; `test_drop_suggestions_removes_the_marked_parts_and_keeps_the_rest`; `test_reject_and_drop_make_no_provider_call`; **Review Focus 1** `test_a_foreign_session_answers_the_absent_404`; **Review Focus 2** `test_fill_all_on_a_complete_proposal_changes_nothing`; **Review Focus 5** `test_two_turns_in_parallel_land_with_distinct_seq_and_keep_both_answers` (turn A adds an alias, turn B a tag, both from the same starting proposal; both are present afterwards); **Review Focus 6** `test_a_long_model_name_is_cut_to_200`; `test_unparseable_twice_is_502_with_two_audit_rows_and_no_turn`; `test_provider_missing_is_502_provider_unavailable`; `test_provider_error_is_502_provider_error`; `test_closed_session_refuses_a_turn_with_409`; `test_close_is_idempotent`.
- [ ] **Step 2: Run** `just test-file app/capabilities/chat/tests/test_interviews.py` — FAIL.
- [ ] **Step 3: Implement** schemas, `InterviewService`, the routes. Run Step 2 — PASS.
- [ ] **Step 4: Commit** — `chore(chat): five endpoints carry an interview turn`.

### Task 8: A capability may declare no path and no nav (PR)

**Files:** Modify `scripts/generate_capabilities.py:255-261` (`facts()` reads `path` as `None` and `nav` as `False` when absent; `typescript_nav` skips a falsy path; `docs_index` prints `—`), its test module (`test_capability_views.py`: a capability without both still generates); `app/capabilities/chat/capability.yaml` (drop `path`, `nav`); regenerate with `just generate`.

- [ ] **Step 1: Write the failing generator test**; run it — FAIL.
- [ ] **Step 2: Implement**; `just generate` changes no generated view (chat has no web module); `just check-generated` — PASS.
- [ ] **Step 3: Commit** — `chore(tooling): a capability may declare no path and no nav`.

### Task 9: PR 2 gate

`just verify` green; `just test-e2e prompts` green; the whole-branch review; the PR «Interviews are stored, and their prompt is the editor's fifth key» ready, threads resolved, merged.

### PR 3 — the interview (Tasks 10–13)

### Task 10: The graph page interviews the author (PR)

**Files:** Create `app/capabilities/knowledge/web/interview/{EntityInterview,TypeChooser,ProposalCard,Transcript,Composer,SessionList}.tsx`, `interview/interviewState.ts`, `interview/useInterview.ts` (+ tests); Modify `app/capabilities/knowledge/web/LoreGraphPage.tsx`, `routes.tsx:89-91` (`validateSearch` gains `interview?: string`), `web/i18n/{de,en,fr}.json`, `web/lib/query.ts`; Create `app/capabilities/knowledge/e2e/test_entity_interview_e2e.py`.

**Interfaces:**
- Produces the hooks in `web/lib/query.ts` (key prefix `["chat", …]`): `useAssistantSessionsQuery(novelId)` (`["chat", "sessions", novelId]`), `useAssistantSessionQuery(sessionId)` (`["chat", "session", sessionId]`), `useOpenAssistantSession()`, `useAssistantTurn()`, `useCloseAssistantSession()` — each mutation invalidates the session and list keys on settle.
- Produces `interviewState.ts`: `interviewFace(input: {session, turns, pending, failure}) -> "chooser" | "question" | "thinking" | "suggestion" | "failed" | "ended"`; `readyToSave(proposal: Proposal | null): boolean` (a name is present); `pendingSuggestion(turns)`. A failed turn is one whose mutation ended in `extraction-failed`, `provider-unavailable` or `provider-error`; each has its copy, all three keep the text and offer «Erneut versuchen».
- Produces the panel as the graph page's right column while the search parameter `interview` holds a session id or `new`; without it the dossier column stands as before. The door «＋ Neue Entität» opens the panel on the newest open session, or on `new`; it carries the count of open interviews. «Von Hand anlegen» on the chooser opens `EntityCreateDialog` with `source: "manual"` — the graph door's own direct path from Task 2 moves here.
- The eleven faces of the states reference, with the German copy of the approved screens, and a twelfth beside them: `provider-error` reads «Die Antwort kam nicht. Dein Text ist noch im Eingabefeld.» with the same «Erneut versuchen». The opening question per type comes from the catalog (`knowledge.interview.opening.<type>`). Under the breakpoint where the dossier column leaves the page's side, the panel takes that column's place. Test ids: `entity-interview`, `entity-interview-type-<type>`, `entity-interview-start`, `entity-interview-manual`, `entity-interview-proposal`, `entity-interview-transcript`, `entity-interview-composer`, `entity-interview-no-idea`, `entity-interview-fill-all`, `entity-interview-send`, `entity-interview-save`, `entity-interview-end`, `entity-interview-suggestion` with `-accept`, `-edit`, `-reject`, `entity-interview-drop-suggestions`, `entity-interview-retry`, `entity-interview-settings-door`, `entity-interview-list`, `entity-interview-sessions`, `graph-new-entity-count`.
- The chips send: «Keine Ahnung» `{text: <its label>, act: "no-idea"}`; «Alles vorschlagen lassen» `{text: <its label>, act: "fill-all"}`; «Übernehmen» `{text: <the suggestion>, act: "accept-suggestion"}`; «Ändern» puts the suggestion into the composer; «Verwerfen» `{text: <its label>, act: "reject-suggestion"}`; «Vorschläge verwerfen» `{text: <its label>, act: "drop-suggestions"}`. A failed turn keeps the text in the composer; «Erneut versuchen» sends it again.
- Accessibility: the panel is a labelled complementary region; the pending row and each answer are a `role="status"` region that is not empty at mount; every face passes `assert_accessible`.

- [ ] **Step 1: Write the failing unit tests** (`interviewState.test.ts`, `EntityInterview.test.tsx`): `the face follows the session`, `ready needs a name`, `each chip sends its act`, `a failed turn keeps the text`, `hide does not close`, `ending makes it read-only`.
- [ ] **Step 2: Implement** the hooks, the state, the six components, the door and the search parameter. Run Step 1 — PASS.
- [ ] **Step 3: Write the browser legs** (`test_entity_interview_e2e.py`): `test_the_interview_asks_and_collects` (chooser «Objekt», start, «Name: Resonanz-Transponder LC-89», the proposal card names it and «Als Entität speichern» enables); `test_no_idea_offers_a_suggestion_with_three_actions`; **Review Focus 4** `test_hiding_the_panel_while_the_model_answers_keeps_the_reply`; `test_the_interview_survives_a_reload`; `test_ending_makes_the_interview_read_only_and_keeps_it_savable`; `test_rejecting_a_suggestion_returns_to_the_question`; `test_suggestions_can_be_discarded`; `test_unparseable_shows_the_named_face_and_keeps_the_text`. `assert_accessible` on the chooser, the conversation, the suggestion card and the failed face.
- [ ] **Step 4: Run** `just test-e2e-file app/capabilities/knowledge/e2e/test_entity_interview_e2e.py` — PASS.
- [ ] **Step 5: Commit** — `feat(knowledge): the graph page interviews the author`; `User-visible: «Neue Entität» on the lore graph opens an interview that asks questions fitting the chosen type, takes «Keine Ahnung» and «Alles vorschlagen lassen», and keeps the conversation across reloads.`

### Task 11: The interview's proposal becomes an entity (PR)

**Files:** Modify `app/capabilities/knowledge/web/crudDialogs.tsx` (`EntityCreateDialog` gains `source: "interview"`), `entityCreate.ts` (+ test), `interview/EntityInterview.tsx`, `ProposalCard.tsx`; Modify `app/capabilities/knowledge/e2e/test_entity_interview_e2e.py`.

**Interfaces:**
- Produces `EntityPrefill {name?, type?: EntityType, aliases?, tags?, content?, suggested: {aliases?, tags?, content?}, relations: [{target, relation_type, note?, suggested: boolean}]}`; `EntityCreateDialog` gains the props `source: "manual" | "interview"` and `prefill?: EntityPrefill`; from an interview the type is locked (a chip with a lock, no select), the suggested parts carry «vorgeschlagen», suggested relation rows the spark before the entity name.
- Produces the handover: «Als Entität speichern» opens the dialog with the prefill; `onCreated` invalidates through `useCreateEntity`, closes the session (`useCloseAssistantSession`), leaves the search parameter, selects the new entity (`select(id)`) and shows the toast «Entität angelegt · <n> Beziehungen verknüpft».
- **Review Focus 3:** a relation that matches two entities by alias shows «Mehrere Treffer — wählen» with both; rows without a resolved target are not sent and the dialog says «Nicht zugeordnete Beziehungen werden nicht angelegt.»

- [ ] **Step 1: Write the failing unit tests** (`entityCreate.test.ts`: `the prefill maps the proposal`, `the interview locks the type`, `an ambiguous alias offers both`; dialog test: `suggested parts are marked`, `unresolved rows are counted and left out`).
- [ ] **Step 2: Implement**. Run Step 1 — PASS.
- [ ] **Step 3: Extend the browser leg** `test_the_interview_ends_in_an_entity_with_relations`: … «Alles vorschlagen lassen», the marked tag and relation row, «Als Entität speichern», the prefilled dialog with the locked type and the resolved relation, «Entität speichern»; the new entity is selected in the graph with its relation; the list shows the interview under «Beendet». Run the file — PASS.
- [ ] **Step 4: Commit** — `feat(knowledge): the interview's proposal becomes an entity`; `User-visible: «Als Entität speichern» opens the create dialog prefilled from the interview, the type locked and suggested parts marked; saving puts the entity and its relations into the graph.`

### Task 12: The W9 record (PR)

`docs/design/stitch/gaps/2026-11-24-entity-interview.md` in the W8 ledger's format (the brief's draft-gap table and every finding of the PRs); the W9 index issue (`follow-up-index`) and the `docs/superpowers/follow-ups.md` row; surviving findings become child issues before merge; `ROADMAP.md` («Where it stands», Phase 1: the entity interview is live, the free chat is next) and `docs/features/INDEX.md` (`Create an entity by hand` and `Entity interview (KB-002)` → `live`). Commit `chore(docs): the W9 record — gap ledger, index, roadmap and inventory`.

### Task 13: Wave gate

`just verify`; `just test-e2e knowledge`; the whole-branch review; the PR «The lore graph interviews the author and saves the answer as an entity» ready for the owner. PR für PR held across all three.
