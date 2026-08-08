---
id: INFRA-007
title: "Background Tasks"
status: stable
area: infra
mvp: false

ui_tooltip: "Embeddings and summaries generate behind the scenes while you write."
ui_help_short: |
  Embedding and band-summary generation run as in-process async tasks so they
  never slow down writing. There is no dedicated task panel.
ui_help_long: |
  Narrare runs a few slow operations — embedding generation for knowledge-base
  sources and band-summary generation for a completed series — as in-process
  async tasks, so they never block the writing experience. Per ADR-080 these
  tasks run inside the API process (asyncio), not on a separate worker; there
  is no broker, queue, or monitoring panel.
ui_available_in: []

service: ""
contract: ""
router: ""
prompt: ""
requires: []
---

# [INFRA-007] — Background Tasks

## What it does

Runs a small number of slow operations — embedding generation
(`embed_source`) and band-summary generation (`generate_band_summary`) — as
**in-process asynchronous tasks** so they do not block the writing experience.

## Why it exists

Operations like embedding generation take time and should not interrupt the
creative flow. Background Tasks offloads these operations onto the API
process's async event loop (never the request handler), giving the writer
uninterrupted typing while the work completes asynchronously.

> **Architectural change (ADR-080, 2026-08-07).** This feature previously ran
> on a TaskIQ broker + dedicated Redis-backed worker process with a read-only
> monitoring API (`GET /tasks/status`) and a Settings panel. That substrate is
> **⛔ superseded by ADR-080** for single-user, self-hosted deployment: the
> broker, worker, monitoring endpoint, frontend panel, and the
> `taskiq`/`redis` dependencies were removed. The two active tasks now run
> in-process via `asyncio.create_task`. See
> [ADR-080](../../architecture/decisions/ADR-080-remove-redis-taskiq-in-process-execution.md)
> (supersedes ADR-007 / ADR-012; amends ADR-036).

## How it works (User perspective)

There is **no dedicated user-facing UI** for background tasks — the Settings
panel was removed in ADR-080. The writer simply experiences responsive
editing: when they save a knowledge-base entry, the embedding is generated in
the background; when a series flips to `completed`, a band summary is
generated. If the API process restarts while a task is in flight, idempotent
workloads regenerate on the next triggering save, and band summaries can be
re-triggered manually (see *Constraints & Edge Cases* and the Durability
Trade-off in ADR-080).

## How it works (Technical)

**Dispatch pattern:** `asyncio.create_task` inside the API process (ADR-080).
No broker, no worker process, no queue.
**Package home:** `apps/api/narrare/tasks/` — retained for import-path
stability per ADR-080; it no longer owns a shared broker (see its `__init__.py`).
**Streaming:** no

### Active in-process tasks

| Task (wrapper) | Definition | Dispatch site | Trigger |
|-----------------|-----------|---------------|---------|
| `run_embed_source_inprocess` | `apps/api/narrare/embeddings/tasks.py` | `apps/api/narrare/kb/embedding_hooks.py` (`asyncio.create_task`) | KB source content changes |
| `generate_band_summary_inprocess` | `apps/api/narrare/series/tasks.py` | `apps/api/narrare/series/tasks.py` (`enqueue_band_summary_generation` → `asyncio.create_task`) | A Series flips to `completed` (via the series auto-trigger) |

> Wiki summary generation (`apps/api/narrare/wiki/tasks.py`) is **not** a
> background task in this sense — it is invoked **directly** (awaited) by
> `apps/api/narrare/wiki/listeners.py`, not dispatched via
> `asyncio.create_task`.

### Execution-boundary guarantees

- **Own DB session** — each in-process wrapper builds its own session via
  `get_session_factory()`, never the request session.
- **GC guard** — the caller holds a strong reference to each
  `asyncio.create_task` result (a module-level container) so the runtime does
  not garbage-collect in-flight coroutines.
- **Retry** — the transport-independent retry schedule in the standalone
  `run_embed_source` (`[30.0, 120.0, 300.0]s`, max 3) is retained as-is. It is
  **not** reimplemented via FastAPI `BackgroundTasks`, which is appropriate
  only for short work, not multi-minute retry loops.
- **Content-hash / freshness** — embedding and band-summary checks make the
  workloads idempotent, so a lost in-flight task is regenerated on the next
  triggering save.

### ⛔ Removed in ADR-080 (historical)

These surfaces are **obsolete**; listed only to document what changed:

- ~~TaskIQ `ListQueueBroker` + `RedisAsyncResultBackend`~~ —
  `apps/api/narrare/tasks/broker.py` **deleted**.
- ~~Read-only monitoring API `GET /tasks/status`~~ —
  `apps/api/narrare/tasks/router.py` **deleted**.
- ~~Dedicated worker process~~ — the `dev-worker` recipe and the Docker
  `worker` service **removed**.
- ~~Event-listener task map / Redis Pub/Sub dispatch~~ — ADR-012 superseded;
  the dormant `EventListener` and the publish-to-nobody `_publish_content_event`
  caller were removed.
- ~~Frontend `BackgroundTasksPanel`~~ (`BrokerStatusCard`,
  `RegisteredTasksCard`, i18n strings) **deleted**.

## Constraints & Edge Cases

- **In-flight tasks are lost on API restart.** `embed_source` is idempotent
  (regenerated on the next dirty save); `generate_band_summary` is best-effort
  and rare (manual re-trigger available). Both trade-offs are explicitly
  accepted in ADR-080 (Durability Trade-off).
- **Shared event loop.** In-process tasks share the API request event loop.
  For a single-user workload the contention is negligible but not zero — a
  long embedding batch or a 300 s retry loop runs on the same loop as HTTP
  requests.
- **No queue-depth / coverage metrics.** There is no broker to query, so no
  per-task queue depth, coverage statistics, or manual retry are exposed.

## Related Features

- [INFRA-004](../infra/INFRA-004-embedding-store.md) — Embeddings generated via the `embed_source` background task
- [KB-008](../kb/KB-008-knowledge-graph.md) — Knowledge-graph summary generation (wiki summaries are invoked directly, not as background tasks)

## Roadmap

- If Narrare moves to **multi-user / multi-worker** deployment → re-introduce a
  broker + worker via a **new ADR that supersedes ADR-080**. The dispatch site
  (`asyncio.create_task(...)` ↔ `task.kiq(...)`) is the single swap seam; the
  TTL-capable `InMemorySessionCache` Protocol in `core/cache/` is the cache
  re-plug point.
- Per-task queue depth / coverage metrics and a manual-retry UI would require a
  richer (re-introduced) broker — out of scope for single-user deployment.

## Status & History

- `2026-05-19` — Added to registry.
- `2026-06-25` — Implemented: TaskIQ broker (Redis transport + result backend),
  7 registered tasks, KB embedding-hook enqueueing, event-listener task map,
  read-only monitoring API + Settings panel, release Docker worker. Status →
  `stable`.
- `2026-08-07` — **ADR-080 superseded the broker-based implementation.**
  Broker, worker, `GET /tasks/status`, frontend panel, event bus, and the
  `taskiq`/`redis` dependencies removed. The two active tasks (`embed_source`,
  `generate_band_summary`) now run in-process via `asyncio.create_task`.
  Implementation substrate changed; feature remains `stable`.
