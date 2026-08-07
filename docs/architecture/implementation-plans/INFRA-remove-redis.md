# INFRA — Remove Redis & TaskIQ: Corrected 5-Step Migration Plan

> **Type:** Implementation plan (companion to ADR-080). NOT an ADR.
> **Author:** Architecture Specialist
> **Date:** 2026-08-07
> **Branch:** `refactor/remove-redis-dependency`
> **Decision ADR:** `docs/architecture/decisions/ADR-080-remove-redis-taskiq-in-process-execution.md`
> **Status:** Ready for implementation (code phases owned by Backend/Core/Frontend/Platform specialists)
> **Related:** ADR-007 (⛔ superseded), ADR-012 (⛔ superseded), ADR-036 (✏️ amended),
> ADR-029 (VM-first), RULE-05/06/07/08/10/11/16/17/18/20/22.

This plan executes ADR-080. It corrects the original draft, which (a) overlooked
the second active task `generate_band_summary`, (b) treated the `RedisEventBus`
as "dead code" while a live caller exists, (c) forgot the `/tasks/status`
endpoint + frontend panel, (d) pointed cache edits at the wrong files, and (e)
under-specified the wiki-flow verification.

**Invariant after every step:** the full test suite (`pytest`), `mypy --strict` /
`pyright`, and the frontend typecheck/build are green. No step is "done" until
green. No `git commit` is performed by this author — the Platform Specialist
commits per step (one commit per step boundary).

**Scope guard (RULE-20):** the removal is complete only when a project-wide
search for `redis` / `Redis` / `REDIS` / `taskiq` / `TaskIQ` / `ListQueueBroker` /
`RedisAsyncResultBackend` / `RedisEventBus` / `is_worker_process` / `broker.kiq`
returns nothing in the runtime path (ADRs/Docs/history are the only allowed
matches). That check is Step 5.

---

## Execution-Boundary Summary (what changes, semantically)

| Concern | Before | After |
|--------|--------|-------|
| `embed_source` dispatch | `broker.find_task(...).kiq(...)` | `asyncio.create_task(run_embed_source(...))` (own session, GC-guarded ref) |
| `generate_band_summary` dispatch | `task.kiq(str(novel_id))` | `asyncio.create_task(run_generate_band_summary(...))` (own session) |
| Retry `[30.0,120.0,300.0]s` | inside standalone `run_embed_source` | unchanged (transport-independent) |
| Session cache | `RedisSessionCache` in `core/cache/redis_client.py` | TTL-capable `InMemorySessionCache` in `core/cache/in_memory.py` |
| Event bus | `RedisEventBus` + dormant listener + live `_publish_content_event` | removed (publish-to-nobody deleted) |
| Monitoring | `GET /tasks/status` + `BackgroundTasksPanel` | removed |
| Infra | `redis` + `worker` services, `redis_data` volume, 4 deps | removed |

---

## Step 1 — Remove the Redis Event Bus + Async Result Backend (resolve publish-to-nobody)

**Goal:** eliminate `RedisEventBus`, the dormant `EventListener`, and the live
publisher, without yet touching the broker (Step 3) or the cache (Step 2).

### Files to delete
- `apps/api/narrare/_app/events.py` (`RedisEventBus`, `get_event_bus`).
- `apps/api/narrare/_app/event_listener.py` (dormant — `_EVENT_TASK_MAP` empty,
  docstring confirms it).
- `tests/unit/api/_app/test_events.py`
- `tests/unit/api/_app/test_event_listener.py`

### Files to edit
- `apps/api/narrare/chapters/service.py:184-213` — **the live caller.** Remove
  `_publish_content_event` (or strip the `get_event_bus()` + `bus.publish(
  CHAPTER_CONTENT_UPDATED)` call). This is publish-to-nobody; deleting the call
  changes no observable behaviour. Remove the `CHAPTER_CONTENT_UPDATED` channel
  constant if it becomes unreferenced.
- `apps/api/narrare/_app/lifespan.py` — remove Event-Bus init (≈L219-226) and
  Event-Bus shutdown (≈L283-289).
- `apps/api/narrare/wiki/listeners.py` — **verify the WikiEventListener's bus
  dependency.** Per audit it invokes `run_wiki_*` directly (not via the bus); if
  it subscribes to Redis channels, refactor those handlers to direct calls now.
  The `@broker.task` *decorators* on the wiki functions are removed in Step 3
  (not here), but any `bus.subscribe(...)` / `get_event_bus()` import in this
  file must go now.
