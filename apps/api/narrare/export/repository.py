"""Read-only manuscript source loader for export (RULE-22).

Export **never modifies** the source data: no ``add``/``update``/``delete``,
no commit. This repository issues only ``SELECT`` statements against the
novels + chapters tables to assemble the raw material the export runner
(:mod:`narrare.export.tasks`) turns into a :class:`ManuscriptMetadata` + the
assembled manuscript HTML. The chapter-content → metadata → HTML assembly
logic lives in the runner (logic), not here (queries only — RULE-06/RULE-22).

The returned :class:`ManuscriptSource` is a plain dataclass of DB rows — it is
NOT the Core :class:`ManuscriptMetadata` (which the runner builds from it,
coercing ``language`` to the Core :class:`Language` enum). Keeping the DB-shape
separate from the Core-shape means this module imports no
``narrare_core.export`` symbol (clean layering: repository = DB, Core = pure
domain).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select

from narrare.chapters.models import Chapter
from narrare.novels.models import Novel

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ChapterRow:
    """One chapter's export-relevant columns, in position order."""

    chapter_id: UUID
    title: str
    position: int
    volume_id: UUID | None
    content: str


@dataclass(frozen=True)
class ManuscriptSource:
    """Raw DB material for one novel's manuscript (read-only snapshot).

    ``language`` is the raw ``Novel.writing_language`` string; the runner
    coerces it to the Core :class:`Language` enum (raising on unknown values
    rather than silently falling back — the no-silent-fallback principle).
    """

    novel_id: UUID
    title: str
    author: str
    language: str
    chapters: list[ChapterRow]


class ExportRepository:
    """RULE-22 read-only loader. Construct with a request/background session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_manuscript_source(
        self,
        novel_id: UUID,
        volume_id: UUID | None = None,
    ) -> ManuscriptSource | None:
        """Load novel metadata + its chapters in position order.

        Returns ``None`` if the novel does not exist (the runner turns that
        into a FAILED job with a typed reason). ``volume_id`` optionally
        restricts the chapter set to one volume.
        """
        novel = await self._get_novel(novel_id)
        if novel is None:
            return None

        chapters = await self._list_chapters(novel_id, volume_id)
        return ManuscriptSource(
            novel_id=novel_id,
            title=novel.title,
            author=novel.author,
            language=novel.writing_language,
            chapters=chapters,
        )

    async def _get_novel(self, novel_id: UUID) -> Novel | None:
        result = await self._session.execute(
            select(Novel).where(Novel.id == novel_id),
        )
        return result.scalar_one_or_none()

    async def _list_chapters(
        self,
        novel_id: UUID,
        volume_id: UUID | None,
    ) -> list[ChapterRow]:
        stmt = select(Chapter).where(Chapter.novel_id == novel_id)
        if volume_id is not None:
            stmt = stmt.where(Chapter.volume_id == volume_id)
        stmt = stmt.order_by(Chapter.position, Chapter.created_at)
        result = await self._session.execute(stmt)
        rows = list(result.scalars())
        return [
            ChapterRow(
                chapter_id=row.id,
                title=row.title,
                position=row.position,
                volume_id=row.volume_id,
                content=row.content,
            )
            for row in rows
        ]
