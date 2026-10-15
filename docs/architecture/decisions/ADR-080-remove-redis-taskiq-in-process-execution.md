# ADR-080 — Remove Redis & TaskIQ for Single-User Deployment: In-Process Execution Boundary

> **Status:** ✅ Accepted (implementation tracked in
> `docs/architecture/implementation-plans/INFRA-remove-redis.md`)
> **Date:** 2026-08-07
> **Deciders:** Architecture Agent, Coordinator (code-verified)
> **Supersedes:** ADR-007 (TaskIQ), ADR-012 (Event-Driven Redis Pub/Sub)
> **Amends:** ADR-036 (Durable Execution Boundary) — substrate references only
> **Related:** ADR-006 (Tech Stack), ADR-029 (VM-First Setup Contract),
> ADR-031 (Observability — unaffected, OTel-only)

---

## Context

Narrare targets **single-user, self-hosted deployment** (ADR-029 VM-first
contract). The current runtime pulls in Redis plus a separate worker container
to satisfy three needs that a single-user workload does not actually have:

1. **TaskIQ broker + result backend** (`ListQueueBroker` +
   `RedisAsyncResultBackend`) in `apps/api/narrare/tasks/broker.py`.
2. **Redis Pub/Sub event bus** (`apps/api/narrare/_app/events.py::RedisEventBus`)
   plus a dormant `EventListener` (`apps/api/narrare/_app/event_listener.py` —
   `_EVENT_TASK_MAP` is empty; docstring confirms it is dormant).
3. **`RedisSessionCache`** (class in `packages/core/narrare_core/cache/redis_client.py`),
   instantiated in 5 DI factories.

Redis is currently the dependency that **demands a second always-on process**
(the TaskIQ worker) and **a second always-on datastore** (the `redis` service in
both `docker-compose.dev.yml` and `docker-compose.release.yml`). For a
single-user, local-first product this is operational overhead with no payoff:
there is no cross-process task distribution, no horizontal scaling, and no
cross-process session sharing to justify it.

### Verified facts (Coordinator audit against code, 2026-08-07)

Only **two** broker tasks are actually active (the other six registered
`@broker.task` functions are either directly invoked or stubs):

| Task | Definition | Dispatch site | Wrapper DB session |
|------|-----------|---------------|--------------------|
| `embed_source` | `apps/api/narrare/embeddings/tasks.py:153` | `apps/api/narrare/kb/embedding_hooks.py:200` (`broker.find_task("embed_source")` + `task.kiq(...)`) | own session via `get_session_factory()` (tasks.py:172) |
| `generate_band_summary` | `apps/api/narrare/series/tasks.py:56` | `enqueue_band_summary_generation` (`series/tasks.py:52`, `task.kiq(str(novel_id))`), triggered when a Series flips to `completed` | own session |

The remaining six registrations are **not** broker-dispatched:

- `wiki_generate_entity / chapter / mark_all_stale / refresh_summary` — called
  **directly** as `run_wiki_*` by `apps/api/narrare/wiki/listeners.py`
  (the `@broker.task` decorator is removable).
- `process_feedback_memory`, `run_preference_analysis` — mem0 Phase-7 stubs
  (TODO markers, not wired).

