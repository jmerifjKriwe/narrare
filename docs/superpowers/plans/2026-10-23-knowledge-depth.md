# Knowledge Depth Implementation Plan (spec §6, phase 6 — final)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The knowledge base gains depth — entities with an extraction review flow built on the first durable background jobs (`kernel/jobs` table + single worker, spec §9 D10), the Wissen dock in the workspace, and JobStatus wired against real job state.

**Architecture:** The dock bundle lands FIRST (binding phase-5 ruling) so no new E2E pins the old `dock=none` URLs: the workspace learns the dock set from a generated registry derived from the existing `dockRoutes` convention, per-dock tabs/matching replace the hard-wired chat surface, and `dock` becomes omit-at-default. Then `kernel/jobs` (table + one worker claiming `FOR UPDATE SKIP LOCKED`, started in the API lifespan, behind an interface) with chapter-entity extraction as its first job kind: extraction writes `EntitySuggestion` rows, the review queue in the Wissen dock consumes them through `ProposalCard`, accept creates `Entity` rows. Entities are novel-scoped (extraction is chapter-based); documents/upload and semantic search keep their standalone homes — in this phase the dock's search box filters entity names client-side and reaches no passage.

**Tech Stack:** as phases 1–5 · RAC `GridList`/`ComboBox` enter `web/ui/` with their first consumers · TanStack Query `refetchInterval` polls running jobs.

**Spec:** `docs/superpowers/specs/2026-10-22-frontend-design.md` — §5.6 (ProposalCard/JobStatus), §5.9, §5.11, §6 phase 6, §9 D10/D14.
**Base:** branch `frontend-foundation` @ 0550b0b2. Execute on a new branch `knowledge-depth` from it.

## Global Constraints

- English in code, comments, tests, commits. User-visible text only through `i18n/{en,de,fr}.json`, all three together; German du-form.
- Capabilities never import capabilities (kernel contracts/models are the shared domain; the shell is reached via `@shell/*`; the generated table is the only composition point). RAC only in `web/ui/`.
- Route contracts (phase 4/5, binding): tolerant `validateSearch`; function-form search writes; `dockRoutes` factory convention (`(parent) => route`, `as const`); dock open state = child-route match; **this plan's Task 1 changes the `dock` output to omit-at-default — the only sanctioned `validateSearch` change.**
- Ghost props `proposal`/`onProposalResolve` are the integration seam for any editor offer; the proposal bus stays pure pub-sub (stateless — no resurrection).
- No side effect in the request path beyond its transaction (D14): extraction enqueues a job row in the request transaction and returns; the LLM call happens in the worker. `kernel/jobs` per D10: table (status, user, progress, error, retry count), one worker, `FOR UPDATE SKIP LOCKED`, worker behind an interface.
- E2E = real UI, real API, real Postgres; fake only at the LLM/embeddings boundary (the fake TextProvider answers extraction prompts with deterministic JSON via the `SOURCE_PREFIX` convention); `assert_accessible(page)` ends every flow. Editor component tests only for the editor layer; backend tests ride the real DB fixtures.
- No new scripts/gates; generator extensions only (`scripts/generate_capabilities.py`); generated files carry the DO-NOT-EDIT header; `just generate` stays drift-free.
- Conventional commits; `feat`/`fix` carry a real `User-visible:` line; `--no-verify` forbidden; `just` recipes only.

## Review Focus

1. **A job row survives its request and its API restart** (the durability D10 exists for): enqueue → `stack.stop_api()`/`start_api()` → worker still completes the extraction. Pinned by Task 3's E2E.
2. **Review decisions are durable and exclusive** — accept creates exactly one Entity and consumes the suggestion; discard consumes without creating; a second accept of the same suggestion is refused. Pinned by Task 3 backend tests + Task 4 E2E.
3. **The dock registry cannot drift from the dock routes** — every generated dock entry corresponds to a mounted `dockRoutes` child and vice versa (generate drift-free, plus the tab for each entry navigates to its route in E2E). Pinned by Task 1.
4. **Job polling stops** — `refetchInterval` while `queued/running`, off on `done/failed`; a finished job's panel shows the result, not a spinner. Pinned by Task 4 E2E (result visible, no polling class).
5. **The fake provider's extraction answers are parseable or loudly not** — a malformed model answer must fail the job (visible in JobStatus), never crash the worker or write half-entities. Pinned by Task 3 unit tests (malformed answer → `failed` job, zero Entity rows).

