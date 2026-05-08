# ADR-007 — TaskIQ for Background Task Processing

> **Status:** ✅ Accepted
> **Date:** project-init+2
> **Deciders:** Architecture Agent
> **Supersedes:** ADR-007 draft (arq) — arq is in maintenance-only mode
>                 (no new features, see github.com/python-arq/arq/issues/510)

---

## Context

Narrare requires background task processing for operations that cannot
complete within an HTTP request lifecycle:

- Batch embedding generation (chapters, KB entries)
- Consistency checks across a full manuscript
- Chapter summarization
- Entity/fact extraction
- Timeline analysis

All tasks are **async throughout** — they call the LLM Gateway (async),
make DB queries (async), and interact with Redis (async).

arq was the initial choice but is in maintenance-only mode. TaskIQ is the
current actively-developed async-native alternative with direct FastAPI
integration.

---

## Decision Drivers

- All background tasks are async — need native async support
- FastAPI Dependency Injection should work in tasks (gateway, db session)
- Redis already in stack — prefer Redis-based broker
- Actively maintained — not maintenance-only
- Consistent patterns with the rest of the codebase

---

## Options Considered

### Option A — TaskIQ (chosen)

TaskIQ describes itself as "an asyncio Celery implementation — same
patterns, but more modern and flexible. Does not work for synchronous
projects."

Key feature: `taskiq-fastapi` integration allows FastAPI dependencies
(`Depends()`) to be reused directly inside task functions via `TaskiqDepends`.
This means `get_gateway`, `get_async_session`, and all other FastAPI
dependencies work identically in tasks and in route handlers.

```python
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend
from taskiq_fastapi import TaskiqDepends

broker = ListQueueBroker(settings.redis_url).with_result_backend(
    RedisAsyncResultBackend(settings.redis_url)
)

@broker.task
async def embed_chapter_task(
    chapter_id: str,
    gateway: LLMGateway = TaskiqDepends(get_gateway),
    session: AsyncSession = TaskiqDepends(get_async_session),
) -> None:
    chapter = await ChapterRepository(session).get_by_id(UUID(chapter_id))
    embeddings = await gateway.embed([chapter.content])
    await EmbeddingStore(session).save(UUID(chapter_id), embeddings)
```

**Pros:**
- Native async — no event loop wrappers
- FastAPI DI works directly in tasks — consistent codebase patterns
- Actively maintained, growing ecosystem
- Redis broker already in our stack
- PEP 612 support — full IDE autocompletion on task arguments
- Broker-agnostic — can switch to RabbitMQ/NATS if needed later
- InMemoryBroker available for tests (no Redis needed in unit tests)

**Cons:**
- Younger than Celery — less production mileage
- No built-in monitoring dashboard (mitigated: Prometheus metrics cover our needs)

### Option B — Celery with asyncio bridge

Every task requires `asyncio.run()` wrapper, defeating connection pooling.
Each task creates a new event loop, new DB connections, new HTTP sessions.
Rejected for same reasons as before — async impedance mismatch.

### Option C — arq

Maintenance-only mode since late 2024. No new features planned.
Acceptable for stability but wrong choice for a new project.
Also lacks FastAPI DI integration.

---

## Decision

**We choose TaskIQ with `taskiq-redis` broker.**

The decisive factor is FastAPI DI integration: `TaskiqDepends` means task
functions look and behave identically to route handlers. The LLM Gateway,
DB session, and all other dependencies are injected consistently.
No separate "task context" pattern needed.

---

## Implementation

### Dependencies

```toml
# pyproject.toml
"taskiq>=0.11.0",
"taskiq-redis>=0.5.0",
"taskiq-fastapi>=0.3.0",
```

### Broker definition

```python
# core/tasks/broker.py

from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend
from narrare_core.config import settings

broker = ListQueueBroker(
    settings.redis_url,
    queue_name="narrare:tasks",
).with_result_backend(
    RedisAsyncResultBackend(
        settings.redis_url,
        result_ex_time=3600,  # results expire after 1 hour
    )
)
```

### FastAPI lifespan integration

```python
# _app/lifespan.py

from contextlib import asynccontextmanager
from core.tasks.broker import broker

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    if not broker.is_worker_process:
        await broker.startup()
    yield
    # shutdown
    if not broker.is_worker_process:
        await broker.shutdown()
```

### Task definition pattern

```python
# embeddings/tasks.py

from taskiq_fastapi import TaskiqDepends
from core.tasks.broker import broker
from narrare._app.dependencies import get_gateway, get_async_session

@broker.task(retry_on_error=True, max_retries=3)
async def embed_chapter_task(
    chapter_id: str,
    gateway: LLMGateway = TaskiqDepends(get_gateway),
    session: AsyncSession = TaskiqDepends(get_async_session),
) -> None:
    """Embed a chapter's content and store in pgvector."""
    chapter = await ChapterRepository(session).get_by_id(UUID(chapter_id))
    if not chapter:
        return  # already deleted — not an error
    embeddings = await gateway.embed([chapter.content])
    await EmbeddingStore(session).upsert(UUID(chapter_id), embeddings[0])
```

### Enqueueing from services

```python
# chapters/service.py

from embeddings.tasks import embed_chapter_task

async def update_content(self, chapter_id: UUID, content: str) -> Chapter:
    chapter = await self._repo.update_content(chapter_id, content)
    # enqueue embedding update — fire and forget
    await embed_chapter_task.kiq(str(chapter_id))
    return chapter
```

### Testing with InMemoryBroker

```python
# tests/conftest.py

from taskiq import InMemoryBroker
from core.tasks.broker import broker

@pytest.fixture(autouse=True)
async def use_in_memory_broker():
    """Replace Redis broker with in-memory broker for tests."""
    broker.is_worker_process = False
    test_broker = InMemoryBroker()
    # patch broker used by tasks
    with patch("core.tasks.broker.broker", test_broker):
        await test_broker.startup()
        yield test_broker
        await test_broker.shutdown()
```

### Worker startup

```bash
# Started by: just dev-worker
taskiq worker narrare.core.tasks.broker:broker --fs-discover
```

---

## Consequences

**Positive:**
- Consistent DI patterns across routes and tasks
- Native async — shared connection pool, no new event loops per task
- InMemoryBroker makes unit tests Redis-free
- Broker-agnostic — Redis now, switchable later without changing task code

**Negative / Tradeoffs:**
- Younger ecosystem than Celery — some edge cases less documented
- No Flower-equivalent dashboard — monitoring via Prometheus + custom admin endpoint

**Changes from TECH_STACK.md:**
- Remove: `celery[redis]`, `arq`
- Add: `taskiq`, `taskiq-redis`, `taskiq-fastapi`

---

## Review Trigger

- [ ] If TaskIQ releases breaking changes in v1.0
- [ ] If monitoring requirements grow beyond Prometheus metrics
