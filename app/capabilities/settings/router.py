"""HTTP surface for the settings. Parses, delegates, returns; no logic here."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.settings.schemas import SettingsRead, SettingsUpdate
from app.capabilities.settings.service import SettingsService
from app.kernel.auth import SetupRequiredError, current_user_id
from app.kernel.db.session import get_session

router = APIRouter(prefix="/api/settings", tags=["settings"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]


def _service(session: SessionDep, user_id: UserDep) -> SettingsService:
    return SettingsService(session, user_id)


ServiceDep = Annotated[SettingsService, Depends(_service)]


@router.get("", response_model=SettingsRead)
async def get_settings(service: ServiceDep) -> SettingsRead:
    return SettingsRead(locale=await service.read_locale())


@router.patch("", response_model=SettingsRead)
async def update_settings(payload: SettingsUpdate, service: ServiceDep) -> SettingsRead:
    try:
        locale = await service.write_locale(payload.locale)
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    return SettingsRead(locale=locale)
