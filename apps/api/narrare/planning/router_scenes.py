"""Scene plan routes — aggregate GET/PUT + AI draft/refine (PLAN-001).

Thin routers that delegate immediately to the scene services (RULE-06).
Included by ``router.py`` under the ``/planning`` prefix. The AI
draft/refine routes are ZERO-DB-write generators (spec §5.2): proposals
return to the client; the aggregate PUT is the single write path.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.planning._scene_ai_factory import get_scene_ai_service
from narrare.planning._service_factory import get_scene_plan_service
from narrare.planning.schemas_scenes import (
    SceneDraftRequest,
    SceneDraftResponse,
    ScenePlanAggregateResponse,
    ScenePlanSaveRequest,
    SceneRefineRequest,
    SceneRefineResponse,
)

# No tags= here: the parent planning router already applies the
# "planning" tag — re-declaring it duplicates the tag on every OpenAPI
# operation (the timeline sub-routers keep theirs: distinct tag).
router = APIRouter(prefix="/scenes")


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


@router.post("/{novel_id}/{chapter_id}/draft", response_model=SceneDraftResponse)
async def draft_scene_plans(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    request: SceneDraftRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> SceneDraftResponse:
    """Propose scenes for the chapter (AI generator, zero DB writes)."""
    service = await get_scene_ai_service(session, user_id, novel_id)
    return await service.draft(chapter_id, request, uuid.UUID(user_id), novel_id=novel_id)


@router.post("/{novel_id}/{chapter_id}/refine", response_model=SceneRefineResponse)
async def refine_scene_plan(
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    request: SceneRefineRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> SceneRefineResponse:
    """Rewrite the carried scene under the instruction (AI generator, zero writes)."""
    service = await get_scene_ai_service(session, user_id, novel_id)
    return await service.refine(chapter_id, request, uuid.UUID(user_id), novel_id=novel_id)