The `RedisEventBus` is **publish-to-nobody**: `apps/api/narrare/chapters/
service.py:184-213` (`_publish_content_event`) actively calls
`get_event_bus()` + `bus.publish(CHAPTER_CONTENT_UPDATED)`, but no consumer
subscribes (the listener's `_EVENT_TASK_MAP` is empty). It is dead-traffic, not
dead code — removing the bus therefore requires touching the live caller.

The read-only monitoring surface (`GET /tasks/status` in
`apps/api/narrare/tasks/router.py`, backed by `broker.get_all_tasks()` /
`broker.is_worker_process`) plus the frontend
`packages/web/components/studio/settings/BackgroundTasksPanel.tsx`
(`BrokerStatusCard`, `RegisteredTasksCard`, i18n strings) and
`tests/unit/api/tasks/test_broker.py` are downstream of the broker and must be
removed alongside it.

`redis_url` is defined with a default at
`apps/api/narrare/_app/settings_model.py:59` (not required, no failing
validation). Four dependencies live in `apps/api/pyproject.toml`:
`taskiq==0.12.4`, `taskiq-redis==1.2.3`, `taskiq-fastapi==0.5.0`
(**declared-but-unused** — never imported), `redis>=7.0.0,<9`. mem0 has **no**
Redis dependency (it uses pgvector), so removing the `redis` package is safe.

---

## Decision Drivers

- **Single-user workload** — no distributed queue, no multi-worker scaling, no
  cross-process session sharing is required.
- **Operational simplicity for self-hosters** — one process, one datastore
  (Postgres). No second always-on container to start, monitor, back up, or lose.
- **Durability is an accepted, bounded trade-off** — the affected workloads are
  idempotent embeddings + best-effort band summaries + rare triggers; none
  require cross-process durability (see ADR-036 amendment below).
- **RULE-08 layering** — Redis must stay confined to `core/cache/` (and the
  `_app/events.py` adapter). If it leaves at all, the removal must preserve a
  clean, reusable in-process abstraction in `core/`, not a writing-layer hack.
- **No half-implementations (RULE-20)** — the removal must be complete: broker,
  bus, cache, config, Docker, deps, endpoint, frontend panel, and tests in one
  coherent migration.

---

## Options Considered

### Option A — Keep Redis optional (graceful degradation already exists)

`RedisSessionCache` already degrades gracefully; keep TaskIQ/Redis in the stack
but make them optional so self-hosters can run without Redis.

**Pros:** Zero migration; existing durability retained where Redis is present.
**Cons:** The **complexity stays in the codebase** — broker wiring, lifespan
`is_worker_process` branches, event-bus publish-to-nobody, a second container in
compose, four dependencies, and a dormant `EventListener` all remain to be
understood, tested, and maintained by every future contributor. "Optional Redis"
is the worst of both worlds: full cognitive cost, partial benefit. Rejected.

### Option B — Lightweight persistent queue (saq/arq + SQLite/Postgres)

Replace TaskIQ-Redis with a small persistent queue (e.g. `saq` or `arq` backed
by SQLite or a Postgres table) to keep durability without Redis.

**Pros:** Retains cross-restart durability for the two active tasks; no Redis.
**Cons:** **YAGNI for single-user.** We would re-introduce a queue
abstraction, a worker lifecycle, result storage, and retry wiring to serve two
tasks whose inputs are already idempotent or best-effort. It is infrastructure
for a problem (multi-worker durability) the deployment model does not have.
Rejected.

### Option C — In-process execution (chosen)

Run the two active tasks via `asyncio.create_task` inside the API process.
Replace `RedisSessionCache` with a TTL-capable `InMemorySessionCache` in
`packages/core/narrare_core/cache/`. Delete the event bus, the listener, the
monitoring endpoint, the frontend panel, the Docker services, and the four
dependencies.

**Pros:** One process, one datastore; deletes a whole infrastructure category;
removes publish-to-nobody dead traffic; cache abstraction stays in the correct
layer (`core/cache/`) and is reusable.
**Cons:** Execution boundary shrinks from "Redis-queue (cross-process durable)"
to "process lifetime (in-flight tasks lost on restart)" — see Durability
Trade-off. Resource contention: tasks share the request event loop.

---

## Decision

**We choose Option C: in-process execution.**

The two active tasks run as `asyncio.create_task` coroutines inside the API
process. Each task wrapper continues to build **its own DB session** (via
`get_session_factory()`), never the request session. The caller keeps a strong
reference to the task (a module-level set) to prevent garbage collection of
in-flight coroutines. The retry logic in the standalone `run_embed_source`
(`[30.0, 120.0, 300.0]s`) is transport-independent and stays as-is — it is **not**
reimplemented via FastAPI `BackgroundTasks`, which is appropriate only for short
work, not multi-minute retry loops.

`RedisSessionCache` is replaced by a new **TTL-capable**
`InMemorySessionCache` in `packages/core/narrare_core/cache/` (RULE-08 layering:
the cache adapter home is `core/cache/`, not the writing layer). The 5 DI
factories are edited at their instantiation sites; the cache *wrapper* classes
(KBCreationSessionStore, BetaReaderCache, KBImproveCache, ConsistencyCache,
WorldbuildingCache) are unchanged. The writing-layer duplicate in
`apps/api/narrare/writing/_ws_cache.py` is consolidated onto the new core
implementation (a thin re-export), not left as a no-expiry special-case. The
WebSocket cache is **not** unbounded: it is TTL-bounded (`SessionManager`
persists every session with a 30-minute TTL, refreshed on each write),
explicitly end-session-evicted (`SessionManager.end_session()` is wired into the
WS router), and size-capped via the core cache's `max_entries` safety net (WS
singleton: `10_000`). The eviction race with an in-flight stream is benign and
resolved: the stream's final `add_message` fails with the session already
evicted, the message is dropped and logged at info
(`direction_stream_session_ended`), and the turn is always unregistered — see
ADR-052 "Explicit end_session semantics".

