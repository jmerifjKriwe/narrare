"""KB entry routes — entry CRUD and search endpoints.

Thin delegation to KBService.  No business logic here (RULE-06).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from narrare._app.dependencies import CurrentUserIdDep
from narrare.kb.dependencies import get_kb_service
from narrare.kb.schemas import (
    KBEntryCreate,
    KBEntryListResponse,
    KBEntryResponse,
    KBEntryUpdate,
)
from narrare.kb.service import KBService

router = APIRouter(tags=["kb"])


@router.post(
    "/novels/{novel_id}/kb/entries",
    response_model=KBEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_entry(
    novel_id: uuid.UUID,
    request: KBEntryCreate,
    user_id: CurrentUserIdDep,
    service: KBService = Depends(get_kb_service),
) -> KBEntryResponse:
    """Create a new KB entry."""
    entry = await service.create(novel_id, uuid.UUID(user_id), request)
    return KBEntryResponse.model_validate(entry)


@router.get(
    "/novels/{novel_id}/kb/entries",
    response_model=KBEntryListResponse,
)
async def list_entries(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: KBService = Depends(get_kb_service),
    entity_type: str | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> KBEntryListResponse:
    """List KB entries for a novel."""
    entries, total = await service.list_entries(
        novel_id,
        uuid.UUID(user_id),
        entity_type=entity_type,
        tags=tags,
        page=page,
        page_size=page_size,
    )
    return KBEntryListResponse(
        items=[KBEntryResponse.model_validate(e) for e in entries],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/novels/{novel_id}/kb/entries/search",
    response_model=KBEntryListResponse,
)
async def search_entries(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: KBService = Depends(get_kb_service),
    q: str = Query(min_length=1),
    entity_type: str | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> KBEntryListResponse:
    """Search KB entries by text."""
    entries, total = await service.search(
        novel_id,
        uuid.UUID(user_id),
        q,
        entity_type=entity_type,
        tags=tags,
        page=page,
        page_size=page_size,
    )
    return KBEntryListResponse(
        items=[KBEntryResponse.model_validate(e) for e in entries],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/novels/{novel_id}/kb/entries/{entry_id}",
    response_model=KBEntryResponse,
)
async def get_entry(
    novel_id: uuid.UUID,
    entry_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: KBService = Depends(get_kb_service),
) -> KBEntryResponse:
    """Get a single KB entry."""
    entry = await service.get(novel_id, entry_id, uuid.UUID(user_id))
    return KBEntryResponse.model_validate(entry)


@router.patch(
    "/novels/{novel_id}/kb/entries/{entry_id}",
    response_model=KBEntryResponse,
)
async def update_entry(
    novel_id: uuid.UUID,
    entry_id: uuid.UUID,
    request: KBEntryUpdate,
    user_id: CurrentUserIdDep,
    service: KBService = Depends(get_kb_service),
) -> KBEntryResponse:
    """Update a KB entry."""
    entry = await service.update(novel_id, entry_id, uuid.UUID(user_id), request)
    return KBEntryResponse.model_validate(entry)


@router.delete(
    "/novels/{novel_id}/kb/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_entry(
    novel_id: uuid.UUID,
    entry_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: KBService = Depends(get_kb_service),
) -> None:
    """Delete a KB entry."""
    await service.delete(novel_id, entry_id, uuid.UUID(user_id))
