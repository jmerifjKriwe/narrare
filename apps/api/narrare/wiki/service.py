"""API-layer WikiService — bridges core WikiService with DB persistence.

Loads KB entity data, constructs WikiGenerationDeps, delegates to core
WikiService, and persists results. Ownership checks follow KBService.
Chapter wiki generation is delegated to ChapterWikiService (RULE-04).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.wiki._system_accessors import WikiSystemAccessors
from narrare.wiki.schemas import (
    WikiChapterSummaryResponse,
    WikiIndexResponse,
    WikiRefreshResponse,
    WikiSummaryListResponse,
    WikiSummaryResponse,
)
from narrare_core.shared.errors import ForbiddenError
from narrare_core.wiki.types import WikiGenerationDeps, WikiSummaryData, WikiSummaryStatus

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare.kb.models import KBEntry
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.novels.models import Novel
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
        core_wiki_service: WikiServiceProtocol,
        chapter_wiki_service: ChapterWikiService | None = None,
        chapter_repo: ChapterRepositoryProtocol | None = None,
        model_registry: ModelRegistry | None = None,
        model_routing_resolver: object | None = None,
        *,
        system_mode: bool = False,
    ) -> None:
        self._session = session
        self._wiki_repo = wiki_repo
        self._kb_repo = kb_repo
        self._novel_repo = novel_repo
        self._relationship_repo = relationship_repo
        self._chapter_wiki_service = chapter_wiki_service
        self._chapter_repo = chapter_repo
        self._core = core_wiki_service
        self._model_registry = model_registry
        self._model_routing_resolver = model_routing_resolver
        self._system_mode = system_mode

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _verify_novel_ownership(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Novel:
        """Return the novel if owned by user, else raise ForbiddenError.

        When ``system_mode`` is True, loads the novel without checking
        ownership — background tasks are system-level operations.
        """
        if self._system_mode:
            novel = await self._novel_repo.get(novel_id)
        else:
            novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise ForbiddenError("You do not have access to this novel")
        return novel

    async def _build_generation_deps(
        self,
        entity: KBEntry,
        novel: Novel,
    ) -> WikiGenerationDeps:
        """Build WikiGenerationDeps from entity + novel + relationships."""
        rels = await self._relationship_repo.list_for_entry(entity.id)
        return WikiGenerationDeps(
            language=novel.writing_language or "en",
            genre=novel.genre or "",
            entity_type=entity.entity_type,
            entity_name=entity.name,
            entity_body=entity.body or "",
            entity_metadata=dict(entity.metadata_) if entity.metadata_ else {},
            relationships=[
                {
                    "entity_id": str(r.target_id if r.source_id == entity.id else r.source_id),
                    "rel_type": r.rel_type,
                    "label": r.label,
                }
                for r in rels
            ],
            chapter_context=[],
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

        Returns None on any failure (RULE-11 graceful degradation).
        """
        try:
            novel = await self._verify_novel_ownership(novel_id, user_id)
            entity = await self._kb_repo.get_by_id(entity_id)
            if entity is None or entity.novel_id != novel_id:
                logger.warning("wiki_entity_not_found", entity_id=str(entity_id))
                return None

            deps = await self._build_generation_deps(entity, novel)
            result = await self._core.generate_entity_summary(
                entity_id=str(entity_id),
                novel_id=str(novel_id),
                deps=deps,
            )
            if result is None:
                return None

            summary_data = WikiSummaryData(
                entity_id=str(entity_id),
                novel_id=str(novel_id),
                narrative_summary=result.narrative_summary,
                role_in_story=result.role_in_story,
                key_attributes=result.key_attributes,
                relationships=result.relationships,
                character_arc=result.character_arc,
                status=WikiSummaryStatus.FRESH,
            )
            persisted = await self._wiki_repo.upsert_summary(summary_data, result)
            logger.info("wiki_summary_persisted", entity_id=str(entity_id))
            return WikiSummaryResponse.model_validate(persisted)
        except ForbiddenError:
            raise
        except Exception:
            logger.exception("wiki_generate_failed", entity_id=str(entity_id))
            return None

    async def generate_chapter_summary(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WikiChapterSummaryResponse | None:
        """Generate and persist a wiki summary for a chapter.

        Delegates to ChapterWikiService (RULE-04: file size limits).
        Returns None on any failure (RULE-11 graceful degradation).
        """
        if self._chapter_wiki_service is None:
            logger.error("wiki_chapter_service_not_configured")
            return None
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
        await self._verify_novel_ownership(novel_id, user_id)
        summaries = await self._wiki_repo.get_summaries(entity_ids, novel_id)
        items = [WikiSummaryResponse.model_validate(s) for s in summaries]
        return WikiSummaryListResponse(items=items, total=len(items))

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
        await self._verify_novel_ownership(novel_id, user_id)
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
        await self._verify_novel_ownership(novel_id, user_id)
        summaries = await self._wiki_repo.get_summaries(None, novel_id)
        fresh = sum(1 for s in summaries if s.status == "fresh")
        stale = sum(1 for s in summaries if s.status == "stale")
        pending = sum(1 for s in summaries if s.status == "pending")
        last_gen = max(
            (s.generated_at for s in summaries if s.generated_at),
            default=None,
        )
        return WikiIndexResponse(
            novel_id=novel_id,
            total_summaries=len(summaries),
            fresh_count=fresh,
            stale_count=stale,
            pending_count=pending,
            last_generated_at=last_gen,
        )

    async def mark_all_stale(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        prompt_version: str | None = None,
    ) -> int:
        """Mark all wiki summaries as stale for a novel."""
        await self._verify_novel_ownership(novel_id, user_id)
        version = prompt_version or ""
        count = await self._wiki_repo.mark_all_stale(novel_id, version)
        logger.info(
            "wiki_marked_stale",
            novel_id=str(novel_id),
            count=count,
            prompt_version=version,
        )
        return count
