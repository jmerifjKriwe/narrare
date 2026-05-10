"""Volume routes."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, status

from narrare._app.database import get_async_session
from narrare.volumes.schemas import CreateVolumeRequest, UpdateVolumeRequest, VolumeResponse
from narrare.volumes.service import VolumeService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare._app.dependencies import CurrentUserIdDep

router = APIRouter(prefix="/novels/{novel_id}/volumes", tags=["volumes"])


def _get_service(session: AsyncSession = Depends(get_async_session)) -> VolumeService:
    return VolumeService(session)


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
