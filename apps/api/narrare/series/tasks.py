"""TaskIQ background task for band-summary auto-generation (Spec 2 Task 5).

When a series transitions to ``completed`` (``SeriesService.update_series``),
the service enqueues ``generate_band_summary_task`` for each novel in the
series. The task builds its own DB session + ``BandSummaryService`` (no
request context) and calls ``service.generate(novel_id)``.

Two exported callables:

- ``enqueue_band_summary_generation(novel_id)`` — production enqueuer used by
  ``SeriesService`` (finds the registered task on the broker and calls
  ``.kiq()``). Injected into ``SeriesService`` via DI so unit tests can
  substitute a recording fake (RULE-07).
- ``generate_band_summary_task(novel_id: str)`` — the ``@broker.task`` wrapper
  that runs in the worker process. Takes a string (JSON-serialisable) because
  TaskIQ serialises arguments across processes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.tasks.broker import broker

if TYPE_CHECKING:
    import uuid

logger = structlog.get_logger(__name__)


async def enqueue_band_summary_generation(novel_id: uuid.UUID) -> None:
    """Production enqueuer: find the task on the broker and call ``.kiq()``.

    Injected into ``SeriesService`` via the DI factory
    (``get_series_service``). Unit tests substitute a recording fake so they
    can assert which novels were enqueued without touching the broker.

    Graceful when the task is not registered (e.g. in a stripped-down test
    environment): logs a warning and returns — the series update still
    succeeds (RULE-11: background generation is best-effort, never blocks the
    status transition).
    """
    task = broker.find_task("generate_band_summary")
    if task is None:
        logger.warning(
            "band_summary_task_not_registered",
            novel_id=str(novel_id),
        )
        return
    await task.kiq(str(novel_id))
    logger.info("band_summary_enqueued", novel_id=str(novel_id))


@broker.task(task_name="generate_band_summary", max_retries=3)
async def generate_band_summary_task(novel_id: str) -> None:
    """TaskIQ wrapper: generate a band summary for ``novel_id`` in the worker.

    Builds its own DB session + ``BandSummaryService`` (resolving model
    routing for the novel's owner) and calls ``service.generate(novel_id)``.
    Commits on success / rolls back on failure, mirroring the
    ``embed_source_task`` pattern.

    Args:
        novel_id: UUID of the novel, as a JSON-serialisable string.
    """
    import uuid

    from narrare._app.database import get_session_factory
    from narrare.novels.repository import NovelRepository
    from narrare.series.dependencies import build_band_summary_service

    nid = uuid.UUID(novel_id)
    session_factory = get_session_factory()
    async with session_factory() as session:
        # Resolve the novel's owner for per-user model routing (background
        # tasks have no request context, so the owner is read from the novel).
        novel = await NovelRepository(session).get(nid)
        if novel is None:
            logger.warning(
                "band_summary_task_novel_not_found",
                novel_id=novel_id,
            )
            return

        service = await build_band_summary_service(session, novel.user_id, nid)
        try:
            await service.generate(nid)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
