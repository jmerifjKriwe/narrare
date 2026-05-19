"""KB relationship routes — relationship CRUD and inverse suggestions.

Thin delegation to RelationshipService.  No business logic here (RULE-06).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from narrare._app.dependencies import CurrentUserIdDep
from narrare.kb.dependencies import get_rel_service
from narrare.kb.relationship_service import RelationshipService
from narrare.kb.schemas import KBRelationshipCreate, KBRelationshipResponse

router = APIRouter(tags=["kb"])


@router.post(
    "/novels/{novel_id}/kb/relationships",
    response_model=KBRelationshipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_relationship(
    novel_id: uuid.UUID,
    request: KBRelationshipCreate,
    user_id: CurrentUserIdDep,
    service: RelationshipService = Depends(get_rel_service),
) -> KBRelationshipResponse:
    """Create a new relationship between KB entries."""
    rel = await service.create(novel_id, uuid.UUID(user_id), request)
    return KBRelationshipResponse.model_validate(rel)


@router.get(
    "/novels/{novel_id}/kb/entries/{entry_id}/relationships",
    response_model=list[KBRelationshipResponse],
)
async def list_relationships(
    novel_id: uuid.UUID,
    entry_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: RelationshipService = Depends(get_rel_service),
    direction: str | None = Query(default=None),
) -> list[KBRelationshipResponse]:
    """List relationships for a KB entry."""
    rels = await service.list_for_entry(novel_id, entry_id, uuid.UUID(user_id), direction=direction)
    return [KBRelationshipResponse.model_validate(r) for r in rels]


@router.delete(
    "/novels/{novel_id}/kb/relationships/{rel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_relationship(
    novel_id: uuid.UUID,
    rel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: RelationshipService = Depends(get_rel_service),
) -> None:
    """Delete a relationship."""
    await service.delete(novel_id, rel_id, uuid.UUID(user_id))


@router.get(
    "/novels/{novel_id}/kb/relationships/inverse-suggestion",
)
async def get_inverse_suggestion(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: RelationshipService = Depends(get_rel_service),
    rel_type: str = Query(),
) -> dict[str, str | None]:
    """Get the suggested inverse relationship type."""
    inverse = service.get_inverse_suggestion(rel_type)
    return {"rel_type": rel_type, "inverse": inverse}
