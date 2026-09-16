"""Service factory for character arc — wires CharacterArcService lazily.

Follows the same pattern as ``_service_factory.py``: wires the service
with proper DI for the PLAN intent. Model routing is wired as a
``LazyModelResolution`` (ADR-086 L20) — the per-user cascade resolves on
the service's first use, never at construction, so request-body
validation errors surface as 422 before any routing work (the eager
factory resolved — and ran its uid-scoped novel guard — at wiring time).

Planning guard ruling (ADR-086 plan §3): the eager factory's uid-scoped
novel guard (``get_by_id(novel_id, uid)`` → 404, preventing resolver
auto-creation of ``project_settings`` for foreign novels) is preserved —
NOT dropped — as the service entry point's existing uid-scoped guard
(same repo, same session), which runs immediately BEFORE the first-use
resolve (gate-before-resolution ordering).

Graceful degradation (AI-optional feature) is service policy, not wiring
(Pattern M-graceful): the eager factory's wiring-time
``except ConfigurationError`` swallow moved into the service's first-use
path, which logs ``no_ai_provider_configured`` and degrades to the
preserved ``no_model_config`` outcome.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from narrare._app.dependencies import (
    get_composer,
    get_invocation_pipeline,
    get_model_registry,
)
from narrare._app.dependencies_services import LazyModelResolution, get_model_routing_resolver
from narrare.novels.repository import NovelRepository
from narrare.planning.character_arc_service import CharacterArcService
from narrare.planning.timeline_repository import TimelineEventRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_character_arc_service(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> CharacterArcService:
    """Wire up CharacterArcService with LAZY model routing (ADR-086 L20).

    The per-user PLAN cascade is wired as a ``LazyModelResolution`` with
    the same args the eager factory resolved verbatim (intent, uid,
    novel_id — timing-only migration, RULE-18). Repos, registry, composer,
    and pipeline still wire eagerly. The uid-scoped novel guard lives in
    the service's first-use path (see module docstring); graceful
    no-provider degradation is service policy there too.

    Args:
        session: DB session.
        user_id: Current user ID (string, will be parsed to UUID).
        novel_id: Target novel UUID.

    Returns:
        Fully wired CharacterArcService (model unresolved).
    """
    from narrare_core.llm.intents import LLMIntent

    uid = uuid.UUID(user_id)

    resolver = get_model_routing_resolver(session)
    model_resolution = LazyModelResolution(lambda: resolver.resolve(LLMIntent.PLAN, uid, novel_id))

    return CharacterArcService(
        novel_repo=NovelRepository(session),
        model_registry=get_model_registry(),
        model_resolution=model_resolution,
        # PromptComposer for governed character-arc system-prompt resolution
        # (RULE-02 / ADR-054 D1). Same source as the timeline-analysis factory.
        composer=get_composer(),
        event_repo=TimelineEventRepository(session),
        invocation_pipeline=get_invocation_pipeline(),
    )