---

### Task 1: Dock bundle — the workspace learns its docks

**Files:**
- Modify: `scripts/generate_capabilities.py` (emit `web/lib/generated/docks.ts`: one entry per discovered `dockRoutes` export — `{ id: <capability>, path: "/novels/$id/<dock-path>", titleKey: "<capability>.dockTitle" }`, sorted; symmetric duplicate-host `SystemExit` guard now fires regardless of dock existence; substring-scan caveat comment — carry)
- Create (generated): `web/lib/generated/docks.ts`
- Modify: `app/capabilities/writing/web/routes.tsx` (`dock` output omit-at-default: emitted only when `"chat"`; `rail`/`focus` byte-stable)
- Modify: `app/capabilities/writing/web/NovelPage.tsx` (tab surface renders from the generated registry: per-dock label `t(entry.titleKey)`, per-dock pressed state via `useChildMatches` filtered to the entry's route id, toggle navigates to the entry's path or to `/novels/$id` on close; aside `aria-label` per active dock)
- Modify: `i18n/{en,de,fr}.json` (`chat.dockTitle` — chat owns its dock name now; `workspace.dockClose` stays)
- Test: update existing dock E2E in `app/capabilities/chat/e2e/test_chat_e2e.py` to the new URLs (no `dock=none` anywhere); add: with TWO docks mocked? No — the knowledge dock lands in Task 4; per-dock matching is provable with one dock by asserting the tab's pressed state comes from the registry entry's route id (and the child-match filter). Registry↔route correspondence asserted via `just generate` drift + typecheck of `to=` literals.

**Interfaces:**
- Produces: `web/lib/generated/docks.ts` exporting `docks: readonly { id: string; path: string; titleKey: string }[]` — Task 4's Wissen dock appears here by adding `dockRoutes`, zero generator changes.
- Produces: the tab-surface pattern Task 4 extends (second entry renders a second tab with no NovelPage change beyond what already renders from the registry).

- [ ] **Step 1: Failing E2E first** — the dock tests red against the new expectations (URLs without `dock=none`, pressed state, chat label from `chat.dockTitle`).
- [ ] **Step 2: Implement** registry + emit + tab surface + omit-at-default + duplicate-host guard + catalogs.
- [ ] **Step 3: Green** — full suite, typecheck, build, `just generate` drift-free (run twice, diff clean).
- [ ] **Step 4: Commit**

```
feat(web): the workspace learns its docks from a generated registry

Per-dock tabs, matching and labels replace the hard-wired chat surface;
dock defaults leave the URL again (omit-at-default like focus). The
registry derives from the dockRoutes convention — the knowledge dock
will appear by existing, not by generator work.

User-visible: dock tabs come from the docks that exist, each named by
its capability; a closed dock leaves a clean URL.
```

### Task 2: `kernel/jobs` — the durable background lane

