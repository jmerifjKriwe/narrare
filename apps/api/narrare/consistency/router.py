"""Consistency API routes — thin delegation (RULE-06).

All business logic is in checker_service.py.
This router only handles HTTP request/response mapping.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep
from narrare.consistency.checker_service import ConsistencyCheckerService
from narrare.consistency.deps import get_consistency_service
from narrare.consistency.schemas import ConsistencyRequest, ConsistencyResponse

router = APIRouter(prefix="/consistency", tags=["consistency"])


@router.post(
    "/check",
    response_model=ConsistencyResponse,
    summary="Run consistency check on chapter(s)",
)
async def check_consistency(
    novel_id: uuid.UUID,
    request: ConsistencyRequest,
    user_id: CurrentUserIdDep,
    service: ConsistencyCheckerService = Depends(get_consistency_service),
) -> ConsistencyResponse:
    """Run cross-chapter and cross-entity consistency analysis.

    Checks character, timeline, world, and plot consistency across
    the requested chapters (or all chapters if none specified) and
    optionally against KB entity data.
    """
    return await service.check(
        novel_id=novel_id,
        user_id=uuid.UUID(user_id),
        request=request,
    )


@router.post(
    "/chapters/{chapter_id}/check",
    response_model=ConsistencyResponse,
    summary="Check a single chapter for consistency",
)
async def check_chapter(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    request: ConsistencyRequest,
    user_id: CurrentUserIdDep,
    service: ConsistencyCheckerService = Depends(get_consistency_service),
) -> ConsistencyResponse:
    """Run consistency check focused on a single chapter.

    Compares a single chapter against KB entity data and optionally
    other chapters in the novel. Useful for targeted checking after
    a writing session.
    """
    return await service.check_chapter(
        novel_id=novel_id,
        chapter_id=chapter_id,
        user_id=uuid.UUID(user_id),
        request=request,
    )
