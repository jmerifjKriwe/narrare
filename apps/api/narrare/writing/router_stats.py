"""Writing stats and scene routes.

Extracted from ``router.py`` for RULE-04 compliance (max 150 lines).
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for FastAPI path parameter type resolution

from fastapi import APIRouter

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.writing.deps import get_writing_service
from narrare.writing.schemas import (
    AcceptResponse,
    GenerationStatsResponse,
    SceneNextResponse,
)

router = APIRouter(prefix="/writing", tags=["writing"])


# ---------------------------------------------------------------------------
# Scene-by-scene
# ---------------------------------------------------------------------------


@router.post(
    "/generation/{request_id}/scene/next",
    response_model=SceneNextResponse,
)
async def next_scene(
    request_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> SceneNextResponse:
    """Request the next scene in scene-by-scene mode."""
    service = await get_writing_service(session, user_id)
    return await service.next_scene(request_id, user_id)


@router.post(
    "/generation/{request_id}/scene/{scene_number}/accept",
    response_model=AcceptResponse,
)
async def accept_scene(
    request_id: uuid.UUID,
    scene_number: int,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> AcceptResponse:
    """Accept a specific scene."""
    service = await get_writing_service(session, user_id)
    return await service.accept_scene(request_id, scene_number, user_id)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/novels/{novel_id}/stats", response_model=GenerationStatsResponse)
async def get_stats(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> GenerationStatsResponse:
    """Get aggregated generation statistics for a novel."""
    service = await get_writing_service(session, user_id, novel_id)
    return await service.get_stats(novel_id, user_id)
