"""HTTP surface. Parses, delegates to the service, returns; no logic here."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.writing.schemas import (
    ChapterCreate,
    ChapterRead,
    ChapterUpdate,
    NovelCreate,
    NovelRead,
)
from app.capabilities.writing.service import NotFoundError, WritingService
from app.kernel.auth import current_user_id
from app.kernel.db.session import get_session

router = APIRouter(prefix="/api/writing", tags=["writing"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]


def _service(session: SessionDep, user_id: UserDep) -> WritingService:
    return WritingService(session, user_id)


ServiceDep = Annotated[WritingService, Depends(_service)]


@router.get("/novels", response_model=list[NovelRead])
async def list_novels(service: ServiceDep) -> list[NovelRead]:
    return [NovelRead.model_validate(novel) for novel in await service.list_novels()]


@router.post("/novels", response_model=NovelRead, status_code=201)
async def create_novel(payload: NovelCreate, service: ServiceDep) -> NovelRead:
    return NovelRead.model_validate(await service.create_novel(payload.title))


@router.get("/novels/{novel_id}/chapters", response_model=list[ChapterRead])
async def list_chapters(novel_id: UUID, service: ServiceDep) -> list[ChapterRead]:
    try:
        chapters = await service.list_chapters(novel_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    return [ChapterRead.model_validate(chapter) for chapter in chapters]


@router.post("/novels/{novel_id}/chapters", response_model=ChapterRead, status_code=201)
async def create_chapter(
    novel_id: UUID, payload: ChapterCreate, service: ServiceDep
) -> ChapterRead:
    try:
        chapter = await service.create_chapter(novel_id, payload.title)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    return ChapterRead.model_validate(chapter)


@router.get("/chapters/{chapter_id}", response_model=ChapterRead)
async def get_chapter(chapter_id: UUID, service: ServiceDep) -> ChapterRead:
    try:
        chapter = await service.get_chapter(chapter_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    return ChapterRead.model_validate(chapter)


@router.put("/chapters/{chapter_id}", response_model=ChapterRead)
async def update_chapter(
    chapter_id: UUID, payload: ChapterUpdate, service: ServiceDep
) -> ChapterRead:
    try:
        chapter = await service.update_chapter(chapter_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    return ChapterRead.model_validate(chapter)
