"""Novel routes."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, status

from narrare._app.database import get_async_session
from narrare.novels.schemas import (
    CreateNovelRequest,
    NovelResponse,
    NovelSummaryResponse,
    UpdateNovelRequest,
)
from narrare.novels.service import NovelService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare._app.dependencies import CurrentUserIdDep

router = APIRouter(prefix="/novels", tags=["novels"])


def _get_service(session: AsyncSession = Depends(get_async_session)) -> NovelService:
    return NovelService(session)


@router.get("", response_model=list[NovelSummaryResponse])
async def list_novels(
    user_id: CurrentUserIdDep,
    service: NovelService = Depends(_get_service),
) -> list[NovelSummaryResponse]:
    """List all novels for the current user."""
    novels = await service.list_novels(uuid.UUID(user_id))
    return [NovelSummaryResponse.model_validate(n) for n in novels]


@router.post("", response_model=NovelResponse, status_code=status.HTTP_201_CREATED)
async def create_novel(
    request: CreateNovelRequest,
    user_id: CurrentUserIdDep,
    service: NovelService = Depends(_get_service),
) -> NovelResponse:
    """Create a new novel."""
    novel = await service.create(uuid.UUID(user_id), request)
    return NovelResponse.model_validate(novel)


@router.get("/{novel_id}", response_model=NovelResponse)
async def get_novel(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: NovelService = Depends(_get_service),
) -> NovelResponse:
    """Get a novel by ID."""
    novel = await service.get(novel_id, uuid.UUID(user_id))
    return NovelResponse.model_validate(novel)


@router.patch("/{novel_id}", response_model=NovelResponse)
async def update_novel(
    novel_id: uuid.UUID,
    request: UpdateNovelRequest,
    user_id: CurrentUserIdDep,
    service: NovelService = Depends(_get_service),
) -> NovelResponse:
    """Update novel metadata."""
    novel = await service.update(novel_id, uuid.UUID(user_id), request)
    return NovelResponse.model_validate(novel)


@router.delete("/{novel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_novel(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: NovelService = Depends(_get_service),
) -> None:
    """Delete a novel and all its content."""
    await service.delete(novel_id, uuid.UUID(user_id))
