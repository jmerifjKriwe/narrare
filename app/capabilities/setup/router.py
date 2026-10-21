"""HTTP surface for first run. Parses, delegates, returns."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.setup.schemas import SetupRequest, SetupResult, SetupStatus
from app.capabilities.setup.service import AlreadySetUpError, SetupService
from app.kernel.db.session import get_session

router = APIRouter(prefix="/api/setup", tags=["setup"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _service(session: SessionDep) -> SetupService:
    return SetupService(session)


ServiceDep = Annotated[SetupService, Depends(_service)]


@router.get("/status", response_model=SetupStatus)
async def status(service: ServiceDep) -> SetupStatus:
    return SetupStatus(complete=await service.is_complete())


@router.post("", response_model=SetupResult, status_code=201)
async def complete(payload: SetupRequest, service: ServiceDep) -> SetupResult:
    try:
        novel = await service.complete(payload.novel_title)
    except AlreadySetUpError:
        raise HTTPException(status_code=409, detail="setup already complete") from None
    return SetupResult(novel_id=novel.id, novel_title=novel.title)
