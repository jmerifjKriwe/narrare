"""The one jobs endpoint: any capability's UI polls its own job here.

Kernel machinery, not a capability's surface — every job-producing capability
would otherwise need the same read route, so it lives with the lane it reports
on and the api app mounts it beside the capability routers (spec §9 D10).

The route answers the caller's own rows only: another user's job id is a 404,
not a 403, the way every scoped read in this product answers.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.kernel.auth import current_user_id
from app.kernel.db.session import get_session
from app.kernel.jobs.models import Job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]


class JobRead(BaseModel):
    """What a UI polls: the row's state, not its payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    status: str
    progress: int | None
    error: str | None
    result: dict[str, object] | None


@router.get("/{job_id}", response_model=JobRead)
async def get_job(job_id: UUID, session: SessionDep, user_id: UserDep) -> JobRead:
    """Return an owned job's state; absent and other users' jobs both raise HTTP 404."""
    job = await session.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobRead.model_validate(job)
