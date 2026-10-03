"""Start-path chapter validation for the bulk extraction job (ADR-092 §4.6).

The real :class:`BulkChapterReader` implementation behind
``BulkExtractionService.start``: a single ``ChapterRepository.list_by_novel``
load serves membership, emptiness, title, and position, so a malformed
start request fails as 422 (``narrare_core`` ``ValidationError`` naming
the offending id) BEFORE any job record exists — no wasted registry entry,
no wasted AI budget.

Validation order: duplicates → cap → membership → content.

The non-empty-content rule mirrors ``ExtractionService.extract_from_chapter``
(``not (chapter.content or "").strip()`` → per-chapter ``ValueError``):
rejecting such chapters at start instead of inside the batch spares the
user a guaranteed per-chapter failure and keeps the job's promise
("these chapters will be analyzed") honest.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.kb.bulk_extraction.contracts import BULK_EXTRACT_MAX_CHAPTERS, BulkChapterRef
from narrare_core.shared.errors import ValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from narrare.chapters.contracts import ChapterRepositoryProtocol


class ChapterReader:
    """Load + validate the requested chapters of one start request.

    Implements the ``BulkChapterReader`` Protocol structurally; DI wires
    the session-scoped ``ChapterRepository`` (RULE-19). Position order of
    the novel's chapters is the job's canonical order (spec §4.1).
    """

    def __init__(self, chapter_repo: ChapterRepositoryProtocol) -> None:
        self._chapter_repo = chapter_repo

    async def load(self, novel_id: UUID, chapter_ids: Sequence[UUID]) -> list[BulkChapterRef]:
        """Validate ``chapter_ids`` against ``novel_id``; return position-ordered refs.

        Raises:
            ValidationError: empty request, a duplicate id, a request over
                the engine cap, an id that does not resolve to a chapter of
                ``novel_id`` (foreign ≡ unknown — the novel itself was
                already ownership-gated), or a chapter without content.
                Every message names the offending id (spec §4.6).
        """
        if not chapter_ids:
            raise ValidationError("chapter_ids must not be empty")
        self._reject_duplicates(chapter_ids)
        self._reject_over_cap(chapter_ids)

        chapters = {
            chapter.id: chapter for chapter in await self._chapter_repo.list_by_novel(novel_id)
        }
        requested = list(dict.fromkeys(chapter_ids))
        missing = [chapter_id for chapter_id in requested if chapter_id not in chapters]
        if missing:
            raise ValidationError(
                f"Chapter {missing[0]} not found in novel {novel_id} "
                f"({len(missing)} of {len(requested)} requested ids unresolved)"
            )
        empty = [
            chapter_id
            for chapter_id in requested
            if not (chapters[chapter_id].content or "").strip()
        ]
        if empty:
            raise ValidationError(f"Chapter {empty[0]} has no content")

        refs = [
            BulkChapterRef(
                chapter_id=chapter_id,
                title=chapters[chapter_id].title,
                position=chapters[chapter_id].position,
            )
            for chapter_id in requested
        ]
        return sorted(refs, key=lambda ref: ref.position)

    @staticmethod
    def _reject_duplicates(chapter_ids: Sequence[UUID]) -> None:
        seen: set[UUID] = set()
        for chapter_id in chapter_ids:
            if chapter_id in seen:
                raise ValidationError(f"Duplicate chapter id in request: {chapter_id}")
            seen.add(chapter_id)

    @staticmethod
    def _reject_over_cap(chapter_ids: Sequence[UUID]) -> None:
        if len(chapter_ids) > BULK_EXTRACT_MAX_CHAPTERS:
            raise ValidationError(
                f"chapter_ids exceeds the maximum of {BULK_EXTRACT_MAX_CHAPTERS} chapters"
            )
