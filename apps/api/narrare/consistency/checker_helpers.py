"""Private helpers for ConsistencyCheckerService — data fetching.

Extracted from checker_service.py per RULE-04 to keep the service under 300 lines.
These are module-internal helpers, not part of the public API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.repository import KBRepository

logger = structlog.get_logger(__name__)


async def fetch_chapters(
    chapter_repo: ChapterRepository,
    novel_id: uuid.UUID,
    chapter_ids: list[uuid.UUID],
) -> tuple[dict[str, str], list[uuid.UUID]]:
    """Fetch chapter content from repository.

    If *chapter_ids* is empty, fetches ALL chapters for the novel
    (all-chapters fallback for comprehensive checking).

    Args:
        chapter_repo: Chapter persistence layer.
        novel_id: The novel to fetch chapters for.
        chapter_ids: Specific chapter IDs, or empty for all chapters.

    Returns:
        Tuple of (chapter_texts mapping, resolved chapter ID list).
        Returns empty dict and empty list if no chapters found.

    Raises:
        NotFoundError: If any specifically requested chapter_id is missing.
    """
    if not chapter_ids:
        chapters = await chapter_repo.list_by_novel(novel_id)
        if not chapters:
            return {}, []
        texts = {str(ch.id): ch.content or "" for ch in chapters}
        ids = [ch.id for ch in chapters]
        return texts, ids

    texts: dict[str, str] = {}
    ids: list[uuid.UUID] = []
    for cid in chapter_ids:
        chapter = await chapter_repo.get_by_id(cid, novel_id)
        if chapter is None:
            raise NotFoundError("Chapter", identifier=str(cid))
        texts[str(cid)] = chapter.content or ""
        ids.append(cid)
    return texts, ids


async def fetch_kb_summaries(
    kb_repo: KBRepository,
    novel_id: uuid.UUID,
    max_kb_entries: int = 100,
) -> list[dict[str, object]]:
    """Build simplified KB entity summaries for agent context.

    Args:
        kb_repo: KB persistence layer.
        novel_id: The novel to fetch KB entries for.
        max_kb_entries: Maximum number of KB entries to fetch.

    Returns:
        List of dicts with ``entity_type``, ``name``, and ``fields`` keys.
        Empty list if no KB entries exist.
    """
    entries, _total = await kb_repo.list_entries(
        novel_id,
        page_size=max_kb_entries,
    )
    summaries: list[dict[str, object]] = []
    for entry in entries:
        summaries.append(
            {
                "entity_type": entry.entity_type,
                "name": entry.name,
                "fields": entry.metadata_ or {},
            }
        )
    return summaries
