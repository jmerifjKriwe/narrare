"""Band-summary auto-trigger logic (Spec 2 Task 5 — RULE-04 split from service.py).

Extracted so ``service.py`` stays under the 300-line hard limit. Contains the
``BandSummaryEnqueuer`` type alias and ``enqueue_band_summaries`` — the
best-effort loop that enqueues a generation task for each novel in a series
when the series transitions to ``completed``.

Pure logic: takes a list of novels + the enqueuer callable. No DB access
(repo queries stay in ``SeriesService``) — RULE-06.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from narrare_core.series.schemas import NovelRow

logger = structlog.get_logger(__name__)

#: Callable that enqueues a band-summary generation task for a single novel.
#: The production implementation (``series.tasks.enqueue_band_summary_generation``)
#: finds the registered TaskIQ task on the broker and calls ``.kiq()``; unit
#: tests inject a recording fake.
BandSummaryEnqueuer = Callable[[uuid.UUID], Awaitable[None]]


async def enqueue_band_summaries(
    novels: list[NovelRow],
    enqueue: BandSummaryEnqueuer,
    *,
    series_id: uuid.UUID,
) -> None:
    """Enqueue band-summary generation for every novel in the list.

    Called by ``SeriesService.update_series`` when the status transitions to
    ``completed``. Individual enqueue failures are logged but do not abort the
    loop — the status transition has already succeeded and each band summary
    is independent (RULE-11 graceful degradation).
    """
    for novel in novels:
        try:
            await enqueue(novel.id)
        except Exception:
            logger.error(
                "band_summary_enqueue_failed",
                novel_id=str(novel.id),
                series_id=str(series_id),
                exc_info=True,
            )
