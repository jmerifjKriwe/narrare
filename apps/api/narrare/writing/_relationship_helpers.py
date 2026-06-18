"""Shared helpers for writing services — avoids duplication across service files.

Extracted for RULE-04 compliance (file size limits).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare_core.context.contracts import RenderedKBContext


async def fetch_formatted_relationships(
    relationship_repo: RelationshipRepository | None,
    novel_id: UUID,
) -> RenderedKBContext:
    """Fetch KB relationships and format them for prompt context.

    Shared by all writing services (WritingService, ExtendService,
    RewriteService, CoAuthorService) to avoid duplicating the
    fetch-format pattern.  FIND-009.

    Args:
        relationship_repo: Optional relationship repository.  When
            ``None``, returns empty string (graceful degradation).
        novel_id: The novel to fetch relationships for.

    Returns:
        Rendered relationship context. ``.text`` contains the legacy
        formatted relationship text.
    """
    from narrare_core.context.contracts import RenderedKBContext

    if relationship_repo is None:
        return RenderedKBContext(
            text="",
            preserved_fields=frozenset(),
            omitted_fields=(),
            entry_count=0,
            render_path="narrare.writing._relationship_helpers.fetch_formatted_relationships",
        )

    from narrare_core.writing._relationship_format import format_relationships

    edges = await relationship_repo.get_relationships_with_names(novel_id=novel_id)
    return format_relationships(edges)