The `RedisEventBus`, the dormant `EventListener`, the live
`_publish_content_event` caller, the `GET /tasks/status` endpoint, the frontend
`BackgroundTasksPanel` (`BrokerStatusCard`, `RegisteredTasksCard`, i18n), and the
`taskiq*` + `redis` dependencies are removed entirely.

---

## Rationale

The root-cause chain (minimum 2× Why):

1. **Symptom:** A single-user, self-hosted product ships a Redis datastore and a
   separate worker container.
2. **Why?** TaskIQ needs a broker + result backend (Redis) and a worker process
   to consume the queue; the event bus needs a Pub/Sub substrate (Redis).
3. **Why?** The architecture (ADR-007, ADR-012) was sized for multi-consumer,
   cross-process background work — a need that does not exist when there is one
   user and one process.
4. **Design:** Collapse the execution boundary to the process. Keep only what a
   single-user workload requires: in-process async tasks, an in-process TTL
   cache, and direct (non-broker) invocation.

This is the **simplest *correct*** solution: it removes an entire infrastructure
category rather than adding a smaller queue (Option B) or carrying optional
complexity forever (Option A). The accepted cost is bounded and explicit (next
section).

---

## Durability Trade-off (explicit — the core of ADR-036)

Removing Redis moves the **execution boundary**:

| Before (ADR-007/012/036) | After (ADR-080) |
|---------------------------|------------------|
| Redis-queue, cross-process durable (task survives API restart once enqueued) | Process-lifetime (in-flight task is lost if the API process restarts) |

Per-workload impact:

- **`embed_source`** — **idempotent.** Embeddings are keyed by content hash; a
  lost in-flight task is regenerated on the next save that dirties the source.
  Acceptable.
- **`generate_band_summary`** — **best-effort + rare trigger.** Fires only when a
  Series flips to `completed`. A lost task requires a manual re-trigger (the
  manual `POST` trigger and `get_or_generate` lazy path remain). Acceptable.

Both trade-offs are **explicitly accepted** for single-user deployment. They are
not silently swallowed (RULE-11): the migration plan documents the manual
re-trigger path for band summaries. On graceful shutdown, in-flight tasks are
deliberately cancelled and awaited (`drain_inflight_tasks()` in
`apps/api/narrare/_app/inflight.py`) **before** the DB engine is disposed, and
each cancellation is logged at info level — the accepted loss is observable,
not silent.

### Resource-contention note (honest)

An in-process task shares the API event loop with request handlers. For a
single-user workload the contention is negligible, but it is **not zero**: a
300 s retry loop or a long embedding batch runs on the same loop as HTTP
requests. This is accepted because (a) the workloads are rare and (b) there is no
concurrency from other users to starve. If future multi-user load appears, the
re-introduction path (below) restores a separate worker.

---

## Consequences

**Positive:**
- One process, one datastore for self-hosters (Postgres only).
- Removes an entire dependency category (`taskiq`, `taskiq-redis`,
  `taskiq-fastapi`, `redis`) and the `taskiq-fastapi` declared-but-unused debt.
- Removes publish-to-nobody dead traffic (`_publish_content_event`).
- Cache abstraction lives in the correct layer (`core/cache/`) and is reusable
  by all four clients (RULE-12) and by tests without Redis.
- Smaller Docker footprint; no `redis`/`worker` services or volumes to operate.

**Negative / Trade-offs:**
- In-flight background tasks are lost on API restart (see Durability Trade-off).
- Band-summary generation requires a manual re-trigger if lost.
- In-process tasks share the request event loop (minor contention, single-user).
- Cross-process session sharing is no longer possible (not needed for
  single-user).

**Constraints introduced / touched:**
- RULE-08: Redis adapter locations (`core/cache/`, `_app/events.py`) are removed;
  the replacement cache is confined to `core/cache/`. If Redis is ever
  re-introduced, it goes back through `core/cache/` only.
- RULE-20: the removal must be complete — no half-removed broker, no orphaned
  endpoint, no leftover i18n strings.

