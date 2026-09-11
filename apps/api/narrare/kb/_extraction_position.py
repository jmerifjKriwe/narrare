"""Chapter-position resolution for the extraction apply flow (ADR-085 P2).

Resolves a request's ``chapter_id`` to the chapter's position in the
novel's chapter ordering via the chapter repository — never from
client-supplied numbers (spec §9(b)): the stored ``Chapter.position``
ordering column is read server-side at apply time, so renumbered
chapters stamp their current position.

Best-effort by design (spec §5): an unresolvable chapter logs a warning
and yields ``None`` — the apply proceeds without stamping (provenance
absence means "unknown", never negative); it never fails the request.

See:
    :class:`narrare.kb.extraction_service.ExtractionService`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.contracts import ChapterRepositoryProtocol

logger = structlog.get_logger(__name__)


async def resolve_chapter_position(
    chapter_repo: ChapterRepositoryProtocol,
    novel_id: UUID,
    chapter_id: UUID | None,
) -> int | None:
    """Resolve the chapter's ordering position for a provenance stamp.

    Args:
        chapter_repo: Chapter repository (novel-scoped lookup).
        novel_id: Novel scope the chapter must belong to.
        chapter_id: The request's chapter, or ``None`` when the request
            carries no chapter (backward compat — no lookup happens).

    Returns:
        The chapter's position in the novel's chapter ordering, or
        ``None`` when no chapter was requested or it cannot be resolved
        within the novel (logged, per RULE-11 — never a silent drop).
    """
    if chapter_id is None:
        return None
    chapter = await chapter_repo.get_by_id(chapter_id, novel_id)
    if chapter is None:
        logger.warning(
            "apply_chapter_position_unresolved",
            chapter_id=str(chapter_id),
            novel_id=str(novel_id),
        )
        return None
    return chapter.position
