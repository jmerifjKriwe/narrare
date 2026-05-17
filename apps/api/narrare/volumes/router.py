"""Volume routes."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, status

from narrare._app.database import get_async_session
from narrare._app.dependencies import CurrentUserIdDep
from narrare.novels.repository import NovelRepository
from narrare.novels.service import NovelService
from narrare.volumes.repository import VolumeRepository
from narrare.volumes.schemas import (
    CreateVolumeRequest,
    ReorderVolumesRequest,
    UpdateVolumeRequest,
    VolumeResponse,
    VolumeStatsResponse,
)
from narrare.volumes.service import VolumeService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/novels/{novel_id}/volumes", tags=["volumes"])


def _get_service(session: AsyncSession = Depends(get_async_session)) -> VolumeService:
    return VolumeService(
        repo=VolumeRepository(session),
        novel_service=NovelService(
            repo=NovelRepository(session),
            volume_repo=VolumeRepository(session),
        ),
    )


@router.get("", response_model=list[VolumeResponse])
async def list_volumes(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: VolumeService = Depends(_get_service),
) -> list[VolumeResponse]:
    volumes = await service.list_volumes(novel_id, uuid.UUID(user_id))
    return [VolumeResponse.model_validate(v) for v in volumes]


@router.post("", response_model=VolumeResponse, status_code=status.HTTP_201_CREATED)
async def create_volume(
    novel_id: uuid.UUID,
    request: CreateVolumeRequest,
    user_id: CurrentUserIdDep,
    service: VolumeService = Depends(_get_service),
) -> VolumeResponse:
    volume = await service.create(novel_id, uuid.UUID(user_id), request)
    return VolumeResponse.model_validate(volume)


@router.patch("/reorder", response_model=list[VolumeResponse])
async def reorder_volumes(
    novel_id: uuid.UUID,
    request: ReorderVolumesRequest,
    user_id: CurrentUserIdDep,
    service: VolumeService = Depends(_get_service),
) -> list[VolumeResponse]:
    volumes = await service.reorder(novel_id, uuid.UUID(user_id), request.volume_ids)
    return [VolumeResponse.model_validate(v) for v in volumes]


@router.get("/{volume_id}", response_model=VolumeResponse)
async def get_volume(
    novel_id: uuid.UUID,
    volume_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: VolumeService = Depends(_get_service),
) -> VolumeResponse:
    volume = await service.get(volume_id, novel_id, uuid.UUID(user_id))
    return VolumeResponse.model_validate(volume)


@router.get("/{volume_id}/stats", response_model=VolumeStatsResponse)
async def get_volume_stats(
    novel_id: uuid.UUID,
    volume_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: VolumeService = Depends(_get_service),
) -> VolumeStatsResponse:
    stats = await service.get_stats(volume_id, novel_id, uuid.UUID(user_id))
    return VolumeStatsResponse(**stats)


@router.patch("/{volume_id}", response_model=VolumeResponse)
async def update_volume(
    novel_id: uuid.UUID,
    volume_id: uuid.UUID,
    request: UpdateVolumeRequest,
    user_id: CurrentUserIdDep,
    service: VolumeService = Depends(_get_service),
) -> VolumeResponse:
    volume = await service.update(volume_id, novel_id, uuid.UUID(user_id), request)
    return VolumeResponse.model_validate(volume)


@router.delete("/{volume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_volume(
    novel_id: uuid.UUID,
    volume_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: VolumeService = Depends(_get_service),
) -> None:
    await service.delete(volume_id, novel_id, uuid.UUID(user_id))
