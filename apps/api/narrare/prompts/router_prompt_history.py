"""CR-AUFG-07-19 — Prompt History routes (thin delegation, RULE-06).

Every route immediately delegates to :class:`PromptHistoryApiService`.
Shares ``prefix="/prompts"`` and ``tags=["prompts"]`` with ``router.py``.
This router MUST be registered in ``main.py`` BEFORE ``prompts_router`` so
its ``/{prompt_id:path}/history*`` routes resolve ahead of the catch-all
``/{prompt_id:path}`` GET in ``router.py`` (path-greedy ordering).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.events.publisher import WikiEventPublisherDep
from narrare.prompts.deps import get_prompt_history_service
from narrare.prompts.schemas_prompt_history import (
    PromptHistoryClearedResponse,
    PromptHistoryListResponse,
    PromptHistoryScope,
    PromptRevisionCompareResponse,
    PromptRevisionRestoredResponse,
)

router = APIRouter(prefix="/prompts", tags=["prompts"])

# CR-AUFG-07-19: scope is resolved deterministically to PROJECT.
# Explicit user-vs-project override switching is deferred (out of scope).
_DEFAULT_SCOPE = PromptHistoryScope.PROJECT


@router.get(
    "/{prompt_id:path}/history",
    response_model=PromptHistoryListResponse,
)
async def list_history(
    prompt_id: str,
    user_id: CurrentUserIdDep,
    session: SessionDep,
    event_publisher: WikiEventPublisherDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PromptHistoryListResponse:
    """List recorded prompt override revisions, newest first."""
    service = await get_prompt_history_service(session, event_publisher)
    return await service.list_history(
        prompt_id,
        scope=_DEFAULT_SCOPE,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{prompt_id:path}/history/compare",
    response_model=PromptRevisionCompareResponse,
)
async def compare_revisions(
    prompt_id: str,
    user_id: CurrentUserIdDep,
    session: SessionDep,
    event_publisher: WikiEventPublisherDep,
    from_revision: str = Query(..., alias="from", description="Revision UUID or 'active'."),
    to_revision: str = Query(..., alias="to", description="Revision UUID or 'active'."),
) -> PromptRevisionCompareResponse:
    """Compare two revisions (or either against the active override)."""
    service = await get_prompt_history_service(session, event_publisher)
    return await service.compare_revisions(
        prompt_id,
        from_id=from_revision,
        to_id=to_revision,
        scope=_DEFAULT_SCOPE,
    )


@router.post(
    "/{prompt_id:path}/history/{revision_id}/restore",
    response_model=PromptRevisionRestoredResponse,
)
async def restore_revision(
    prompt_id: str,
    revision_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
    event_publisher: WikiEventPublisherDep,
) -> PromptRevisionRestoredResponse:
    """Append-only restore: write the active file + record a NEW revision."""
    service = await get_prompt_history_service(session, event_publisher)
    return await service.restore_revision(
        prompt_id,
        revision_id,
        actor_id=uuid.UUID(user_id),
        scope=_DEFAULT_SCOPE,
    )


@router.delete(
    "/{prompt_id:path}/history",
    response_model=PromptHistoryClearedResponse,
    status_code=status.HTTP_200_OK,
)
async def clear_history(
    prompt_id: str,
    user_id: CurrentUserIdDep,
    session: SessionDep,
    event_publisher: WikiEventPublisherDep,
) -> PromptHistoryClearedResponse:
    """Delete all history revisions; the active override file is untouched."""
    service = await get_prompt_history_service(session, event_publisher)
    return await service.clear_history(prompt_id, scope=_DEFAULT_SCOPE)
