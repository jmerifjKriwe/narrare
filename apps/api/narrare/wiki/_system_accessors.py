"""System-level wiki accessors for background tasks and event listeners.

Mixin for APIWikiService that exposes read/write methods without ownership
checks.  These are used exclusively by background tasks and event listeners
that operate in system mode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.wiki.schemas import WikiChapterSummaryResponse, WikiSummaryResponse

if TYPE_CHECKING:
    import uuid

    from narrare.wiki.repository import WikiRepository


class WikiSystemAccessors:
    """Mixin providing system-level wiki read/write methods.

    Subclasses must set ``self._wiki_repo`` (a WikiRepository instance)
    before calling any of these methods.
    """

    _wiki_repo: WikiRepository

    async def get_summary_raw(
        self,
        entity_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> WikiSummaryResponse | None:
        """Read a single entity wiki summary without ownership checks.

        Used by background tasks for idempotency checks.  Returns ``None``
        when no summary exists for the given entity.
        """
        result = await self._wiki_repo.get_summary(entity_id, novel_id)
        return WikiSummaryResponse.model_validate(result) if result else None

    async def get_chapter_summary_raw(
        self,
        chapter_id: uuid.UUID,
    ) -> WikiChapterSummaryResponse | None:
        """Read a chapter wiki summary without ownership checks.

        Used by background tasks for idempotency checks.  Returns ``None``
        when no summary exists for the given chapter.
        """
        result = await self._wiki_repo.get_chapter_summary(chapter_id)
        return WikiChapterSummaryResponse.model_validate(result) if result else None

    async def mark_related_stale(self, entity_id: uuid.UUID) -> int:
        """Mark wiki summaries that reference *entity_id* as stale.

        Cross-entity staleness propagation for background listeners.
        Returns the number of summaries marked stale.
        """
        return await self._wiki_repo.mark_related_stale(entity_id)