- `apps/api/narrare/kb/dependencies_core.py:73` — note: `EmbeddingHookManager` is
  instantiated **without** `event_bus`, so `_publish_wiki_sync_event` is already a
  no-op. Verify no `event_bus` argument needs cleaning here; if the constructor
  accepts an optional `event_bus`, leave the signature or simplify per the
  verify-reality check.

### Tests in this step
- Delete the two event test files above.
- Run `tests/unit/api/chapters/` and any test that imported `RedisEventBus` /
  `get_event_bus` — fix or remove those imports.

### Out of scope here
- The TaskIQ `RedisAsyncResultBackend` (it lives in `broker.py`, removed wholesale
  in Step 3). Only the event-bus half of Redis is removed in Step 1.

### Commit boundary
`test(…): green` → commit. **Suite must be green.**

---

## Step 2 — TTL-capable InMemorySessionCache in `core/` + DI rewiring

**Goal:** replace `RedisSessionCache` with a reusable, TTL-capable in-process
cache in the correct layer (RULE-08: `core/cache/`), then rewire the 5 DI
factories.

### New file
- `packages/core/narrare_core/cache/in_memory.py` — `InMemorySessionCache` with
  **real TTL expiration** (asyncio timer-based or lazy expiry-on-access; either
  is acceptable, but "TTL ignored in-memory" is not). Constructor and method
  shape mirror `RedisSessionCache` so the DI factories are a one-line swap.
  - **Mandatory module comment:** note process-locality (cache does not survive
    restart; single-user accepted) + the re-introduction path (a Redis-backed
    implementation plugs back into the same Protocol when multi-user arrives —
    see ADR-080).
- Update `packages/core/narrare_core/cache/__init__.py` to export
  `InMemorySessionCache`.
- Define the cache Protocol in `core/cache/` (RULE-03) before deleting the Redis
  implementation, so both implementations satisfy one contract.

### DI factories to edit (instantiation sites — NOT the cache wrapper classes)
| File | Line | Cache wrapper fed by the factory | TTL |
|------|------|----------------------------------|-----|
| `apps/api/narrare/kb/dependencies_session.py` | ≈42 | `KBCreationSessionStore` | 30 min |
| `apps/api/narrare/analysis/dependencies_beta_reader.py` | ≈81 | `BetaReaderCache` | 30 min |
| `apps/api/narrare/kb/dependencies_improve.py` | ≈57 | `KBImproveCache` | 10 min |
| `apps/api/narrare/kb/_consistency_deps.py` | ≈56 | `ConsistencyCache` | 10 min |
| `apps/api/narrare/kb/dependencies_worldbuilding.py` | ≈48 | `WorldbuildingCache` | 10 min |

Each: replace `RedisSessionCache(...)` with `InMemorySessionCache(...)` preserving
the TTL. Do **not** edit `KBCreationSessionStore` / `BetaReaderCache` /
`KBImproveCache` / `ConsistencyCache` / `WorldbuildingCache` themselves — they
consume the cache via the Protocol.

### Consolidate the writing-layer special-case
- `apps/api/narrare/writing/_ws_cache.py:30` — the existing non-TTL
  `InMemorySessionCache` ("TTL ignored in-memory"). Consolidate onto the new
  `core/cache/in_memory.py` implementation (RULE-08 layering + reusable, not a
  writing-layer special-case). If the WebSocket cache genuinely wants no expiry,
  construct the core implementation with `ttl=None` rather than keeping a
  duplicate class.

### Delete
- `packages/core/narrare_core/cache/redis_client.py` (`RedisSessionCache` class).
  Verify with a project grep first that nothing else references it after the DI
  edits (only the 5 factories + tests are expected consumers).

### Tests in this step
- Delete `tests/unit/core/cache/test_redis_client.py`; replace with
  `tests/unit/core/cache/test_in_memory.py` — cover get/set, TTL expiry, and
  `ttl=None` (no-expiry) behaviour.
- Add/adjust factory tests for the 5 DI sites so they assert an
  `InMemorySessionCache` is constructed with the correct TTL.

### Commit boundary
`test(…): green` → commit. **Suite must be green.**

---

## Step 3 — Move BOTH active tasks to in-process; remove broker, endpoint, panel

**Goal:** dispatch the two genuinely-active tasks via `asyncio.create_task`,
strip the broker layer entirely, and remove the monitoring endpoint + frontend
panel + i18n.

