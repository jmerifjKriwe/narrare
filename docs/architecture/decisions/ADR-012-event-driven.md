# ADR-012 — Event-Driven Architecture

> **Status:** ✅ Accepted
> **Date:** 2026-05-12
> **Deciders:** Architecture Agent
> **Supersedes:** `embeddings_dirty` flag pattern

---

## Context

Current pattern for triggering background work: **polling-based flags**.

```python
chapter.embeddings_dirty = True
# ... some process checks this flag periodically
```

Problems: implicit contracts (flag setter/checker coupled by convention),
no extensibility (adding reactions requires modifying the polling loop),
no observability (can't trace from "content changed" to "embedding regenerated").

Phase 5 adds many background tasks: embeddings, consistency checks,
summarization, fact extraction, timeline analysis. These should trigger
automatically on content changes, not via polling.

Redis (in stack) supports Pub/Sub. TaskIQ (in stack, ADR-007) is the task
execution layer.

---

## Decision Drivers

- Decouple event emission from event processing
- Use existing infrastructure (Redis + TaskIQ)
- Events publishable from any service method
- Processing: async, retriable, observable
- Extensible — new reactions without modifying existing code

---

## Options Considered

### Option A — Redis Pub/Sub + TaskIQ (chosen)

Services publish to Redis channels. Listeners subscribe and enqueue TaskIQ
tasks. Emission (request handlers) is separated from processing (workers).

**Pros:** Uses existing Redis; TaskIQ handles retriable execution (ADR-007);
clean decoupling; extensible; in-memory fallback for tests.
**Cons:** Fire-and-forget — no persistence if no subscriber connected
(mitigated: TaskIQ tasks are durable once enqueued).

### Option B — Redis Streams

Persistent, consumer-group-based message queuing.

**Pros:** Messages persist until acknowledged; consumer groups for load balancing.
**Cons:** More complex API; overkill for our scale; duplicates TaskIQ durability.

### Option C — Dedicated message broker (RabbitMQ / NATS)

**Pros:** Battle-tested; rich routing.
**Cons:** New infra dependency; additional operational burden; not justified at
our scale.

### Option D — In-process events only (asyncio.Event / signals)

**Pros:** Zero infrastructure; fastest delivery.
**Cons:** Doesn't survive restarts; no cross-process communication; tight coupling.

---

## Decision

**We choose Redis Pub/Sub + TaskIQ.**

We don't need durable event storage — we need decoupled task triggering.
Pub/Sub connects "what happened" to "what to do about it" using infrastructure
we already operate. TaskIQ handles durability and execution.

---

## Rationale

When chapter content changes: (1) chapter service publishes
`chapter.content.updated`, (2) embedding listener enqueues
`embed_chapter_task`, (3) TaskIQ executes (retriable, async, with DI).
Redis Pub/Sub is the lightest mechanism connecting step 1→2.
If replay or audit trails are needed later, specific channels can migrate
to Redis Streams without changing the publisher API.

---

## Consequences

**Positive:** Services decoupled — chapter service doesn't import embedding
tasks; extensible — add new subscribers without touching publishers; observable
— events flow through known bus; testable — mockable EventBus.
**Negative:** Fire-and-forget — event lost if no subscriber (mitigated:
subscribers always running in prod); event schema untyped (may need typed
classes later).

**Constraints introduced:**
- Services must not import task modules directly — use events
- Channel names: `{domain}.{entity}.{action}`

---

## Implementation Notes

### Event bus

```python
# core/events/bus.py
class EventBus:
    async def publish(self, channel: str, payload: dict) -> None:
        """Publish event to Redis channel."""

    async def subscribe(self, channel: str, handler: Callable) -> None:
        """Subscribe to Redis channel with handler."""
```

### Event types (initial set)

| Channel | Subscriber → Task |
|---------|-------------------|
| `chapter.content.updated` | `embed_chapter_task` |
| `chapter.created` | `kb_consistency_check_task` |
| `chapter.deleted` | `kb_cleanup_task` |
| `kb.entry.updated` | `embed_kb_entry_task` |
| `novel.settings.changed` | `novel_reanalysis_task` |

### Publishing from services

```python
# chapters/service.py
async def update_content(self, chapter_id: UUID, content: str) -> Chapter:
    chapter = await self._repo.update_content(chapter_id, content)
    await self._events.publish("chapter.content.updated", {
        "chapter_id": str(chapter_id),
        "novel_id": str(chapter.novel_id),
    })
    return chapter
```

### Listener registration

```python
# core/events/listeners.py
async def register_listeners(bus: EventBus) -> None:
    @bus.subscribe("chapter.content.updated")
    async def on_content_updated(payload: dict) -> None:
        await embed_chapter_task.kiq(payload["chapter_id"])
```

### Testing: InMemoryEventBus records events without Redis.

---

## Review Trigger

- [ ] If event replay is needed (migration path: Redis Streams for specific channels)
- [ ] If event volume exceeds Pub/Sub throughput (unlikely at our scale)
- [ ] If cross-service events span multiple deployments (may need broker)
