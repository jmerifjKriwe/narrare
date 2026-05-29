"""Wiki summary routes — thin delegation to APIWikiService (RULE-06)."""

import uuid

from fastapi import APIRouter, Body, Depends, Query

from narrare._app.dependencies import CurrentUserIdDep
from narrare.wiki.dependencies import get_wiki_service
from narrare.wiki.schemas import (
    WikiChapterSummaryResponse,
    WikiIndexResponse,
    WikiRefreshRequest,
    WikiRefreshResponse,
    WikiSummaryListResponse,
    WikiSummaryResponse,
)
from narrare.wiki.service import APIWikiService
from narrare_core.shared.errors import NotFoundError

router = APIRouter(tags=["wiki"])


@router.get("/novels/{novel_id}/wiki/summaries", response_model=WikiSummaryListResponse)
async def list_summaries(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: APIWikiService = Depends(get_wiki_service),
    entity_ids: str | None = Query(
        default=None,
        description="Comma-separated entity UUIDs to filter by",
    ),
) -> WikiSummaryListResponse:
    """List all wiki summaries for a novel."""
    parsed_ids = [uuid.UUID(e.strip()) for e in entity_ids.split(",")] if entity_ids else None
    return await service.get_summaries(novel_id, uuid.UUID(user_id), parsed_ids)


@router.get(
    "/novels/{novel_id}/wiki/summaries/{entity_id}",
    response_model=WikiSummaryResponse,
)
async def get_summary(
    novel_id: uuid.UUID,
    entity_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: APIWikiService = Depends(get_wiki_service),
) -> WikiSummaryResponse:
    """Get a single wiki summary for an entity."""
    result = await service.get_summaries(novel_id, uuid.UUID(user_id), [entity_id])
    if not result.items:
        raise NotFoundError("Wiki summary", identifier=str(entity_id))
    return result.items[0]


@router.get(
    "/novels/{novel_id}/wiki/chapters/{chapter_id}/summary",
    response_model=WikiChapterSummaryResponse,
)
async def get_chapter_summary(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: APIWikiService = Depends(get_wiki_service),
) -> WikiChapterSummaryResponse:
    """Get a chapter-level wiki summary."""
    result = await service.get_chapter_summary(chapter_id, uuid.UUID(user_id))
    if result is None:
        raise NotFoundError("Chapter wiki summary", identifier=str(chapter_id))
    return result


@router.post(
    "/novels/{novel_id}/wiki/summaries/{entity_id}/refresh",
    response_model=WikiRefreshResponse,
)
async def refresh_summary(
    novel_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: WikiRefreshRequest,
    user_id: CurrentUserIdDep,
    service: APIWikiService = Depends(get_wiki_service),
) -> WikiRefreshResponse:
    """Force-refresh a wiki summary for an entity."""
    return await service.refresh_summary(
        entity_id, novel_id, uuid.UUID(user_id), force=request.force
    )


@router.get("/novels/{novel_id}/wiki/index", response_model=WikiIndexResponse)
async def get_wiki_index(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: APIWikiService = Depends(get_wiki_service),
) -> WikiIndexResponse:
    """Get wiki overview and health status for a novel."""
    return await service.get_wiki_index(novel_id, uuid.UUID(user_id))


@router.post("/novels/{novel_id}/wiki/mark-stale")
async def mark_all_stale(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: APIWikiService = Depends(get_wiki_service),
    prompt_version: str | None = Body(default=None, embed=True),
) -> dict[str, int]:
    """Mark all wiki summaries as stale for a novel."""
    count = await service.mark_all_stale(novel_id, uuid.UUID(user_id), prompt_version)
    return {"affected_count": count}
