"""Service factory for timeline extraction — wires TimelineExtractionService lazily.

Follows the same pattern as ``_timeline_analysis_factory.py`` (ADR-086
L22): model routing is wired as a ``LazyModelResolution`` (ADR-086 L24)
— the per-user PLAN cascade resolves on the service's first AI use,
never at construction, so request validation errors surface as 422
before any routing work (the eager factory resolved — and ran its
uid-scoped novel guard — at wiring time).

Planning guard ruling (ADR-086 plan §3): the eager factory's uid-scoped
novel guard (``get_by_id(novel_id, uid)`` → 404, preventing resolver
auto-creation of ``project_settings`` for foreign novels) is preserved —
NOT dropped — in the service's first-use path: the ``stream_extraction``
entry point's existing uid-scoped guard runs immediately BEFORE the
first-use resolve (gate-before-resolution ordering). The extraction
service has no non-AI entry point (the REST variant delegates to the
stream), so every entry resolves at most once.

Graceful degradation is entry-point policy, not wiring (Pattern
M-graceful): the eager factory's wiring-time ``except ConfigurationError``
swallow moved into the service's first-use path, which logs
``no_ai_provider_configured`` and preserves the ``NO_AI_PROVIDER``
outcome.

Extraction is split from analysis to keep file sizes under the 300-line
limit (RULE-04).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from narrare._app.dependencies import get_composer, get_invocation_pipeline, get_model_registry
from narrare._app.dependencies_services import LazyModelResolution, get_model_routing_resolver
from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.planning.timeline_extraction_service import TimelineExtractionService
from narrare.planning.timeline_repository import TimelineEventRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_timeline_extraction_service(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> TimelineExtractionService:
    """Wire up TimelineExtractionService with LAZY model routing (ADR-086 L24).

    The per-user PLAN cascade is wired as a ``LazyModelResolution`` with
    the same args the eager factory resolved verbatim (intent, uid,
    novel_id — timing-only migration, RULE-18). Repos, registry, composer,
    and pipeline still wire eagerly. The uid-scoped novel guard and the
    graceful no-provider degradation live in the service's first-use
    path (see module docstring).

    Args:
        session: DB session.
        user_id: Current user ID (string, will be parsed to UUID).
        novel_id: Target novel UUID.

    Returns:
        Fully wired TimelineExtractionService (model unresolved).
    """
    from narrare_core.llm.intents import LLMIntent

    uid = uuid.UUID(user_id)

    resolver = get_model_routing_resolver(session)
    model_resolution = LazyModelResolution(lambda: resolver.resolve(LLMIntent.PLAN, uid, novel_id))

    return TimelineExtractionService(
        novel_repo=NovelRepository(session),
        chapter_repo=ChapterRepository(session),
        model_registry=get_model_registry(),
        model_resolution=model_resolution,
        # PromptComposer for governed timeline-extraction system-prompt
        # resolution (RULE-02 / ADR-054 D2). Same source as the
        # timeline-analysis factory.
        composer=get_composer(),
        event_repo=TimelineEventRepository(session),
        invocation_pipeline=get_invocation_pipeline(),
    )
