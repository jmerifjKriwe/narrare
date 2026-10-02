"""Import chapter repository — bulk append (DB only, RULE-06)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from narrare.chapters.models import Chapter

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare_core.importing.models import DetectedChapter


class ImportChapterRepository:
    """Implements ImportChapterRepositoryProtocol (contracts.py) implicitly."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def max_position(self, novel_id: uuid.UUID) -> int:
        """Highest existing chapter position for the novel (-1 when empty)."""
        result = await self._session.execute(
            select(func.max(Chapter.position)).where(Chapter.novel_id == novel_id)
        )
        value = result.scalar_one_or_none()
        # Explicit None check: `value or -1` would map a legitimate max of 0 to -1.
        return -1 if value is None else value

    async def append_chapters(
        self,
        novel_id: uuid.UUID,
        chapters: Sequence[DetectedChapter],
        start_position: int,
    ) -> list[Chapter]:
        """Add all chapters in one flush — atomic within the request transaction."""
        rows = [
            Chapter(
                novel_id=novel_id,
                title=chapter.title,
                content=chapter.content,
                position=start_position + offset,
                word_count=chapter.word_count,
                status=chapter.status,
            )
            for offset, chapter in enumerate(chapters)
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return rows
