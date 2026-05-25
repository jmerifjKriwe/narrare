"""Context assembly contracts — Protocol definitions.

Defines the interface for proactive context suggestion services.
Contracts are written before implementation (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.context.suggestion import EntityMetadata, Suggestion


@runtime_checkable
class ProactiveContextProtocol(Protocol):
    """Protocol for proactive KB context suggestion.

    Suggests relevant KB entries based on chapter content using
    a three-stage pipeline: name matching -> embedding search -> hybrid scoring.
    """

    async def suggest(
        self,
        chapter_content: str,
        *,
        novel_id: UUID,
        chapter_frontmatter: dict[str, object] | None = None,
        entity_names: list[str] | None = None,
        max_results: int = 20,
        entity_metadata: dict[UUID, EntityMetadata] | None = None,
    ) -> list[Suggestion]:
        """Suggest relevant KB entries for a chapter.

        Args:
            chapter_content: The chapter text to analyze.
            novel_id: Novel UUID to scope the embedding search.
            chapter_frontmatter: Optional frontmatter (POV character, location, etc.).
            entity_names: Known entity names for name matching.
            max_results: Maximum suggestions to return (1-100, default 20).
            entity_metadata: Optional metadata mapping entry_id to name, type,
                usage_count, and last_referenced_at. Used for name-match boost,
                hybrid scoring, and building Suggestion objects.

        Returns:
            Ranked list of Suggestions sorted by relevance_score descending.
        """
        ...
