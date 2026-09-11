"""KB Suggestion Service — thin API-layer wrapper over ProactiveContextService.

Resolves chapter content and entity metadata, then delegates to the core
ProactiveContextService for the 3-stage suggestion pipeline.

``get_suggestions`` is gated on novel ownership at service entry (IDOR
fix S9): the caller must own ``novel_id`` BEFORE chapter content or KB
entries are loaded — foreign and unknown novels are indistinguishable
(``NotFoundError`` → 404).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.kb._novel_gate import verify_novel_owned
from narrare.kb.schemas import KBSuggestionResponse
from narrare_core.context.suggestion import EntityMetadata
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare_core.context.contracts import ProactiveContextProtocol

logger = structlog.get_logger(__name__)

# Default max results for KB suggestions.
# Can be overridden by callers. Not yet tied to TokenBudgetManager —
# that requires a larger refactor (FIND-005 Phase 2).
DEFAULT_KB_SUGGEST_MAX_RESULTS: int = 20


class KBSuggestService:
    """API service for KB suggestions.

    Resolves data dependencies and delegates to ProactiveContextService.

    Args:
        proactive_context: Core suggestion service.
        chapter_repo: For loading chapter content.
        kb_repo: For loading entity names and metadata.
        novel_repo: Novel repository — the novel ownership gate (IDOR
            fix S9), checked before any chapter or KB read.
    """

    def __init__(
        self,
        proactive_context: ProactiveContextProtocol,
        chapter_repo: ChapterRepositoryProtocol,
        kb_repo: KBRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
    ) -> None:
        self._proactive = proactive_context
        self._chapter_repo = chapter_repo
        self._kb_repo = kb_repo
        self._novel_repo = novel_repo

    async def get_suggestions(
        self,
        chapter_id: UUID,
        *,
        novel_id: UUID,
        user_id: UUID,
        max_results: int = DEFAULT_KB_SUGGEST_MAX_RESULTS,
    ) -> list[KBSuggestionResponse]:
        """Get proactive KB suggestions for a chapter.

        Ownership gate first (IDOR fix S9), then the S5-style compound
        chapter∈novel check: the caller must own ``novel_id`` BEFORE any
        data load, and the chapter must belong to that novel before its
        content reaches the suggestion pipeline. Foreign and unknown
        novels are indistinguishable; a chapter outside the owned novel
        is indistinguishable from an unknown chapter.

        Args:
            chapter_id: UUID of the chapter to analyze.
            novel_id: UUID of the novel — KB scoping (must be owned).
            user_id: Caller identity — the ownership gate input.
            max_results: Maximum suggestions to return (1-100).

        Returns:
            Ranked list of KB suggestions.

        Raises:
            NotFoundError: If the novel is unknown or not owned by the
                caller, or the chapter is not part of the novel.
        """
        await verify_novel_owned(self._novel_repo, novel_id, user_id)

        # 1. Load chapter (scoped to the owned novel)
        chapter = await self._chapter_repo.get_by_id(chapter_id, novel_id)
        if chapter is None:
            raise NotFoundError("Chapter", identifier=str(chapter_id))

        chapter_content = chapter.content or ""

        # 2. Load all KB entries for the novel to get names + metadata
        entries, _ = await self._kb_repo.list_entries(novel_id=novel_id, page_size=1000)

        entity_names = [e.name for e in entries]

        # Build entity metadata map (entry_id → EntityMetadata)
        entity_metadata: dict[UUID, EntityMetadata] = {}
        for entry in entries:
            entity_metadata[entry.id] = EntityMetadata(
                name=entry.name,
                entity_type=entry.entity_type,
                usage_count=entry.usage_count or 0,
                last_referenced_at=entry.last_referenced_at,
            )

        # 3. Delegate to core service
        suggestions = await self._proactive.suggest(
            chapter_content,
            novel_id=novel_id,
            entity_names=entity_names,
            entity_metadata=entity_metadata,
            max_results=max_results,
        )

        # 4. Map to response
        return [
            KBSuggestionResponse(
                entry_id=s.entry_id,
                entry_type=s.entry_type,
                name=s.name,
                relevance_score=round(s.relevance_score, 4),
                reason=s.reason,
                similarity=round(s.similarity, 4),
                usage_count=s.usage_count,
                last_referenced_at=s.last_referenced_at,
            )
            for s in suggestions
        ]
