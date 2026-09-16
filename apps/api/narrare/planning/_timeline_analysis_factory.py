"""Service factory for timeline analysis — wires TimelineAnalysisService lazily.

Follows the same pattern as ``_character_arc_factory.py`` (ADR-086 L20):
model routing is wired as a ``LazyModelResolution`` (ADR-086 L22) — the
per-user PLAN cascade resolves on the service's first AI use, never at
construction, so request validation errors surface as 422 before any
routing work (the eager factory resolved — and ran its uid-scoped novel
guard — at wiring time).

Planning guard ruling (ADR-086 plan §3): the eager factory's uid-scoped
novel guard (``get_by_id(novel_id, uid)`` → 404, preventing resolver
auto-creation of ``project_settings`` for foreign novels) is preserved —
NOT dropped — in the service's first-use paths: the ``generate_timeline``
entry point's existing uid-scoped guard runs immediately BEFORE the
first-use resolve (gate-before-resolution ordering), and the non-AI
``confirm_extracted_event`` path keeps its guard inside
``persist_extracted_event``.

Graceful degradation is entry-point policy, not wiring (Pattern
M-graceful): the eager factory's wiring-time ``except ConfigurationError``
swallow moved into the service's first-use path, which logs
``no_ai_provider_configured`` and preserves the ``NO_AI_PROVIDER``
outcome.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from narrare._app.dependencies import get_composer, get_invocation_pipeline, get_model_registry
from narrare._app.dependencies_services import LazyModelResolution, get_model_routing_resolver
from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.planning.timeline_analysis_service import TimelineAnalysisService
from narrare.planning.timeline_repository import TimelineEventRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_timeline_analysis_service(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> TimelineAnalysisService:
    """Wire up TimelineAnalysisService with LAZY model routing (ADR-086 L22).

    The per-user PLAN cascade is wired as a ``LazyModelResolution`` with
    the same args the eager factory resolved verbatim (intent, uid,
    novel_id — timing-only migration, RULE-18). Repos, registry, composer,
    KB-context provider (ADR-067), and pipeline still wire eagerly. The
    uid-scoped novel guard and the graceful no-provider degradation live
    in the service's first-use paths (see module docstring).

    Args:
        session: DB session.
        user_id: Current user ID (string, will be parsed to UUID).
        novel_id: Target novel UUID.

    Returns:
        Fully wired TimelineAnalysisService (model unresolved).
    """
    from narrare_core.llm.intents import LLMIntent

    uid = uuid.UUID(user_id)

    # Canonical KB-context provider (ADR-067): supplies kb_characters/
    # kb_locations/kb_factions/kb_relationships, rendered through the ADR-050
    # envelope with provenance (FIND-017). Degrades gracefully (RULE-11).
    from narrare.kb._context_provider import KBContextProvider
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository

    kb_context_provider = KBContextProvider(
        kb_repo=KBRepository(session),
        relationship_repo=RelationshipRepository(session),
    )

    resolver = get_model_routing_resolver(session)
    model_resolution = LazyModelResolution(lambda: resolver.resolve(LLMIntent.PLAN, uid, novel_id))

    return TimelineAnalysisService(
        novel_repo=NovelRepository(session),
        chapter_repo=ChapterRepository(session),
        model_registry=get_model_registry(),
        model_resolution=model_resolution,
        # PromptComposer for governed timeline system-prompt resolution
        # (RULE-02 / ADR-049 D9). Same source as the KB consistency factory.
        composer=get_composer(),
        event_repo=TimelineEventRepository(session),
        kb_context_provider=kb_context_provider,
        invocation_pipeline=get_invocation_pipeline(),
    )
