"""Wiki dependency injection factories.

Creates WikiRepository, ChapterWikiService, and APIWikiService with all
required dependencies wired up following the pattern from kb/dependencies.py.
Two factories: user-facing (normal ownership checks) and system (bypassed).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import (
    SessionDep,
    get_invocation_pipeline,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from narrare.wiki.repository import WikiRepository
    from narrare.wiki.service import APIWikiService
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.wiki.contracts import WikiServiceProtocol


def get_wiki_repository(session: SessionDep) -> WikiRepository:
    """Create a WikiRepository with the given session."""
    from narrare.wiki.repository import WikiRepository

    return WikiRepository(session)


async def build_core_wiki_service(
    invocation_pipeline: InvocationPipeline | None = None,
) -> WikiServiceProtocol:
    """Create the core WikiService with agent, event bus, and optional pipeline.

    Args:
        invocation_pipeline: Optional InvocationPipeline for evidence
            recording (ADR-048). When ``None``, pipeline is skipped.

    Returns:
        A configured WikiService instance.
    """
    from narrare._app.dependencies import get_model_registry
    from narrare._app.dependencies_services import (
        SystemModelCategory,
        build_system_default_config,
    )
    from narrare_core.events.bus import NullEventBus
    from narrare_core.wiki.agent import WikiGenerationAgent
    from narrare_core.wiki.service import WikiService

    registry = get_model_registry()
    config = build_system_default_config(
        SystemModelCategory.WRITING, temperature=0.7, max_tokens=4096
    )
    model = await registry.get_model(config)
    agent = WikiGenerationAgent(model=model)
    return WikiService(
        agent=agent,
        event_bus=NullEventBus(),
        invocation_pipeline=invocation_pipeline,
    )


async def get_wiki_service(session: SessionDep) -> APIWikiService:
    """Create APIWikiService with all injected dependencies.

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

    pipeline = get_invocation_pipeline()
    core_service = await build_core_wiki_service(invocation_pipeline=pipeline)

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
