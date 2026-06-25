---
id: INFRA-007
title: "Background Tasks"
status: stable
area: infra
mvp: false

ui_tooltip: "Monitor the asynchronous background processing infrastructure."
ui_help_short: |
  Monitor the background processing infrastructure (embedding generation and knowledge-graph summary tasks).
  These tasks run asynchronously so you can continue writing without waiting.
ui_help_long: |
  Narrare processes several tasks in the background using TaskIQ workers, including embedding generation,
  knowledge-graph (wiki) summary generation, and feedback/preference memory processing.
  The Background Tasks panel shows the broker status and the list of registered tasks so you can confirm
  the background infrastructure is running.
ui_available_in: ["editor", "cli", "mcp"]

service: apps/api/narrare/tasks/
contract: apps/api/narrare/tasks/broker.py
router: apps/api/narrare/tasks/router.py
prompt: ""
requires: []
---

# [INFRA-007] — Background Tasks

## What it does

Runs expensive operations (embedding generation, knowledge-graph summary
generation, feedback/preference memory processing) asynchronously so they do
not block the writing experience, and exposes read-only monitoring of the
background task infrastructure.

## Why it exists

Operations like embedding generation and wiki summary generation take time and
should not interrupt the creative flow. Background Tasks lets Narrare offload
these heavy operations to a worker process while giving the writer visibility
that the infrastructure is up.

## How it works (User perspective)

1. The writer performs an action (e.g., saves a knowledge-base entry).
2. Narrare offloads processing to a background worker.
3. The writer opens the **Background Tasks** panel (Settings) to see the broker
   status (running / stopped) and the list of registered background tasks,
   confirming the infrastructure is operating.

> The panel is currently **read-only monitoring**. Per-task queue depth,
   coverage statistics, and manual retry are not exposed — TaskIQ's
   `ListQueueBroker` provides no queue-depth API. See *Roadmap* below.

## How it works (Technical)

**Broker:** `apps/api/narrare/tasks/broker.py`
**Task registry:** `apps/api/narrare/tasks/__init__.py`
**Monitoring API:** `apps/api/narrare/tasks/router.py` → `GET /tasks/status`
**Streaming:** no

Narrare uses **TaskIQ** (ADR-007 / Q-004) — not Celery — as its background task
framework. The shared broker is a `ListQueueBroker` over Redis with a matching
`RedisAsyncResultBackend`; both transports use the application `REDIS_URL`.

### Implemented architecture

- **Broker & result backend** — `ListQueueBroker(url=REDIS_URL)` combined with
  `RedisAsyncResultBackend(redis_url=REDIS_URL)`. The broker is started by the
  application lifespan (`_app/lifespan.py`) in the API process and is
  self-managed inside the dedicated worker process (`broker.is_worker_process`).
- **7 registered tasks** (registered at import time via
  `narrare.tasks.__init__`, which imports the embeddings and wiki task modules):
  | Task name | Module | Purpose |
  |-----------|--------|---------|
  | `embed_source` | `embeddings/tasks.py` | Generate / refresh an embedding (idempotent via content hash) |
  | `wiki_generate_entity` | `wiki/tasks.py` | Generate an entity wiki summary |
  | `wiki_generate_chapter` | `wiki/tasks.py` | Generate a chapter wiki summary |
  | `wiki_mark_all_stale` | `wiki/tasks.py` | Invalidate summaries after a prompt change |
  | `wiki_refresh_summary` | `wiki/tasks.py` | Force-refresh a single entity summary |
  | `process_feedback_memory` | `tasks/__init__.py` | Forward feedback to mem0 (stub) |
  | `run_preference_analysis` | `tasks/__init__.py` | Run preference analysis (stub) |
- **Serialization boundary** — TaskIQ serializes arguments across processes, so
  task wrappers take JSON-serializable args (UUIDs as strings) and build their
  own database session / wiki-service factory inside the task body. Each task
  has a matching standalone `run_*` function for direct in-process invocation.
- **KB embedding hooks** — `kb/embedding_hooks.py` enqueues `embed_source`
  through the broker when KB content changes, instead of embedding inline.
- **Event listener dispatch** — `_app/event_listener.py` subscribes to Redis
  Pub/Sub event channels and routes events to registered tasks via
  `_EVENT_TASK_MAP` (`KB_ENTRY_UPDATED → embed_source`). The listener is
  currently dormant infrastructure (not started by the lifespan); when wired,
  the dispatcher must adapt each event payload to its target task's signature.
- **Monitoring API** — `GET /tasks/status` returns the broker process role
  (`is_worker_process` / `broker_started`), the registered task count, and the
  sorted list of registered `task_name` labels.

### Worker process

The taskiq worker is the process that actually executes queued tasks. In
development it runs locally:

```bash
just dev-worker   # taskiq worker narrare.tasks.broker:broker
```

In the self-hosted release deployment (`docker-compose.release.yml`) a
`worker` service reuses the `narrare` image with a taskiq entrypoint and the
same database / Redis access as the application:

```yaml
worker:
  image: ${NARRARE_IMAGE:-ghcr.io/jmerifjkriwe/narrare}:${NARRARE_VERSION:-latest}
  entrypoint: ["/app/.venv/bin/taskiq", "worker", "narrare.tasks.broker:broker"]
  env_file: [.env]
  depends_on: [postgres, redis]
```

## Constraints & Edge Cases

- Tasks retry with exponential backoff (30s / 120s / 300s, max 3 retries).
  Content-hash / freshness checks make embedding and wiki tasks idempotent.
- Large imports may heavily load the worker.
- No queue-depth or coverage metrics are exposed (ListQueueBroker limitation).

## Related Features

- [INFRA-004](../infra/INFRA-004-embedding-store.md) — Embeddings generated via background tasks
- [KB-008](../kb/KB-008-knowledge-graph.md) — Knowledge graph summary generation handled in the background

## Roadmap

- Wire the event listener into the application lifespan and add per-event
  payload adaptation so `KB_ENTRY_UPDATED` actually enqueues `embed_source`.
- Implement the `process_feedback_memory` / `run_preference_analysis` bodies
  (currently stubs).
- Queue-depth / coverage metrics and manual retry UI (requires a richer broker).

## Status & History

- `2026-05-19` — Added to registry
- `2026-06-25` — Implemented: TaskIQ broker (Redis transport + result backend),
  7 registered tasks, KB embedding-hook enqueueing, event-listener task map,
  read-only monitoring API + Settings panel, release Docker worker. Status → stable.
