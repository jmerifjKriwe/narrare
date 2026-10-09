"""Scene plan routes — aggregate GET/PUT (PLAN-001).

Thin routers that delegate immediately to ScenePlanService (RULE-06).
Included by ``router.py`` under the ``/planning`` prefix; the AI
draft/refine routes join this module in T8.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.planning._service_factory import get_scene_plan_service
from narrare.planning.schemas_scenes import ScenePlanAggregateResponse, ScenePlanSaveRequest

router = APIRouter(prefix="/scenes", tags=["planning"])


@router.get("/{novel_id}/{chapter_id}", response_model=ScenePlanAggregateResponse)
async def get_scene_plans(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> ScenePlanAggregateResponse:
    """Return the chapter's scene plans ordered by position (no auto-create)."""
    service = get_scene_plan_service(session)
    return await service.get_aggregate(chapter_id, uuid.UUID(user_id), novel_id=novel_id)


@router.put("/{novel_id}/{chapter_id}", response_model=ScenePlanAggregateResponse)
async def save_scene_plans(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    request: ScenePlanSaveRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> ScenePlanAggregateResponse:
    """Whole-aggregate diff-sync save; returns the fresh aggregate."""
    service = get_scene_plan_service(session)
    return await service.save_aggregate(chapter_id, request, uuid.UUID(user_id), novel_id=novel_id)
