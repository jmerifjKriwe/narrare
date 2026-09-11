"""Wiki dependency injection factories.

Creates WikiRepository, ChapterWikiService, and APIWikiService with all
required dependencies wired up following the pattern from kb/dependencies.py.
Two factories: user-facing (normal ownership checks) and system (bypassed).

Model planes (Task 6 user-routing migration):
- ``get_wiki_service`` (user-facing refresh path) resolves via the
  per-user model-routing cascade — real intent SUMMARIZE (the intent
  core ``WikiService`` composes with at both call sites) — with the
  novel_id project tier (all wiki routes are novel-scoped).
- ``build_core_wiki_service`` with ``config=None`` stays on the operator
  plane (system-default config): it serves the STARTUP wiki listener in
  ``_app/lifespan.py``, where no user context exists. Plan-sanctioned
  survivor (user-routing migration plan, Global Constraints). The core
  service factory itself lives in ``dependencies_core.py`` (RULE-04
  split) and is re-exported here for wiring stability.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends

from narrare._app.dependencies import (
    SessionDep,
    get_current_user_id,
    get_invocation_pipeline,
)
from narrare._app.dependencies_services import get_model_routing_resolver
from narrare.wiki.dependencies_core import build_core_wiki_service
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from collections.abc import Callable

    from narrare.wiki.repository import WikiRepository
    from narrare.wiki.service import APIWikiService
    from narrare_core.wiki.contracts import WikiServiceProtocol

__all__ = [
    "build_core_wiki_service",
    "get_wiki_repository",
    "get_wiki_service",
    "make_system_wiki_factory",
]


def get_wiki_repository(session: SessionDep) -> WikiRepository:
    """Create a WikiRepository with the given session."""
    from narrare.wiki.repository import WikiRepository

    return WikiRepository(session)


async def get_wiki_service(
    novel_id: UUID,
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> APIWikiService:
    """Create APIWikiService with all injected dependencies.

    User-facing refresh path: resolves ``LLMIntent.SUMMARIZE`` (the real
    intent core ``WikiService`` composes with) via the per-user cascade
    WITH the novel_id project tier — every wiki route is novel-scoped, so
    the path parameter is available at dependency-wiring time.
    ``ConfigurationError`` propagates when the user has no provider
    configured (wiki routers are auth-mandatory).

    Production wiring: WikiGenerationAgent for core WikiService,
    NullEventBus for event publishing, invocation pipeline for
    evidence recording (ADR-048), and all repositories
    for data access.  Uses normal ownership checks (system_mode=False).
    """
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare.wiki.chapter_service import ChapterWikiService
    from narrare.wiki.repository import WikiRepository
    from narrare.wiki.service import APIWikiService

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(LLMIntent.SUMMARIZE, UUID(user_id), novel_id)

    pipeline = get_invocation_pipeline()
    core_service = await build_core_wiki_service(
        invocation_pipeline=pipeline,
        config=resolved.config,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )

    chapter_wiki_svc = ChapterWikiService(
        wiki_repo=WikiRepository(session),
        novel_repo=NovelRepository(session),
        chapter_repo=ChapterRepository(session),
        core_wiki_service=core_service,
    )

    return APIWikiService(
        session=session,
        wiki_repo=WikiRepository(session),
        kb_repo=KBRepository(session),
        novel_repo=NovelRepository(session),
        relationship_repo=RelationshipRepository(session),
        core_wiki_service=core_service,
        chapter_wiki_service=chapter_wiki_svc,
        chapter_repo=ChapterRepository(session),
        model_registry=None,
        model_routing_resolver=None,
        system_mode=False,
    )


def make_system_wiki_factory(
    core_service: WikiServiceProtocol,
) -> Callable[[], APIWikiService]:
    """Create a zero-arg factory for system-mode APIWikiService.

    Used by WikiEventListener and background tasks.  The factory creates
    a fresh session and service per call.  The core_service is captured
    in a closure to avoid repeated async model initialization.

    Args:
        core_service: Pre-created core WikiService (from startup).

    Returns:
        Callable that creates system-mode APIWikiService instances.
    """
    from narrare._app.database import get_session_factory
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare.wiki.chapter_service import ChapterWikiService
    from narrare.wiki.repository import WikiRepository
    from narrare.wiki.service import APIWikiService

    session_factory = get_session_factory()

    def factory() -> APIWikiService:
        session = session_factory()
        chapter_wiki_svc = ChapterWikiService(
            wiki_repo=WikiRepository(session),
            novel_repo=NovelRepository(session),
            chapter_repo=ChapterRepository(session),
            core_wiki_service=core_service,
            system_mode=True,
        )
        return APIWikiService(
            session=session,
            wiki_repo=WikiRepository(session),
            kb_repo=KBRepository(session),
            novel_repo=NovelRepository(session),
            relationship_repo=RelationshipRepository(session),
            core_wiki_service=core_service,
            chapter_wiki_service=chapter_wiki_svc,
            chapter_repo=ChapterRepository(session),
            system_mode=True,
        )

    return factory
