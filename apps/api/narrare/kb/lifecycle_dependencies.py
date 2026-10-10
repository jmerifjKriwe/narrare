"""KB lifecycle observer DI wiring (ADR-050 P1-B).

Architecture decision: use synchronous in-process service-layer observers,
not ADR-012 Redis Pub/Sub, for KB ref lifecycle notifications.

Rationale:
* Consistency boundary: Timeline rename/deprecate repairs are writes in the
  same PostgreSQL session as the KB mutation, so the request sees a coherent
  unit of work. Redis Pub/Sub would be fire-and-forget and could run after the
  request, leaving stale denormalised JSON refs longer than necessary.
* Transaction boundary: the dispatcher isolates observer failures (RULE-11) and
  does not roll back the KB mutation, matching ADR-050 Option B. Redis would not
  improve transactional guarantees because ADR-012 events are explicitly
  untyped and non-durable until TaskIQ enqueues work.
* Testability: Protocol observers can be unit-tested with in-memory repos and
  injected directly into ``KBService``; no Redis listener or worker is required.
* Module boundaries: KB depends only on Core's ``KBEntityLifecycleObserver``
  contract and this DI composition module. Consumers remain in their owning
  modules (planning/chapters/consistency), preserving RULE-05/RULE-07.

Per ADR-080, decoupled background tasks (embedding generation, wiki refresh) now
run in-process via ``asyncio.create_task`` — the ADR-012 Redis Pub/Sub bus was
removed. KB lifecycle ref repair remains request-scoped consistency work, not
background task triggering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 - FastAPI DI marker at runtime

if TYPE_CHECKING:
    from narrare.kb.lifecycle_dispatcher import KBLifecycleDispatcher


def get_kb_lifecycle_dispatcher(session: SessionDep) -> KBLifecycleDispatcher:
    """Create the request-scoped KB lifecycle dispatcher and observers."""
    from narrare.chapters.kb_lifecycle_consumer import ChapterFrontmatterRefConsumerImpl
    from narrare.chapters.repository import ChapterRepository
    from narrare.consistency.ref_integrity_sink import LoggingRefIntegrityIssueSink
    from narrare.kb.lifecycle_dispatcher import KBLifecycleDispatcher
    from narrare.planning.kb_lifecycle_consumer import (
        StoryboardRefConsumerImpl,
        TimelineRefConsumerImpl,
    )
    from narrare.planning.repository import OutlineRepository
    from narrare.planning.repository_scenes import ScenePlanRepository
    from narrare.planning.timeline_repository import TimelineEventRepository

    issue_sink = LoggingRefIntegrityIssueSink()
    return KBLifecycleDispatcher(
        observers=[
            TimelineRefConsumerImpl(
                event_repo=TimelineEventRepository(session),
                issue_sink=issue_sink,
            ),
            StoryboardRefConsumerImpl(
                outline_repo=OutlineRepository(session),
                scene_repo=ScenePlanRepository(session),
                issue_sink=issue_sink,
            ),
            ChapterFrontmatterRefConsumerImpl(
                chapter_repo=ChapterRepository(session),
                issue_sink=issue_sink,
            ),
        ]
    )