### 3a — In-process dispatch for the two active tasks

- `apps/api/narrare/embeddings/tasks.py:153` (`embed_source`):
  - Keep the standalone `run_embed_source` (it builds its **own** DB session via
    `get_session_factory()` at tasks.py:172, and owns the `[30.0,120.0,300.0]s`
    retry loop — transport-independent).
  - Remove the `embed_source_task` broker wrapper if it only exists to register
    with the broker; keep the standalone runner.
- `apps/api/narrare/kb/embedding_hooks.py:200` — replace
  `broker.find_task("embed_source")` + `task.kiq(...)` with
  `asyncio.create_task(run_embed_source(...))`. **Hold a strong reference**
  (module-level `set` of in-flight tasks, remove on completion) to avoid GC of
  the coroutine.
- `apps/api/narrare/series/tasks.py:56` (`generate_band_summary`):
  - Keep the standalone runner (own DB session).
  - In `enqueue_band_summary_generation` (`series/tasks.py:52`), replace
    `task.kiq(str(novel_id))` with `asyncio.create_task(...)` + GC-guarded ref.
- **Do NOT** use FastAPI `BackgroundTasks` for these — it is for short work, not
  multi-minute retry loops. `asyncio.create_task` is correct.

### 3b — Strip the removable `@broker.task` registrations
- `wiki_generate_entity / chapter / mark_all_stale / refresh_summary` — remove
  the `@broker.task` decorator (the WikiEventListener calls `run_wiki_*`
  directly). **Check every call path** before removing — verify reality, do not
  assume (RULE-22: wiki is a cross-feature consumer).
- `process_feedback_memory`, `run_preference_analysis`
  (`apps/api/narrare/tasks/feedback_tasks.py`) — mem0 Phase-7 stubs. Remove them
  (TODO markers, not wired). If the file becomes empty, delete it.

### 3c — Remove the broker, the monitoring endpoint, and the panel
- Delete `apps/api/narrare/tasks/broker.py` entirely.
- Delete `apps/api/narrare/tasks/router.py` (`GET /tasks/status`) and remove its
  router mount from the app/`__init__.py`.
- Remove `is_worker_process` branches in `apps/api/narrare/_app/lifespan.py`
  (broker startup ≈L203-213 incl. the `is_worker_process` check ≈L209; broker
  shutdown ≈L295-302 incl. the check ≈L299).
- Clean `apps/api/narrare/tasks/__init__.py` (remove broker/`find_task`
  re-exports).
- Frontend `packages/web/components/studio/settings/BackgroundTasksPanel.tsx` —
  remove `BrokerStatusCard` and `RegisteredTasksCard`; remove the panel from the
  settings page; remove the `/tasks/status` API client + TypeScript types.
- **RULE-16 / RULE-17:** remove the i18n strings/namespace for the panel from
  `packages/web/lib/i18n/request.ts` and the `en` / `de` / `fr` locale JSONs; run
  the i18n-namespace-registry + locale-sync checks.

### Tests in this step
- Delete `tests/unit/api/tasks/test_broker.py`
  (TestBrokerConfiguration, TestTaskRegistration, TestDirectCallability,
  TestKBHookEnqueuesViaBroker, TestTaskStatusEndpoint).
- Add in-process dispatch tests: assert `embed_source` and
  `generate_band_summary` are launched via `asyncio.create_task` from their
  dispatch sites, with own-session semantics and a GC-guarded reference.
- Add a regression test that `GET /tasks/status` no longer exists (404) so the
  endpoint cannot silently reappear.

### Commit boundary
`test(…): green` → commit. **Suite must be green.**

---

## Step 4 — Remove config, Docker services, and dependencies

**Goal:** delete the `redis_url` setting, the Redis/worker containers, and the
four packages.

### Config
- `apps/api/narrare/_app/settings_model.py:59` — remove
  `redis_url: str = "redis://localhost:6379/0"`. (Not `config.py`.) Grep for
  remaining `redis_url` / `settings.redis_url` consumers and remove them.
- `.env.example:25-27` — remove the `REDIS_URL` block.

### Docker
- `docker-compose.release.yml` — remove the `worker` service (≈L59-81), the
  `redis` service (≈L101-113), and the `redis_data` volume; remove
  `depends_on: redis` from the `narrare` service (keep `postgres`).
- `docker-compose.dev.yml` — remove the `redis` service (≈L34-44) and its volume
  (there is no worker service in dev).