**Files:**
- Create: `app/kernel/jobs/__init__.py`, `app/kernel/jobs/models.py` (Job: UserOwned + id, kind: str, status: queued/running/done/failed, progress: int 0–100 nullable, error: Text nullable, retry_count: int default 0, payload: JSON, result: JSON nullable, created_at/updated_at timezone-aware)
- Create: `app/kernel/jobs/worker.py` (protocol `JobHandler = Callable[[AsyncSession, Job], Awaitable[dict]]`; `Worker` claims `FOR UPDATE SKIP LOCKED` one row at a time, marks running→done/failed, captures handler errors into `error`, `retry_count` increments on failure with one re-run allowed then `failed`; behind the interface, swappable)
- Create: `app/kernel/jobs/runtime.py` (start/stop for the API lifespan: one asyncio task looping claim→execute with a small idle sleep; started from `app/api/main.py` lifespan — Modify)
- Test: `app/kernel/tests/test_jobs.py` (real DB fixtures like kernel's existing tests): enqueue in a transaction; claim excludes other claimers (two concurrent claims → one wins); handler failure → retry once → failed with error text; done carries result; restart simulation: enqueue, new Worker instance (fresh "process") completes it.

**Interfaces:**
- Produces: `enqueue(session, user_id, kind, payload) -> Job`; `Worker(session_factory, handlers: dict[str, JobHandler])` with `async def run_once() -> bool`; `handlers` registry filled by capabilities at app assembly (Task 3 registers `"extract-entities"` — assembly point: `app/api/main.py` imports capability handler factories through the mounted routers' packages? No — capabilities register via a small `app/kernel/jobs/handlers` hook the api app discovers by convention: `app/capabilities/*/jobs.py` exporting `handlers`. Convention like routers, no registry file.)

- [ ] **Step 1: Failing kernel tests** (claim exclusivity, retry, restart-completes). Run red.
- [ ] **Step 2: Implement** models + worker + runtime + lifespan wiring + capability `jobs.py` discovery convention (empty for now).
- [ ] **Step 3: Green** — kernel tests, full `just test`, E2E untouched and green (worker idles with zero jobs).
- [ ] **Step 4: Commit**

```
feat(kernel): the jobs table and its single worker

Spec D10 arrives with its first consumer next: a jobs table (status,
user, progress, error, retry count) and one worker claiming rows with
FOR UPDATE SKIP LOCKED, started in the API lifespan behind an
interface. Durable side effects leave the request path (D14).

User-visible: none yet — the lane exists, extraction boards it next.
```

### Task 3: Extraction — the first job, entities, and the review contract

**Files:**
- Modify: `app/kernel/contracts/models.py` (Entity: UserOwned + id, novel_id FK, name String(200), kind String(40) — `character|place|thing`, description Text nullable, created_at; EntitySuggestion: UserOwned + id, novel_id FK, chapter_id FK, name, kind, description nullable, status `pending|accepted|discarded`, created_at)
- Create: `app/capabilities/knowledge/jobs.py` (`handlers = {"extract-entities": extract_entities}` — reads the chapter through the kernel Chapter model (scoped), prompts the TextProvider (`SOURCE_PREFIX = "extraction"` — Modify/Create `app/capabilities/knowledge/prompts.py`), parses a JSON array of `{name, kind, description}`, writes one `EntitySuggestion` row per item, returns `{"suggestions": n}`; malformed answer → raise → job `failed`, zero rows)
- Modify: `app/kernel/llm/fake.py` (recognizes the `extraction` source prefix and answers with deterministic JSON — the boundary fake stays honest: names derived from the prompt text)
- Modify: `app/capabilities/knowledge/{repository,service,schemas,router}.py` — endpoints: `POST /api/writing-bridge?` NO: knowledge owns extraction but chapters are writing's domain — routing decision: the endpoint lives on the WRITING router path? Capability boundary: the API path is `/api/knowledge/…`; extraction input is a chapter id. The knowledge service reads chapters via kernel models (allowed); endpoint `POST /api/knowledge/extraction/{novel_id}` with body `{chapter_id}` → enqueues job (request transaction) → `202 {job_id}`. Plus `GET /api/knowledge/novels/{novel_id}/entities`, `GET …/suggestions?status=pending`, `POST …/suggestions/{id}/accept` (creates Entity, marks accepted, one-transaction exclusivity), `POST …/suggestions/{id}/discard`.
- Test: `app/capabilities/knowledge/tests/test_extraction.py`, `test_entities.py` (accept/discard exclusivity: second accept → 409 or 404-consumed, assert exactly-once); e2e durability test in `app/capabilities/knowledge/e2e/test_extraction_e2e.py` (drive via API first — UI lands in Task 4 — but through the real stack: enqueue via the running API, stop/start API, job completes, suggestions queryable).

**Interfaces:**
- Consumes: Task 2's `enqueue`/`Worker` + the `jobs.py` convention.
- Produces: the client surface Task 4 consumes — `EntityRead {id, novel_id, name, kind, description}`, `SuggestionRead {…, status}`, `JobRead {id, kind, status, progress, error, result}` (job status endpoint: `GET /api/jobs/{id}` — kernel-owned generic route mounted by the api app, any capability's UI can poll).

- [ ] **Step 1: Failing backend tests** (extraction happy path with fake provider; malformed answer → failed job, zero suggestions; accept-exactly-once; discard-creates-nothing). Run red.
- [ ] **Step 2: Implement** models (`just db-reset`), prompts + fake branch, jobs.py handler, service/repo/router + `GET /api/jobs/{id}` (kernel router), `just generate` (client refresh).
- [ ] **Step 3: Green** — capability tests, full `just test`, E2E durability test green (real restart), existing suites green.
- [ ] **Step 4: Commit**

```
feat(knowledge): entity extraction as the first durable job

Extraction reads a chapter, prompts the provider, and files one
suggestion per proposed entity — in the worker, not the request
(D14). Review is exactly-once: accept creates the entity and consumes
the suggestion in one transaction; discard consumes without creating.
A malformed model answer fails the job loudly, writing nothing.

User-visible: none yet — the entities surface boards next.
```

### Task 4: The Wissen dock — entities, review, JobStatus

**Files:**
- Create: `app/capabilities/knowledge/web/dock.tsx` + `dockRoutes` (path `"wissen"` → appears in the generated registry with zero generator changes), `EntitiesPanel.tsx` (searchable entity list + detail; RAC enters `web/ui/`: `web/ui/GridList.tsx`, `web/ui/ComboBox.tsx` — first consumers, token-styled), `ExtractionPanel.tsx` (trigger „Dieses Kapitel durchsuchen" for the active chapter → `202` → JobStatus poll → queue)
- Create: `web/ui/JobStatus.tsx` (`JobStatus({ job })` — spinner/progress/error/result per status; assert-friendly states)
- Modify: `web/lib/query.ts` (`useJobQuery(id)` with `refetchInterval` while queued/running; `useEntitiesQuery(novelId)`, `useSuggestionsQuery(novelId)`, mutations with invalidation)
- Carries (files open here): `web/ui/TextField.tsx` gains `isInvalid`/`validationMessage` (RAC native) and `NovelsPage` marks empty Titel on failed submit (the recorded deliberate-drop becomes implemented — one key `novels.titleRequired` ×3 catalogs); ProposalCard discard-path assertion added in this task's E2E (accept AND discard both pinned).
- Test: `app/capabilities/knowledge/e2e/test_knowledge_dock_e2e.py` — in the workspace: Wissen tab (from registry) → extraction on the typed chapter → JobStatus visible → suggestions appear as ProposalCards → accept one → entity in list (and in the chapter-scoped search); discard another → gone, no entity; JobStatus shows result not spinner; second accept of a consumed suggestion refused (if reachable via UI timing — else backend test covers, UI asserts queue empties). Every test ends `assert_accessible(page)`.

**Interfaces:**
- Consumes: Task 1's registry (`docks` entry appears automatically), Task 3's client surface, phase-5 ProposalCard/ghost seam (NOT used here — review acts on suggestions, not editor offers; the editor-offer path stays chat's).
- Produces: `web/ui/{GridList,ComboBox,JobStatus}.tsx` primitives (phase-6+ surfaces reuse).

- [ ] **Step 1: Failing E2E** (the full review flow above). Run red.
- [ ] **Step 2: Implement** dock + panels + primitives + queries + carries.
- [ ] **Step 3: Green** — full suite, typecheck, build, generate drift-free.
- [ ] **Step 4: Commit**

```
feat(knowledge): the Wissen dock — entities, review, job status

The knowledge dock mounts through the same factory convention (the
registry picked it up untouched), entities list and search beside the
text, extraction runs as a durable job with a live status, and the
review queue is ProposalCards: accept files the entity, discard
clears it. GridList, ComboBox and JobStatus enter the ui layer.

User-visible: your novel's knowledge lives beside your text — pull
entities out of a chapter and keep what fits, in two clicks.
```

---

## Self-review notes

Spec coverage: §6 phase 6 — entities (T3/T4), extraction review (T3/T4, ProposalCard consumed + discard pinned), `kernel/jobs` + worker (T2, D10 contract incl. progress/error/retry), JobStatus wired against real state (T4). §5.9's "documents and search integrated as the dock tab": not in this phase — search and documents remain standalone-only; the dock's box filters entity names client-side, nothing in the dock calls the search endpoint; the documents/upload LIST stays standalone as planned (upload is a rare bulk action with its standalone flow and E2E). Deliberate deviation, recorded (search-out-of-dock): the dock's search box reaches entities only — a passage-reaching dock search is the follow-up for the next knowledge-surface work. §5.11 axe + keyboard already in the harness; the new dock flows carry both. Dock bundle FIRST as ruled; no new dock E2E before it (T1 rewrites the existing ones). Manual entity CRUD deliberately out (creation is extraction-review; editing returns with the graph/notes surfaces, per spec §11's "on merit"). Not folded (no natural file-opening task — owners recorded for the next writing-editor work): forwarded-Esc `code` field, ghost-swap "replaced" announcement, stream-error announce copy, ChatPanel abort-on-unmount. Proportion: four tasks, the kernel lane provable before any UI boards it.
