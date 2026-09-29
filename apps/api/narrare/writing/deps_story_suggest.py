"""Service factory for story suggest — wires StorySuggestService lazily.

Follows the same graceful pattern as ``planning/_character_arc_factory.py``
(ADR-086 L20, Pattern M-graceful): model routing is wired as a
``LazyModelResolution`` (ADR-086 L34) — the per-user SUGGEST cascade
resolves on the service's first use, never at construction, so request
validation errors surface as 422 before any routing work.

Planning guard ruling (ADR-086 plan §3): the eager factory's uid-scoped
novel guard (``verify_novel_owned`` → 404, preventing resolver
auto-creation of ``project_settings`` for foreign novels) is preserved —
NOT dropped — in the service's first-use paths: the router's pre-stream
``validate_suggest`` seam runs it immediately BEFORE the first-use
resolve (gate-before-resolution ordering), keeping the 404 a pre-header
status on the SSE endpoint, and the ``suggest`` entry point re-runs both
idempotently for direct callers.

Graceful degradation is entry-point policy, not wiring (Pattern
M-graceful): the eager factory's wiring-time ``except ConfigurationError``
swallow moved into the service's first-use paths, which log
``no_ai_provider_configured`` and preserve the ``no_model_config``
degraded outcome (AI-optional feature).

See WRITE-009 (Writer's Unblock Tools).
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
from narrare.planning.repository import OutlineRepository
from narrare.writing.story_suggest_service import StorySuggestService
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_story_suggest_service(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> StorySuggestService:
    """Wire up StorySuggestService with LAZY model routing (ADR-086 L34).

    The per-user SUGGEST cascade is wired as a ``LazyModelResolution``
    with the same args the eager factory resolved verbatim (intent, uid,
    novel_id — timing-only migration, RULE-18). Repos, registry,
    composer, and pipeline still wire eagerly. The uid-scoped novel
    guard and the graceful no-provider degradation live in the service's
    first-use paths (see module docstring).

    Args:
        session: DB session.
        user_id: Current user ID (string, will be parsed to UUID).
        novel_id: Target novel UUID.

    Returns:
        Fully wired StorySuggestService (model unresolved).
    """
    uid = uuid.UUID(user_id)

    novel_repo = NovelRepository(session)
    resolver = get_model_routing_resolver(session)
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.SUGGEST, uid, novel_id)
    )

    return StorySuggestService(
        novel_repo=novel_repo,
        model_registry=get_model_registry(),
        model_resolution=model_resolution,
        composer=get_composer(),
        outline_repo=OutlineRepository(session),
        invocation_pipeline=get_invocation_pipeline(),
    )
