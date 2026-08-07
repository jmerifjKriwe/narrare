"""BandSummary repository — DB queries only (Spec 2, Task 3).

Implements ``BandSummaryRepositoryProtocol`` (``band_summary_contracts.py``).
Query-only: no business decisions (RULE-06). Every mutating method is an
upsert keyed by ``novel_id`` (the 1:1 PK), mirroring the
``SeriesRepository.update_settings`` load-or-create pattern so the ORM session
+ ``_flush_and_refresh`` populate ``generated_at`` server-defaults correctly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from narrare._app.base_repository import BaseRepository
from narrare.series.band_summary_models import BandSummary

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class BandSummaryRepository(BaseRepository):
    """DB-query surface for the ``band_summaries`` table (1:1 to ``Novel``)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get(self, novel_id: uuid.UUID) -> BandSummary | None:
        """Load the band summary for a novel (``None`` if no row yet)."""
        result = await self._session.execute(
            select(BandSummary).where(BandSummary.novel_id == novel_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        novel_id: uuid.UUID,
        full_summary: str,
        short_summary: str,
    ) -> BandSummary:
        """Insert or update ``full_summary`` + ``short_summary`` (override kept)."""
        summary = await self._get_or_create(novel_id)
        summary.full_summary = full_summary
        summary.short_summary = short_summary
        await self._flush_and_refresh(summary)
        return summary

    async def set_override(self, novel_id: uuid.UUID, override: str) -> BandSummary:
        """Set the user ``override`` for a novel (creates row on demand)."""
        summary = await self._get_or_create(novel_id)
        summary.override = override
        await self._flush_and_refresh(summary)
        return summary

    async def clear_override(self, novel_id: uuid.UUID) -> BandSummary:
        """Clear the user ``override`` (idempotent; creates row on demand)."""
        summary = await self._get_or_create(novel_id)
        summary.override = None
        await self._flush_and_refresh(summary)
        return summary

    async def _get_or_create(self, novel_id: uuid.UUID) -> BandSummary:
        """Load the row by PK, creating an empty one if absent (upsert basis)."""
        summary = await self.get(novel_id)
        if summary is None:
            summary = BandSummary(novel_id=novel_id)
            self._session.add(summary)
        return summary
