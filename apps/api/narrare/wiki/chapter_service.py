"""Wiki chapter summary generation service.

Handles generation and persistence of wiki summaries for chapters.
Extracted from APIWikiService to respect file size limits (RULE-04).
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import structlog

from narrare.wiki.schemas import WikiChapterSummaryResponse
from narrare_core.shared.errors import ForbiddenError
from narrare_core.wiki.types import (
    WikiChapterSummaryData,
    WikiGenerationDeps,
    WikiSummaryStatus,
)

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.novels.models import Novel
    from narrare.wiki.repository import WikiRepository
    from narrare_core.wiki.contracts import WikiServiceProtocol

logger = structlog.get_logger(__name__)


class ChapterWikiService:
    """Generates and persists wiki summaries for chapters.

    Used by APIWikiService for user-facing chapter summary retrieval and
    by background tasks for chapter finalization events.  When created
    with ``system_mode=True``, ownership checks are bypassed.
    """

    def __init__(
        self,
        wiki_repo: WikiRepository,
        novel_repo: NovelRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
        core_wiki_service: WikiServiceProtocol,
        *,
        system_mode: bool = False,
    ) -> None:
        self._wiki_repo = wiki_repo
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._core = core_wiki_service
        self._system_mode = system_mode

    async def _load_novel(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Novel:
        """Load novel, skipping ownership check in system_mode."""
        if self._system_mode:
            novel = await self._novel_repo.get(novel_id)
        else:
            novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise ForbiddenError("You do not have access to this novel")
        return novel

    async def generate_chapter_summary(
        self,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WikiChapterSummaryResponse | None:
        """Generate and persist a wiki summary for a chapter.

        Flow: load novel → load chapter → build deps → generate → persist.
        Returns None on any failure (RULE-11 graceful degradation).
        """
        try:
            novel = await self._load_novel(novel_id, user_id)

            chapter = await self._chapter_repo.get_by_id(chapter_id, novel_id)
            if chapter is None:
                logger.warning("wiki_chapter_not_found", chapter_id=str(chapter_id))
                return None

            deps = WikiGenerationDeps(
                language=novel.writing_language or "en",
                genre=novel.genre or "",
                entity_type="chapter",
                entity_name=chapter.title,
                entity_body=chapter.content,
                entity_metadata={},
                relationships=[],
                chapter_context=[chapter.content],
            )
            result = await self._core.generate_chapter(deps=deps)
            if result is None:
                return None

            content_hash = hashlib.sha256(chapter.content.encode()).hexdigest()
            summary_data = WikiChapterSummaryData(
                chapter_id=str(chapter_id),
                narrative_summary=result.narrative_summary,
                key_events=result.key_events,
                entities_involved=result.entities_involved,
                themes=result.themes,
                emotional_arc=result.emotional_arc,
                chapter_content_hash=content_hash,
                wiki_prompt_version="1.0.0",
                status=WikiSummaryStatus.FRESH,
            )
            persisted = await self._wiki_repo.upsert_chapter_summary(summary_data, result)
            logger.info("wiki_chapter_summary_persisted", chapter_id=str(chapter_id))
            return WikiChapterSummaryResponse.model_validate(persisted)
        except ForbiddenError:
            raise
        except Exception:
            logger.exception("wiki_chapter_generate_failed", chapter_id=str(chapter_id))
            return None
