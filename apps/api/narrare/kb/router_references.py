"""KB reference resolution routes — thin delegation to KBService (RULE-06)."""

import uuid

from fastapi import APIRouter, Depends, Query

from narrare._app.dependencies import CurrentUserIdDep
from narrare.kb.dependencies import get_kb_service
from narrare.kb.schemas import (
    ResolveReferencesRequest,
    ResolveReferencesResponse,
)
from narrare.kb.service import KBService

router = APIRouter(tags=["kb"])


@router.post(
    "/novels/{novel_id}/kb/resolve-references",
    response_model=ResolveReferencesResponse,
)
async def resolve_references(
    novel_id: uuid.UUID,
    request: ResolveReferencesRequest,
    user_id: CurrentUserIdDep,
    service: KBService = Depends(get_kb_service),
) -> ResolveReferencesResponse:
    """Resolve @Name mentions to KB entries."""
    return await service.resolve_references(novel_id, uuid.UUID(user_id), request.text)


@router.get("/novels/{novel_id}/kb/entries/autocomplete")
async def autocomplete_entries(
    novel_id: uuid.UUID,
    q: str,
    user_id: CurrentUserIdDep,
    service: KBService = Depends(get_kb_service),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[dict[str, str]]:
    """Auto-complete KB entry names by prefix."""
    return await service.autocomplete(novel_id, uuid.UUID(user_id), q, limit)
