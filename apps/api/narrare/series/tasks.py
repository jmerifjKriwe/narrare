"""Band-summary auto-generation — in-process dispatch (Spec 2 Task 5, ADR-080).

When a series transitions to ``completed`` (``SeriesService.update_series``),
the service calls ``enqueue_band_summary_generation`` for each novel in the
series. That enqueuer launches ``generate_band_summary_inprocess`` via
``asyncio.create_task`` in the API process. The in-process wrapper builds its
own DB session + ``BandSummaryService`` (no request context) and calls
``service.generate(novel_id)``.

Two exported callables:

- ``enqueue_band_summary_generation(novel_id)`` — production enqueuer used by
  ``SeriesService``. Launches the in-process coroutine fire-and-forget with a
  GC-guarded reference. Injected into ``SeriesService`` via DI so unit tests
  can substitute a recording fake (RULE-07).
- ``generate_band_summary_inprocess(novel_id)`` — the in-process entry point
  that owns its own DB session and commits/rolls back.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    import uuid

logger = structlog.get_logger(__name__)

#: Strong references to in-flight band-summary coroutines, preventing the
#: garbage collector from cancelling an ``asyncio.create_task`` coroutine
#: that nothing else holds a reference to (ADR-080). Entries are removed
#: automatically via ``add_done_callback`` when the task completes.
_INFLIGHT_TASKS: set[asyncio.Task[None]] = set()


def _on_done(task: asyncio.Task[None]) -> None:
    """Done-callback for in-flight band-summary tasks.

    Removes the task from the GC-guard set and retrieves any exception so
    asyncio does not emit an un-retrieved-exception warning (IMP-1). A
    surfaced failure is logged via structlog at error level (RULE-11): the
    inner runner already logs, but this guarantees a structured error signal
    even on the retry-exhaustion / premature-failure paths.
    """
    _INFLIGHT_TASKS.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("background_task_failed", error=str(exc), exc_info=exc)


async def enqueue_band_summary_generation(novel_id: uuid.UUID) -> None:
    """Production enqueuer: launch band-summary generation in-process (ADR-080).

    Injected into ``SeriesService`` via the DI factory
    (``get_series_service``). Unit tests substitute a recording fake so they
    can assert which novels were enqueued without touching real dispatch.

    The signature ``(novel_id: uuid.UUID) -> Awaitable[None]`` matches the
    ``BandSummaryEnqueuer`` callable alias and is call-site compatible.
    """
    task = asyncio.create_task(generate_band_summary_inprocess(novel_id))
    _INFLIGHT_TASKS.add(task)
    task.add_done_callback(_on_done)
    logger.info("band_summary_dispatched", novel_id=str(novel_id))


async def generate_band_summary_inprocess(novel_id: uuid.UUID) -> None:
    """In-process entry point: generate a band summary for ``novel_id``.

    Builds its own DB session + ``BandSummaryService`` (resolving model
    routing for the novel's owner) and calls ``service.generate(novel_id)``.
    Commits on success / rolls back on failure. Fire-and-forget: the dispatch
    site does not await the result.

    Args:
        novel_id: UUID of the novel.
    """
    from narrare._app.database import get_session_factory
    from narrare.novels.repository import NovelRepository
    from narrare.series.dependencies_band_summary import build_band_summary_service

    session_factory = get_session_factory()
    async with session_factory() as session:
        # Resolve the novel's owner for per-user model routing (background
        # tasks have no request context, so the owner is read from the novel).
        novel = await NovelRepository(session).get(novel_id)
        if novel is None:
            logger.warning(
                "band_summary_task_novel_not_found",
                novel_id=str(novel_id),
            )
            return

        service = await build_band_summary_service(session, novel.user_id, novel_id)
        try:
            await service.generate(novel_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