### Re-introduction path (when this decision is revisited)

If Narrare moves to **multi-user or multi-worker** deployment:
re-introduce a broker + worker (TaskIQ or successor) and a Redis (or equivalent)
backend via a **new ADR that supersedes ADR-080**. The in-process task wrappers
are structured so the dispatch site (`asyncio.create_task(...)` ↔ `task.kiq(...)`)
is the single seam to swap. The TTL-capable `InMemorySessionCache` Protocol in
`core/cache/` is the seam at which a `RedisSessionCache` can be re-plugged without
touching the 5 DI factories or the cache wrapper classes.

---

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-03 | ✅ | The TTL-capable cache Protocol is defined in `core/cache/` before the Redis implementation is deleted (migration Step 2). |
| RULE-04 | ✅ | New `in_memory.py` cache is a focused module; no file grows past limits. |
| RULE-05 | ✅ | Cache module boundary stays in `core/cache/`; broker removal does not cross module ownership. |
| RULE-06 | ✅ | One responsibility per file preserved; the broker module is deleted, not repurposed. |
| RULE-07 | ✅ | Dependency direction unchanged — `core/cache/` never imports `apps/`; tasks call services/repos downward only. |
| RULE-08 | ✅ | Redis confined to `core/cache/` + `_app/events.py` today; removal keeps the replacement in `core/cache/`. No Redis use leaks to other modules. |
| RULE-09 | ✅ | New cache and task-wrapper functions are fully type-annotated; the removed `Any`-prone broker surface is gone. |
| RULE-10 | ✅ | Unit tests for the new `InMemorySessionCache` and in-process task dispatch replace `test_redis_client.py` / `test_broker.py` (migration Steps 2 & 3). |
| RULE-11 | ✅ | Lost-task behaviour is documented (manual re-trigger), not silently swallowed; in-process task exceptions are logged via structlog. |
| RULE-12 | ✅ | Service Layer remains the only public API; the removed `/tasks/status` was operational, not a client contract. |
| RULE-16 | ✅ | Removed i18n namespace/strings for `BackgroundTasksPanel` are cleaned in `request.ts` + all 3 locale JSONs. |
| RULE-17 | ✅ | The `GET /tasks/status` response type and its frontend TypeScript types are removed together (same migration step). |
| RULE-18/18b | ✅ | The `redis_url` setting is removed at its definition (`settings_model.py`); no orphaned configurable value remains. |
| RULE-20 | ✅ | Removal is complete in one migration; no half-removed broker. |
| RULE-21 | ✅ | This ADR *is* the architecture review of the removal plan; material deviations require re-review. |
| RULE-22 | ✅ | KB-embedding and wiki flows are cross-feature consumers of the task dispatch; both are verified in the migration (Step 5) before the change is declared done. |

---

## Sustainability Check

1. **Correct in 3 months?** Yes — as long as single-user self-hosted deployment
   remains the target (ADR-029). The decision removes infrastructure that the
   deployment model does not need.
2. **Hard-to-undo coupling?** None introduced — the dispatch seam and the cache
   Protocol are the documented re-introduction points. Coupling is *reduced*
   (fewer dependencies, one fewer always-on process).
3. **Simplest correct solution?** Yes — Option C removes a category rather than
   substituting a smaller queue (Option B) or carrying optional complexity
   (Option A).
4. **Design intent clear?** Yes — this ADR + the migration plan record the
   boundary shift, the per-workload durability impact, and the re-introduction
   path.

---

## Implementation Notes

- **Full migration plan:** `docs/architecture/implementation-plans/INFRA-remove-redis.md`
  (5 steps; each step ends with a green test suite).
- **Two active tasks, not one** — `embed_source` **and** `generate_band_summary`
  must both move to in-process dispatch. (The original draft overlooked
  `generate_band_summary`.)
- **Wrapper DB session** — in-process wrappers keep building their own session
  via `get_session_factory()`, never the request session.
