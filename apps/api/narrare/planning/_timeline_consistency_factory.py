"""Service factory for timeline consistency — wires TimelineConsistencyService lazily.

Follows the same pattern as ``_timeline_analysis_factory.py`` (ADR-086
L22): model routing is wired as a ``LazyModelResolution`` (ADR-086 L23) —
the per-user PLAN cascade resolves on the service's first AI use, never
at construction, so request validation errors surface as 422 before any
routing work (the eager factory resolved — and ran its uid-scoped novel
guard — at wiring time).

Planning guard ruling (ADR-086 plan §3): the eager factory's uid-scoped
novel guard (``get_by_id(novel_id, uid)`` → 404, preventing resolver
auto-creation of ``project_settings`` for foreign novels) is preserved —
NOT dropped — in the service's first-use paths: the ``check_consistency``
entry point's existing uid-scoped guard runs immediately BEFORE the
first-use resolve (gate-before-resolution ordering), and the non-AI
``get_character_ages`` path keeps its guard inside ``CharacterAgeService``.

Graceful degradation is entry-point policy, not wiring (Pattern
M-graceful): the eager factory's wiring-time ``except ConfigurationError``
swallow moved into the service's first-use path, which logs
``no_ai_provider_configured`` and preserves the deterministic-only
outcome (LLM checks skip).
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
from narrare.kb.repository import KBRepository
from narrare.novels.repository import NovelRepository
from narrare.planning.character_age_service import CharacterAgeService
from narrare.planning.timeline_consistency_service import TimelineConsistencyService
from narrare.planning.timeline_repository import TimelineEventRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_timeline_consistency_service(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> TimelineConsistencyService:
    """Wire up TimelineConsistencyService with LAZY model routing (ADR-086 L23).

    The per-user PLAN cascade is wired as a ``LazyModelResolution`` with
    the same args the eager factory resolved verbatim (intent, uid,
    novel_id — timing-only migration, RULE-18). Repos, registry, composer,
    pipeline, and the CharacterAgeService wiring (KB character metadata
    reads) still wire eagerly. The uid-scoped novel guard and the graceful
    no-provider degradation live in the service's first-use paths (see
    module docstring).

    Args:
        session: DB session.
        user_id: Current user ID (string, will be parsed to UUID).
        novel_id: Target novel UUID.

    Returns:
        Fully wired TimelineConsistencyService (model unresolved).
    """
    from narrare_core.llm.intents import LLMIntent

    uid = uuid.UUID(user_id)

    novel_repo = NovelRepository(session)

    resolver = get_model_routing_resolver(session)
    model_resolution = LazyModelResolution(lambda: resolver.resolve(LLMIntent.PLAN, uid, novel_id))

    # Wire CharacterAgeService for KB character metadata reads.
    character_age_service = CharacterAgeService(
        novel_repo=novel_repo,
        kb_repo=KBRepository(session),
    )

    return TimelineConsistencyService(
        event_repo=TimelineEventRepository(session),
        novel_repo=novel_repo,
        character_age_service=character_age_service,
        model_registry=get_model_registry(),
        model_resolution=model_resolution,
        invocation_pipeline=get_invocation_pipeline(),
        composer=get_composer(),
    )
