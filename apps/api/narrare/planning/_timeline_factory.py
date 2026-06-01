"""Service factory for timeline CRUD — wires TimelineService with repository.

Provides ``get_timeline_crud_service`` for CRUD operations and keeps
the existing ``get_timeline_service`` as a backward-compatible alias
that wires the analysis service (AD-5).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.planning.timeline_repository import TimelineEventRepository
from narrare.planning.timeline_service import TimelineService
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def get_timeline_crud_service(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> TimelineService:
    """Wire up TimelineService (CRUD) with repository and ownership checks.

    Validates novel existence before creating the service.

    Args:
        session: DB session.
        user_id: Current user ID (string, will be parsed to UUID).
        novel_id: Target novel UUID.

    Returns:
        Fully wired TimelineService for CRUD operations.

    Raises:
        NotFoundError: If the novel does not exist.
    """
    uid = uuid.UUID(user_id)

    # Validate novel exists
    novel_repo = NovelRepository(session)
    novel = await novel_repo.get_by_id(novel_id, uid)
    if novel is None:
        raise NotFoundError("Novel", identifier=str(novel_id))

    return TimelineService(
        event_repo=TimelineEventRepository(session),
        novel_repo=novel_repo,
        chapter_repo=ChapterRepository(session),
    )


# Backward compatibility — existing code calls get_timeline_service
# for AI analysis. Now delegates to the analysis factory.
async def get_timeline_service(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> object:
    """Backward-compatible factory — delegates to analysis service.

    Existing router code calls this for the AI analysis endpoint.
    Delegates to ``_timeline_analysis_factory``.
    """
    from narrare.planning._timeline_analysis_factory import get_timeline_analysis_service

    return await get_timeline_analysis_service(session, user_id, novel_id)
