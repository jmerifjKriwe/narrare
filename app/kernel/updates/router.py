"""The update check's two routes, beside the jobs route in the kernel.

The shell reads ``GET /api/updates`` and dismisses from the release-notes
dialog. ``force`` bypasses the interval, but a fresh cached answer still
serves: the hourly cache is what keeps a reload storm off the release source.
Before setup the read is the same 409 every user-owned route answers; the
service's own silent failure path means a release source outage never reaches
the client as an error.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.kernel.auth import SetupRequiredError, current_user_id
from app.kernel.db.session import get_session
from app.kernel.updates.schemas import UpdateDismiss, UpdateRead
from app.kernel.updates.service import UpdateService

router = APIRouter(prefix="/api/updates", tags=["updates"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]


def _service(session: SessionDep, user_id: UserDep) -> UpdateService:
    return UpdateService(session, user_id)


ServiceDep = Annotated[UpdateService, Depends(_service)]


@router.get("", response_model=UpdateRead)
async def get_updates(service: ServiceDep, force: bool = False) -> UpdateRead:
    """The last known release.

    ``force`` bypasses the interval; the source is still only asked when the
    in-memory cache has no fresh answer, so a reload cannot spend the quota.
    """
    try:
        return await service.read(force=force)
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None


@router.post("/dismiss", response_model=UpdateRead)
async def dismiss_update(payload: UpdateDismiss, service: ServiceDep) -> UpdateRead:
    """Stop announcing the carried version; a newer one announces again."""
    try:
        return await service.dismiss(payload.version)
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
