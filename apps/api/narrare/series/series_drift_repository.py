"""SeriesDrift repository — DB queries only (SERIES-004 Slice 6, C2).

Implements ``SeriesDriftRepositoryProtocol`` (``series_drift_contracts.py``).
Query-only: no business decisions (RULE-06).

``store_section`` is a single atomic PostgreSQL ``INSERT … ON CONFLICT
(novel_id) DO UPDATE``: the composite ``result`` document is merged with a
JSONB shallow concat (``series_drift_results.result || excluded.result``) —
exactly the two top-level keys ``consistency`` / ``voice_drift`` — so the
panel's two PARALLEL check POSTs never PK-collide and never clobber each
other's section. A load-or-create loop here would race (both requests would
INSERT the missing row; one would fail on the PK). ``input_fingerprint`` and
record-level ``generated_at`` are refreshed on every write (latest-wins).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from narrare._app.base_repository import BaseRepository
from narrare.series.series_drift_models import SeriesDriftResult

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.series.series_drift_contracts import DriftSection


class SeriesDriftRepository(BaseRepository):
    """DB-query surface for the ``series_drift_results`` table (1:1 to Novel)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get(self, novel_id: uuid.UUID) -> SeriesDriftResult | None:
        """Load the persisted snapshot row for a novel (``None`` if no row)."""
        result = await self._session.execute(
            select(SeriesDriftResult).where(SeriesDriftResult.novel_id == novel_id)
        )
        return result.scalar_one_or_none()

    async def store_section(
        self,
        novel_id: uuid.UUID,
        *,
        section: DriftSection,
        document: dict[str, object],
        fingerprint: str,
    ) -> None:
        """Atomically upsert ONE section of the composite document.

        Args:
            novel_id: The band whose snapshot row is written (created on
                demand by the conflict clause).
            section: The composite-document key this run owns
                (``"consistency"`` or ``"voice_drift"``).
            document: The serialized run-result model (JSON-ready dict).
            fingerprint: Save-time chapter-texts fingerprint (ADR-045 scheme).
        """
        stmt = pg_insert(SeriesDriftResult).values(
            novel_id=novel_id,
            result={section: document},
            input_fingerprint=fingerprint,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[SeriesDriftResult.novel_id],
            set_={
                # JSONB shallow merge: this run's section overlays the stored
                # document; the sibling section survives.
                "result": SeriesDriftResult.result.op("||")(stmt.excluded.result),
                "input_fingerprint": stmt.excluded.input_fingerprint,
                "generated_at": func.now(),
            },
        )
        await self._session.execute(stmt)
