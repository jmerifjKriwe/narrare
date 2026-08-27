"""KB suggestions routes — thin delegation to KBSuggestService (RULE-06)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from narrare._app.dependencies import CurrentUserIdDep
from narrare.kb.dependencies import get_kb_suggest_service
from narrare.kb.schemas import KBSuggestionResponse
from narrare.kb.suggest_service import DEFAULT_KB_SUGGEST_MAX_RESULTS, KBSuggestService

router = APIRouter(tags=["kb"])


@router.get(
    "/novels/{novel_id}/kb/suggestions/{chapter_id}",
    response_model=list[KBSuggestionResponse],
)
async def get_suggestions(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    max_results: int = Query(default=DEFAULT_KB_SUGGEST_MAX_RESULTS, ge=1, le=100),
    service: KBSuggestService = Depends(get_kb_suggest_service),
) -> list[KBSuggestionResponse]:
    """Get proactive KB suggestions for a chapter."""
    return await service.get_suggestions(
        chapter_id=chapter_id,
        novel_id=novel_id,
        user_id=uuid.UUID(user_id),
        max_results=max_results,
    )
