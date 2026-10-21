"""HTTP surface. Parses, delegates to the service, returns; no logic here."""

from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.capabilities.writing.schemas import NovelCreate, NovelRead
from app.capabilities.writing.service import WritingService
from app.kernel.auth import current_user_id
from app.kernel.db.session import get_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/writing", tags=["writing"])


def _service(
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[UUID, Depends(current_user_id)],
) -> WritingService:
    return WritingService(session, user_id)


@router.get("/novels", response_model=list[NovelRead])
async def list_novels(service: Annotated[WritingService, Depends(_service)]) -> list[NovelRead]:
    return [NovelRead.model_validate(novel) for novel in await service.list_novels()]


@router.post("/novels", response_model=NovelRead, status_code=201)
async def create_novel(
    payload: NovelCreate, service: Annotated[WritingService, Depends(_service)]
) -> NovelRead:
    return NovelRead.model_validate(await service.create_novel(payload.title))
