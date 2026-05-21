"""Custom tone routes — CRUD for user-defined writing tones.

Routes are grouped under ``/settings/user/tones``. The router delegates
immediately to CustomToneService — no business logic here (RULE-06).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, status

from narrare._app.database import get_async_session
from narrare._app.dependencies import CurrentUserIdDep
from narrare.settings.custom_tone_service import CustomToneService
from narrare.settings.repository import UserSettingsRepository
from narrare.settings.schemas_tones import (
    CustomTone,
    CustomToneCreate,
    CustomToneUpdate,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["settings"])


def _get_service(session: AsyncSession = Depends(get_async_session)) -> CustomToneService:
    repo = UserSettingsRepository(session)
    return CustomToneService(repo)


@router.get(
    "/user/tones",
    response_model=list[CustomTone],
)
async def list_custom_tones(
    user_id: CurrentUserIdDep,
    service: CustomToneService = Depends(_get_service),
) -> list[CustomTone]:
    """List all custom tones for the current user."""
    return await service.list_tones(uuid.UUID(user_id))


@router.post(
    "/user/tones",
    response_model=CustomTone,
    status_code=status.HTTP_201_CREATED,
)
async def create_custom_tone(
    request: CustomToneCreate,
    user_id: CurrentUserIdDep,
    service: CustomToneService = Depends(_get_service),
) -> CustomTone:
    """Create a new custom tone."""
    return await service.create_tone(uuid.UUID(user_id), request)


@router.put(
    "/user/tones/{tone_id}",
    response_model=CustomTone,
)
async def update_custom_tone(
    tone_id: str,
    request: CustomToneUpdate,
    user_id: CurrentUserIdDep,
    service: CustomToneService = Depends(_get_service),
) -> CustomTone:
    """Update an existing custom tone."""
    return await service.update_tone(uuid.UUID(user_id), tone_id, request)


@router.delete(
    "/user/tones/{tone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_custom_tone(
    tone_id: str,
    user_id: CurrentUserIdDep,
    service: CustomToneService = Depends(_get_service),
) -> None:
    """Delete a custom tone."""
    await service.delete_tone(uuid.UUID(user_id), tone_id)
