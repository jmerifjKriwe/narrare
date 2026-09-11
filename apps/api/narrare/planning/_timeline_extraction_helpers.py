"""Timeline extraction helpers — extracted from ``timeline_extraction_service.py``
and ``timeline_analysis_service.py`` (RULE-04).

The helpers take their dependencies as explicit parameters rather than as
instance state, mirroring ``_timeline_consistency_helpers.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.planning._extracted_event_refs import build_extracted_event_create_kwargs
from narrare.planning.timeline_schemas import TimelineEventCRUDResponse
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.models import Chapter
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare.novels.repository import NovelRepository
    from narrare.planning.timeline_repository import TimelineEventRepository
    from narrare_core.agents.temporal_extraction_types import ExtractedTemporalExpression

logger = structlog.get_logger(__name__)


async def load_chapters(
    chapter_repo: ChapterRepository,
    novel_id: UUID,
    chapter_ids: list[UUID] | None,
) -> list[Chapter]:
    """Load chapters by IDs or all chapters for a novel.

    Args:
        chapter_repo: For listing chapters.
        novel_id: UUID of the novel.
        chapter_ids: Optional list of specific chapter IDs. If None,
            returns all chapters.

    Returns:
        List of matching chapters.
    """
    chapters = await chapter_repo.list_by_novel(novel_id)
    if chapter_ids is not None:
        chapter_id_set = set(chapter_ids)
        chapters = [ch for ch in chapters if ch.id in chapter_id_set]
    return chapters


async def persist_extracted_event(
    novel_repo: NovelRepository,
    event_repo: TimelineEventRepository | None,
    kb_context_provider: KBContextProviderProtocol | None,
    novel_id: UUID,
    user_id: UUID,
    extracted: ExtractedTemporalExpression,
) -> TimelineEventCRUDResponse:
    """Convert a confirmed extracted expression into a timeline event.

    Creates a TimelineEvent with source='extracted' and confidence
    from the extraction result.

    Raises:
        NotFoundError: If the novel does not exist.
        ConfigurationError: If no event_repo is available.
    """
    if event_repo is None:
        raise ConfigurationError(
            "Event repository not available for confirming extracted events.",
            code="NO_EVENT_REPO",
        )

    novel = await novel_repo.get_by_id(novel_id, user_id)
    if novel is None:
        raise NotFoundError("Novel", identifier=str(novel_id))

    event = await event_repo.create(
        **await build_extracted_event_create_kwargs(kb_context_provider, novel_id, extracted)
    )

    logger.info(
        "extracted_event_confirmed",
        event_id=str(event.id),
        novel_id=str(novel_id),
        expression=extracted.expression,
    )
    return TimelineEventCRUDResponse.model_validate(event)
