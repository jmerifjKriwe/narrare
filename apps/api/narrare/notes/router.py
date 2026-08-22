# apps/api/narrare/notes/router.py
"""Notes routes — thin delegation (RULE-06: no business logic here).

Route order: the literal ``/tags`` path is declared BEFORE the ``/{note_id}``
path-parameter routes.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, status

from narrare._app.dependencies import CurrentUserIdDep
from narrare.notes.dependencies import get_note_service
from narrare.notes.schemas import (
    NoteCreateRequest,
    NoteResponse,
    NoteTagsResponse,
    NoteUpdateRequest,
)

if TYPE_CHECKING:
    from narrare.notes.service import NoteService

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("/tags", response_model=NoteTagsResponse)
async def list_tags(
    user_id: CurrentUserIdDep,
    service: NoteService = Depends(get_note_service),
    q: str | None = Query(default=None, max_length=32),
) -> NoteTagsResponse:
    """Distinct existing tags (autocomplete; optional prefix ``q``)."""
    tags = await service.list_tags(uuid.UUID(user_id), q)
    return NoteTagsResponse(tags=tags)


@router.get("", response_model=list[NoteResponse])
async def list_notes(
    user_id: CurrentUserIdDep,
    service: NoteService = Depends(get_note_service),
    note_type: str | None = Query(default=None),
    tag: str | None = Query(default=None, max_length=32),
    novel_id: uuid.UUID | None = Query(default=None),
    series_id: uuid.UUID | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[NoteResponse]:
    """List notes, default sort ``updated_at DESC`` (spec §5)."""
    notes = await service.list_notes(
        uuid.UUID(user_id),
        note_type=note_type,
        tag=tag,
        novel_id=novel_id,
        series_id=series_id,
        q=q,
        limit=limit,
        offset=offset,
    )
    return [NoteResponse.model_validate(n) for n in notes]


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    request: NoteCreateRequest,
    user_id: CurrentUserIdDep,
    service: NoteService = Depends(get_note_service),
) -> NoteResponse:
    """Create a note (quick capture and full editor both use this)."""
    note = await service.create(uuid.UUID(user_id), request)
    return NoteResponse.model_validate(note)


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: NoteService = Depends(get_note_service),
) -> NoteResponse:
    note = await service.get(note_id, uuid.UUID(user_id))
    return NoteResponse.model_validate(note)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: uuid.UUID,
    request: NoteUpdateRequest,
    user_id: CurrentUserIdDep,
    service: NoteService = Depends(get_note_service),
) -> NoteResponse:
    note = await service.update(note_id, uuid.UUID(user_id), request)
    return NoteResponse.model_validate(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: NoteService = Depends(get_note_service),
) -> None:
    await service.delete(note_id, uuid.UUID(user_id))