- **GC guard** — hold a strong reference to each `asyncio.create_task` result.
- **Wiki flow caveat** — `EmbeddingHookManager` is instantiated in
  `dependencies_core.py:73` **without** `event_bus`, so
  `_publish_wiki_sync_event` could never fire. As part of the PR #157 review
  follow-up, that dead path was **removed**: `_publish_wiki_sync_event`
  (embedding_hooks.py), the `wiki.sync.requested` subscription (lifespan),
  `on_wiki_sync_requested` (wiki/listeners.py), and its test file
  (`test_embedding_hooks_wiki_sync.py`) are all gone. The remaining dormant
  subscriptions (`kb.entry.updated`, `chapter.finalized`, `wiki.prompt.changed`)
  are flagged as follow-up (WIKI-001), **not** deleted — see
  `docs/architecture/questions/INDEX.md`.
- **`check_architecture.py` impact** — this is a docs-only change at the ADR
  layer; no RULE-XX code checker scans ADR *status*. `check_adr_naming.py`
  validates only the filename shape (satisfied), and
  `doc_drift/adr_checks.py::check_adr_consistency` validates INDEX↔file coverage
  (ADR-080 is added to INDEX in this change). The Platform Specialist runs the
  full pre-commit/CI gate after the code migration to confirm green.

**ADR Implementation Completeness Gate (Gate 12):** Before marking this ADR as
"✅ Implemented", verify all items in the Gate 12 checklist at
`.opencode/context/narrare-dev/processes/quality-gates.md` *(2026-10-15 correction: that path was removed in f11eb44a and the doc anchor retired by ADR-098 — each ADR states its own completeness checklist; the gate SSOT is the ci.yml header table + CONSTRAINTS.md §6.)*. An ADR is not
implemented until it is fully wired, tested, consumed, and documented — here,
"implemented" means the migration plan is executed end-to-end and no Redis/TaskIQ
symbol remains in the runtime path.

---

## Supersedes & Amends

### ⛔ ADR-007 (TaskIQ) — Superseded

TaskIQ, the `ListQueueBroker` + `RedisAsyncResultBackend`, and the worker process
are removed. The in-process execution boundary (this ADR) replaces the
broker-based execution substrate. ADR-007's Option B/C reasoning (reject Celery,
reject arq) is retained as historical context; the new default substrate is
`asyncio.create_task`, not a queue.

### ⛔ ADR-012 (Event-Driven Redis Pub/Sub) — Superseded

The `RedisEventBus` and the dormant `EventListener` are removed. The
publish-to-nobody `_publish_content_event` traffic is deleted. Decoupled
triggering of background work is no longer mediated by a bus; the two active
tasks are dispatched directly at their call sites. If decoupled, multi-consumer
eventing is needed again (multi-user/multi-process), a new ADR reintroduces it —
not ADR-012.

### ✏️ ADR-036 (Durable Execution Boundary) — Amended (NOT superseded)

**Decision: amend, do not supersede.**

ADR-036's *policy* — "durable execution is architecture-gated; no second workflow
stack; define idempotency/persistence/retries before implementing" — is
**substrate-independent and still correct**. What changes is only the
**substrate** that future durable-execution ADRs must integrate with:

- Before: "TaskIQ is the only execution substrate" (ADR-036 Options A/B/C all
  reference TaskIQ).
- After: "the **in-process asyncio execution boundary** (ADR-080) is the current
  execution substrate." ADR-036's chosen Option A (block durable execution behind
  an architecture gate) **stands unchanged** — ADR-080 does not introduce a
  durable engine; it makes the substrate *less* durable, explicitly.

The execution *boundary* that ADR-036 exists to govern is precisely what ADR-080
relocates (cross-process Redis-queue → process-lifetime). A full supersede would
discard a still-valid gate policy and force a from-scratch rewrite; an amend that
updates the substrate references and points at ADR-080 is the correct, minimal,
lossless change. ADR-036's Review Triggers remain in force.

> **Coordinator-Review note:** This supersede-vs-amend call is the Architecture
> Specialist's firm recommendation with rationale. If the Coordinator prefers a
> full supersede of ADR-036, the amend can be converted to a supersede — but the
> durable-execution gate policy would then need to be re-stated in a successor
> ADR to avoid losing it. Recommendation stands: **amend**.

---

## Review Trigger

- [ ] When Narrare moves to **multi-user or multi-worker** deployment →
      re-introduce a broker + worker + backend via a new ADR that supersedes
      ADR-080 (re-introduction seam: dispatch site + `core/cache/` Protocol).
- [ ] When a background workload genuinely requires cross-restart durability
      (neither idempotent nor best-effort) → do not silently re-add Redis; open
      a new ADR.
- [ ] When in-process event-loop contention is observed under real use → revisit
      moving long tasks off the request loop.
