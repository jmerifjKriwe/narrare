"""Dismissed finding repository — DB queries only.

Handles persistence of user-dismissed consistency findings, keyed by a
stable fingerprint per novel (CR-AUFG-07-26).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from narrare._app.base_repository import BaseRepository
from narrare.kb.dismissed_models import DismissedFinding

if TYPE_CHECKING:
    import uuid


class DismissedFindingRepository(BaseRepository):
    """Persistence operations for dismissed consistency findings.

    Uses PostgreSQL ``ON CONFLICT ... DO UPDATE`` so dismissing the same
    fingerprint twice is an idempotent upsert that refreshes the reason
    and timestamp rather than raising an IntegrityError.
    """

    async def dismiss(
        self,
        novel_id: uuid.UUID,
        fingerprint: str,
        reason: str | None = None,
    ) -> None:
        """Upsert a dismissed finding for a novel.

        If the (novel_id, fingerprint) pair already exists, the reason and
        ``dismissed_at`` timestamp are updated.  Otherwise a new row is
        inserted.

        Args:
            novel_id: The project the finding belongs to.
            fingerprint: Stable finding identifier (description::entities).
            reason: Optional user-provided reason for dismissing.
        """
        stmt = (
            pg_insert(DismissedFinding)
            .values(novel_id=novel_id, fingerprint=fingerprint, reason=reason)
            .on_conflict_do_update(
                constraint="uq_dismissed_novel_fingerprint",
                set_={
                    "reason": reason,
                    "dismissed_at": func.now(),
                },
            )
        )
        await self._session.execute(stmt)
        await self._flush()

    async def list_dismissed(self, novel_id: uuid.UUID) -> list[str]:
        """List all dismissed fingerprints for a novel.

        Args:
            novel_id: The project to list dismissed findings for.

        Returns:
            List of dismissed fingerprint strings, most-recent first.
        """
        result = await self._session.execute(
            select(DismissedFinding.fingerprint)
            .where(DismissedFinding.novel_id == novel_id)
            .order_by(DismissedFinding.dismissed_at.desc())
        )
        return list(result.scalars().all())

    async def undismiss(
        self,
        novel_id: uuid.UUID,
        fingerprint: str,
    ) -> bool:
        """Remove a dismissed finding for a novel.

        Args:
            novel_id: The project the finding belongs to.
            fingerprint: Stable finding identifier to un-dismiss.

        Returns:
            ``True`` if a row was deleted, ``False`` if it did not exist.
        """
        result = await self._session.execute(
            delete(DismissedFinding)
            .where(
                DismissedFinding.novel_id == novel_id,
                DismissedFinding.fingerprint == fingerprint,
            )
            .returning(DismissedFinding.id)
        )
        await self._flush()
        return result.scalar_one_or_none() is not None
