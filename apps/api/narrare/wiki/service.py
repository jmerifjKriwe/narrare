"""API-layer WikiService — bridges core WikiService with DB persistence.

Loads KB entity data, constructs WikiGenerationDeps, delegates to core
WikiService, and persists results. Ownership checks follow KBService.
Chapter wiki generation is delegated to ChapterWikiService (RULE-04).

ADR-086 L30 (user plane): the core WikiService composes lazily — the
DI factory threads a ``core_service_factory`` closure (per-user routing
resolve + PreparedWikiAgent assembly), and the service builds + caches
the core on FIRST AI use (``_ensure_core_service``), post-validation
and ahead of the in-method gates (eager-world precedence, L06-L11
landed shape). ConfigurationError propagates un-swallowed (loud
RULE-11 — wiki is AI-mandatory). The system plane keeps its eager
startup-built core (operator plane — out of ledger).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.wiki._system_accessors import WikiSystemAccessors
from narrare.wiki.chapter_service import ChapterWikiService
from narrare.wiki.generation_support import (
    build_wiki_index,
    compose_chapter_wiki_service,
    generate_and_persist_summary,
    list_summaries,
    verify_novel_ownership,
)
from narrare.wiki.schemas import (
    WikiChapterSummaryResponse,
    WikiIndexResponse,
    WikiRefreshResponse,
    WikiSummaryListResponse,
    WikiSummaryResponse,
)

if TYPE_CHECKING:
    import uuid
    from collections.abc import Awaitable, Callable

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.wiki.chapter_service import ChapterWikiService
    from narrare.wiki.repository import WikiRepository
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.wiki.contracts import WikiServiceProtocol

logger = structlog.get_logger(__name__)


class APIWikiService(WikiSystemAccessors):
    """Orchestrates wiki generation, persistence, and queries.

    Bridges HTTP routes and core WikiService: loads entity data →
    builds deps → generates → persists → returns response.
    """

    def __init__(
        self,
        session: AsyncSession,
        wiki_repo: WikiRepository,
        kb_repo: KBRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
        relationship_repo: RelationshipRepositoryProtocol,
        core_wiki_service: WikiServiceProtocol | None = None,
        chapter_wiki_service: ChapterWikiService | None = None,
        chapter_repo: ChapterRepositoryProtocol | None = None,
        model_registry: ModelRegistry | None = None,
        model_routing_resolver: object | None = None,
        *,
        core_service_factory: Callable[[], Awaitable[WikiServiceProtocol]] | None = None,
        system_mode: bool = False,
    ) -> None:
        """Wire the service for one of two planes.

        - System plane (startup listener, background tasks): pass the
          eager ``core_wiki_service`` built at lifespan startup.
        - User plane (ADR-086 L30): pass ``core_service_factory`` — the
          core composes lazily on first AI use, never at construction.

        Raises:
            ValueError: If eager core and lazy factory are not mutually
                exclusive (exactly one is required).
        """
        msg = (
            "Exactly one of core_wiki_service (eager/system plane) or "
            "core_service_factory (lazy/user plane, ADR-086) is required"
        )
        if core_wiki_service is not None:
            if core_service_factory is not None:
                raise ValueError(msg)

            # System plane: normalize the eager core into a factory so
            # _ensure_core_service has a single code path (returns the
            # same startup-built instance every time).
            async def eager_factory() -> WikiServiceProtocol:
                return core_wiki_service

            core_service_factory = eager_factory
        elif core_service_factory is None:
            raise ValueError(msg)
        self._session = session
        self._wiki_repo = wiki_repo
        self._kb_repo = kb_repo
        self._novel_repo = novel_repo
        self._relationship_repo = relationship_repo
        self._chapter_wiki_service = chapter_wiki_service
        self._chapter_repo = chapter_repo
        self._core = core_wiki_service
        self._core_service_factory = core_service_factory
        self._model_registry = model_registry
        self._model_routing_resolver = model_routing_resolver
        self._system_mode = system_mode

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _ensure_core_service(self) -> WikiServiceProtocol:
        """Return the core WikiService, building it on first use (ADR-086).

        User plane: the factory-supplied closure resolves the per-user
        routing cascade and assembles the core service exactly once,
        then caches. ``ConfigurationError`` (unconfigured provider)
        propagates un-swallowed — loud RULE-11, AI-mandatory feature.
        """
        if self._core is None:
            self._core = await self._core_service_factory()
        return self._core

    async def _verify_access(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Ownership gate for the wired plane (403 semantics, KB-plane)."""
        await verify_novel_ownership(
            self._novel_repo, novel_id, user_id, system_mode=self._system_mode
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_entity_summary(
        self,
        entity_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WikiSummaryResponse | None:
        """Full generation flow: verify → load → generate → persist.

        ADR-086: first-use lazy core-service composition (per-user
        resolve + PreparedWikiAgent assembly), post-validation and
        ahead of the gates — eager-world precedence (L06-L11 shape).
        Returns None on any failure (RULE-11 graceful degradation).
        """
        core = await self._ensure_core_service()
        return await generate_and_persist_summary(
            self._wiki_repo,
            self._kb_repo,
            self._novel_repo,
            self._relationship_repo,
            core,
            entity_id,
            novel_id,
            user_id,
            system_mode=self._system_mode,
        )

    async def generate_chapter_summary(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WikiChapterSummaryResponse | None:
        """Generate and persist a wiki summary for a chapter.

        Delegates to ChapterWikiService (RULE-04: file size limits).
        User plane: the chapter service composes at first chapter AI
        use, sharing the lazily built core instance. Returns None on
        any failure (RULE-11 graceful degradation).
        """
        if self._chapter_wiki_service is None:
            if self._chapter_repo is None:
                logger.error("wiki_chapter_service_not_configured")
                return None
            core = await self._ensure_core_service()
            self._chapter_wiki_service = compose_chapter_wiki_service(
                self._wiki_repo,
                self._novel_repo,
                self._chapter_repo,
                core,
                system_mode=self._system_mode,
            )
        return await self._chapter_wiki_service.generate_chapter_summary(
            chapter_id, novel_id, user_id
        )

    async def get_summaries(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        entity_ids: list[uuid.UUID] | None = None,
    ) -> WikiSummaryListResponse:
        """List wiki summaries, optionally filtered by entity IDs."""
        await self._verify_access(novel_id, user_id)
        return await list_summaries(self._wiki_repo, entity_ids, novel_id)

    async def get_chapter_summary(
        self,
        chapter_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WikiChapterSummaryResponse | None:
        """Fetch a chapter-level wiki summary."""
        summary = await self._wiki_repo.get_chapter_summary(chapter_id)
        if summary is None:
            return None
        return WikiChapterSummaryResponse.model_validate(summary)

    async def refresh_summary(
        self,
        entity_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        force: bool = False,
    ) -> WikiRefreshResponse:
        """Refresh a single entity's wiki summary."""
        await self._verify_access(novel_id, user_id)
        if not force:
            existing = await self._wiki_repo.get_summary(entity_id, novel_id)
            if existing is not None and existing.status == "fresh":
                return WikiRefreshResponse(
                    summary_id=existing.id,
                    status="fresh",
                    message="Summary is already fresh — use force=True to regenerate.",
                )

        result = await self.generate_entity_summary(entity_id, novel_id, user_id)
        if result is None:
            return WikiRefreshResponse(
                summary_id=None,
                status="error",
                message="Generation failed — try again later.",
            )
        return WikiRefreshResponse(
            summary_id=result.id,
            status=result.status,
            message="Summary refreshed successfully.",
        )

    async def get_wiki_index(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WikiIndexResponse:
        """Overview of wiki summary statuses for a novel."""
        await self._verify_access(novel_id, user_id)
        return await build_wiki_index(self._wiki_repo, novel_id)

    async def mark_all_stale(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        prompt_version: str | None = None,
    ) -> int:
        """Mark all wiki summaries as stale for a novel."""
        await self._verify_access(novel_id, user_id)
        version = prompt_version or ""
        count = await self._wiki_repo.mark_all_stale(novel_id, version)
        logger.info(
            "wiki_marked_stale",
            novel_id=str(novel_id),
            count=count,
            prompt_version=version,
        )
        return count

    async def mark_all_stale_global(self) -> int:
        """Mark EVERY wiki summary stale, across all novels (Q-016).

        Triggered when the wiki generation prompt is overridden globally
        (prompts have no novel dimension). No ownership check — the call is
        system-initiated from ``WikiEventListener`` via the system-mode
        factory. Contrast with :meth:`mark_all_stale` (per-novel, version-gated).
        """
        count = await self._wiki_repo.mark_all_stale_global()
        logger.info("wiki_marked_stale_global", count=count)
        return count
