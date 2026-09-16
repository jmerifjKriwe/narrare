"""Service factory for planning router — wires StoryboardService lazily.

Extracted from router.py to respect the 150-line file size limit (RULE-04).

Model routing is wired as a ``LazyModelResolution`` (ADR-086 L21) — the
per-user PLAN cascade resolves on the service's first remap use, never
at construction, so request-body validation errors surface as 422
before any routing work (the eager factory resolved — and ran its
uid-scoped novel guard — at wiring time).

Planning guard ruling (ADR-086 plan §3): the eager factory's uid-scoped
novel guard (``get_by_id(novel_id, uid)`` → 404, preventing resolver
auto-creation of ``project_settings`` for foreign novels) is preserved —
NOT dropped — as the service's ``_get_novel`` guard (same repo, same
session), which runs immediately BEFORE the first-use resolve
(gate-before-resolution ordering).

Graceful degradation (AI-optional feature) is service policy, not wiring
(Pattern M-graceful): the eager factory's wiring-time
``except ConfigurationError`` swallow moved into the first-use resolve
(``StoryboardResolution.resolve_graceful``), which logs
``no_ai_provider_configured`` and degrades to the preserved
heuristic-remap outcome. The governed AIRemapService is injected
unconditionally (composer-based, provider-independent) and only engages
on explicit remap requests with sufficient chapter-summary coverage.
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
from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.planning.repository import OutlineRepository
from narrare.planning.service import StoryboardService
from narrare_core.planning.remap import AIRemapService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_storyboard_service(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> StoryboardService:
    """Wire up StoryboardService with LAZY model routing (ADR-086 L21).

    The per-user PLAN cascade is wired as a ``LazyModelResolution`` with
    the same args the eager factory resolved verbatim (intent, uid,
    novel_id — timing-only migration, RULE-18). Repos, registry, composer
    (via ``AIRemapService``), and pipeline still wire eagerly. The
    uid-scoped novel guard and the graceful no-provider degradation live
    in the service's first-use path (see module docstring).

    Args:
        session: DB session.
        user_id: Current user ID (string, will be parsed to UUID).
        novel_id: Target novel UUID.

    Returns:
        Fully wired StoryboardService (model unresolved).
    """
    from narrare_core.llm.intents import LLMIntent

    uid = uuid.UUID(user_id)

    resolver = get_model_routing_resolver(session)
    model_resolution = LazyModelResolution(lambda: resolver.resolve(LLMIntent.PLAN, uid, novel_id))

    return StoryboardService(
        outline_repo=OutlineRepository(session),
        chapter_repo=ChapterRepository(session),
        novel_repo=NovelRepository(session),
        ai_remap_service=AIRemapService(composer=get_composer()),
        model_registry=get_model_registry(),
        model_resolution=model_resolution,
        invocation_pipeline=get_invocation_pipeline(),
    )