- `justfile` — remove the `dev-worker` command and Redis references in the
  `e2e` / `serve` recipes.

### Dependencies
- `apps/api/pyproject.toml` — remove all four:
  `taskiq==0.12.4`, `taskiq-redis==1.2.3`, `taskiq-fastapi==0.5.0`
  (declared-but-unused), `redis>=7.0.0,<9`.
- **Verify before removing `redis`:** mem0 has **no** Redis dependency (it uses
  pgvector) — confirmed during ADR-080 audit. Re-run a dependency check (`uv tree`
  / grep) to ensure nothing else pulls `redis` transitively in a way that needs
  the pin; if a transitive consumer exists, keep only what it needs and document.
- Run `uv lock` / `uv sync` to refresh `uv.lock`.

### Tests in this step
- Smoke-test the app boots without `redis_url` and without a Redis container.
- Verify `docker compose -f docker-compose.dev.yml up` and the release compose
  start cleanly (Postgres only).

### Commit boundary
`test(…): green` + `uv.lock` refreshed → commit. **Suite must be green.**

---

## Step 5 — Verification & cleanup (RULE-20 completeness gate)

**Goal:** prove the removal is complete and no Redis/TaskIQ symbol survives in
the runtime path.

### Automated
- Full test suite (`pytest`), `mypy --strict` / `pyright`, frontend typecheck +
  build, `uv.lock` consistent.
- `scripts/check_architecture.py` + the full pre-commit gate green (including
  `check_adr_naming.py`, `doc_drift/adr_checks.py` INDEX↔file consistency,
  i18n-namespace-registry, locale-sync).
- **Project-wide search** (the completeness gate) for:
  `redis`, `Redis`, `REDIS`, `taskiq`, `TaskIQ`, `ListQueueBroker`,
  `RedisAsyncResultBackend`, `RedisEventBus`, `is_worker_process`, `broker.kiq`,
  `find_task`. The only allowed matches are ADRs / docs / git history.

### Manual (RULE-22 cross-feature verification)
- **KB-Entry create/edit → embedding generated.** Verify the in-process
  `embed_source` runs, produces embeddings, and that a lost task is regenerated
  on the next content change (content-hash idempotency).
- **Wiki flow — verify BEFORE attributing.** `EmbeddingHookManager` is
  instantiated in `dependencies_core.py:73` **without** `event_bus`, so
  `_publish_wiki_sync_event` is already a no-op; the wiki auto-regeneration over
  KB changes does not appear wired through this path today. **Manually confirm
  the wiki-summary generation path works *before* this migration and after** — do
  not credit the migration for enabling a flow it did not wire.
- **Rate limiting.** `pyrate-limiter` is in-memory only (no Redis backend init —
  accepted risk AR-05-02). Confirm rate limits still function without Redis.
- **Series → completed → band summary.** Confirm `generate_band_summary` fires
  in-process, and that a lost task can be manually re-triggered (the manual
  `POST` and `get_or_generate` lazy path).

### Doc consistency
- Confirm `ADR-007.md`, `ADR-012.md` show ⛔ Superseded-by-ADR-080.
- Confirm `ADR-036.md` carries the Amended-by-ADR-080 note (substrate references).
- Confirm `INDEX.md` reflects ADR-080 (✅) and the 007/012/036 status changes.

### Definition of Done (for this plan)
- [ ] Steps 1-5 each landed with a green suite at their boundary.
- [ ] Completeness-gate search returns zero runtime hits.
- [ ] `check_architecture.py` + full pre-commit green.
- [ ] ADR-080 marked ✅ Implemented (Gate 12) once the runtime is verified.
- [ ] No code change outside the scope described above (no scope creep, no
      workarounds — RULE-20).

---

## Risk register

| Risk | Mitigation |
|------|-----------|
| Lost `generate_band_summary` on restart with no auto-retry | Documented manual re-trigger (manual `POST` + `get_or_generate`); accepted per ADR-080 durability trade-off. |
| GC collecting an in-flight `asyncio.create_task` | Strong reference held in a module-level set, removed on completion (Step 3a). |
| Wiki flow quietly broken and credited to the migration | Mandatory before/after manual verification (Step 5); `event_bus=None` no-op noted in ADR-080. |
| `redis` removal breaks a transitive consumer | Dependency check before removal; mem0 confirmed Redis-free (pgvector). |
| In-process task starves the request loop under load | Single-user: negligible; revisit trigger in ADR-080 if contention observed. |
