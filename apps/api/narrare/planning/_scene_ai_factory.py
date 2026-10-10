"""Scene AI service factory — wires SceneAIService lazily (PLAN-001 T8).

Mirrors ``get_storyboard_service`` (ADR-086 L21): the per-user PLAN
cascade is wired as a ``LazyModelResolution`` — resolved at the service's
first draft/refine use, never at construction, so request-body
validation errors surface as 422 before any routing work.

The uid-scoped novel guard and the graceful no-provider degradation live
in the service's first-use path (gate-before-resolution ordering,
Pattern M-graceful — see ``scene_ai_service.py``). Repos, registry, and
composer wire eagerly.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from narrare._app.dependencies import get_composer, get_model_registry
from narrare._app.dependencies_services import LazyModelResolution, get_model_routing_resolver
from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.planning.repository_scenes import ScenePlanRepository
from narrare.planning.scene_ai_service import SceneAIService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_scene_ai_service(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> SceneAIService:
    """Wire up SceneAIService with LAZY model routing (ADR-086 L21).

    The per-user PLAN cascade is wired as a ``LazyModelResolution`` with
    the same args the eager world resolved verbatim (intent, uid,
    novel_id — timing-only migration, RULE-18). Repos, registry, and
    composer still wire eagerly; the guards + degradation are
    first-use service policy.

    Args:
        session: DB session.
        user_id: Current user ID (string, parsed to UUID).
        novel_id: Target novel UUID.

    Returns:
        Fully wired SceneAIService (model unresolved).
    """
    from narrare_core.llm.intents import LLMIntent

    uid = uuid.UUID(user_id)

    resolver = get_model_routing_resolver(session)
    model_resolution = LazyModelResolution(lambda: resolver.resolve(LLMIntent.PLAN, uid, novel_id))

    return SceneAIService(
        ScenePlanRepository(session),
        ChapterRepository(session),
        NovelRepository(session),
        get_model_registry(),
        model_resolution=model_resolution,
        composer=get_composer(),
    )
