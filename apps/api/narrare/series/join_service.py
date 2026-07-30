"""SeriesJoinService — Policy alpha (preview-then-apply scope assignment).

Policy alpha decides how each KB entry of a joining novel is treated based
on the target series' Canon state at preview time:

* **Canon empty** — Policy iii heuristics apply. Entity types
  ``system / concept / setting / location / object / timeline`` default to
  Series-Canon (promoted); ``character / faction`` default to Novel-Overlay
  (kept).
* **Canon non-empty** — every joining entry stays a Novel-Overlay.

``preview_join`` computes the per-entry treatment without mutating state.
``apply_join`` re-previews (authoritative — state may have shifted between
the user's preview and their apply) and executes the treatments atomically
within the session transaction: commit on success, rollback + re-raise on
any failure (RULE-11).

Business logic only (RULE-06): all DB work is delegated to the repositories;
the session is used solely for transaction control.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.series.schemas import JoinEntryTreatment, JoinPreview, JoinResult
from narrare_core.shared.errors import ConflictError, NotFoundError

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare_core.kb.schemas.entry import NovelKBEntry

logger = structlog.get_logger(__name__)

# Policy iii entity-type defaults (Series Foundation spec).
# Canon-preferring types are promoted to Series-Canon when the Canon is empty;
# character/faction stay Novel-Overlay even on a first join.
_CANON_TYPES: frozenset[str] = frozenset(
    {"system", "concept", "setting", "location", "object", "timeline"}
)
_OVERLAY_TYPES: frozenset[str] = frozenset({"character", "faction"})


class NovelAlreadyInSeriesError(ConflictError):
    """Raised when a novel is already a member of another series (409).

    Subclasses :class:`ConflictError` so the router can map it to HTTP 409
    alongside other state-conflict errors.
    """

    def __init__(self, novel_id: uuid.UUID, existing_series_id: uuid.UUID) -> None:
        super().__init__(f"Novel {novel_id} is already in series {existing_series_id}")
        self.novel_id = novel_id
        self.existing_series_id = existing_series_id


class SeriesJoinService:
    """Policy alpha: adaptive scope assignment on join (preview-then-apply)."""

    def __init__(
        self,
        session: AsyncSession,
        series_repo: SeriesRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
        kb_repo: KBRepositoryProtocol,
    ) -> None:
        self._session = session
        # ``series_repo`` is injected for DI completeness (router wiring) and
        # reserved for future series-existence/ownership checks; the current
        # join logic operates on the novel + its KB entries only.
        self._series_repo = series_repo
        self._novel_repo = novel_repo
        self._kb_repo = kb_repo

    async def preview_join(self, series_id: uuid.UUID, novel_id: uuid.UUID) -> JoinPreview:
        """Compute per-entry treatments without mutating state.

        Args:
            series_id: The series the novel would join.
            novel_id: The novel joining the series.

        Raises:
            NotFoundError: If the novel does not exist.
            NovelAlreadyInSeriesError: If the novel is already in another series.
        """
        novel = await self._novel_repo.get(novel_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))
        if novel.series_id is not None and novel.series_id != series_id:
            raise NovelAlreadyInSeriesError(novel_id, novel.series_id)

        canon_entries = await self._kb_repo.find_canon_for_series(series_id)
        canon_empty = len(canon_entries) == 0
        novel_entries = await self._kb_repo.find_overlay_for_novel(novel_id)

        treatments = [self._treatment_for(e, canon_empty) for e in novel_entries]
        return JoinPreview(
            series_id=series_id,
            novel_id=novel_id,
            canon_empty=canon_empty,
            treatments=treatments,
        )

    async def apply_join(
        self, series_id: uuid.UUID, novel_id: uuid.UUID, position: int
    ) -> JoinResult:
        """Execute the previewed treatments atomically.

        Re-previews to obtain authoritative treatments (state may have changed
        since the user previewed), then assigns series membership and promotes
        the canon-default entries. All mutations commit together or roll back
        together.

        Args:
            series_id: The series to join.
            novel_id: The novel joining the series.
            position: 1-based position within the series.

        Raises:
            NotFoundError: If the novel does not exist.
            NovelAlreadyInSeriesError: If the novel is already in another series.
        """
        # Authoritative: re-derive treatments from current state.
        preview = await self.preview_join(series_id, novel_id)

        promoted = 0
        kept = 0
        try:
            # Membership first: promote_to_canon (real repo) requires the
            # novel to already carry series_id.
            await self._novel_repo.update_series_membership(
                novel_id, series_id=series_id, series_position=position
            )
            for treatment in preview.treatments:
                if treatment.target_scope == "series":
                    await self._kb_repo.promote_to_canon(novel_id, treatment.entry_id)
                    promoted += 1
                else:
                    kept += 1
            await self._session.commit()
        except Exception:
            logger.error(
                "join_apply_failed",
                series_id=str(series_id),
                novel_id=str(novel_id),
                exc_info=True,
            )
            await self._session.rollback()
            raise

        logger.info(
            "join_applied",
            series_id=str(series_id),
            novel_id=str(novel_id),
            promoted_to_canon=promoted,
            kept_as_overlay=kept,
        )
        return JoinResult(
            series_id=series_id,
            novel_id=novel_id,
            position=position,
            promoted_to_canon=promoted,
            kept_as_overlay=kept,
        )

    async def remove_novel(self, series_id: uuid.UUID, novel_id: uuid.UUID) -> None:
        """Remove a novel from a series — the inverse of :meth:`apply_join`.

        Clears ``series_id`` / ``series_position`` on the novel, returning it
        to standalone. Idempotent: a novel not currently in ``series_id`` is a
        no-op (still 204). Only the membership is cleared — KB scope
        adjustments on leave are intentionally out of scope here.

        Args:
            series_id: The series the novel should leave.
            novel_id: The novel to remove.

        Raises:
            NotFoundError: If the novel does not exist.
        """
        novel = await self._novel_repo.get(novel_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))
        if novel.series_id == series_id:
            await self._novel_repo.clear_series_membership(novel_id)
            await self._session.commit()
        logger.info(
            "novel_removed_from_series",
            series_id=str(series_id),
            novel_id=str(novel_id),
        )

    @staticmethod
    def _treatment_for(entry: NovelKBEntry, canon_empty: bool) -> JoinEntryTreatment:
        """Derive a JoinEntryTreatment for one novel entry under Policy alpha."""
        entity_type = entry.entity_type
        if canon_empty and entity_type in _CANON_TYPES:
            target_scope = "series"
            reason = f"Entity type '{entity_type}' defaults to Canon (Policy iii)"
        elif canon_empty and entity_type in _OVERLAY_TYPES:
            target_scope = "novel"
            reason = f"Entity type '{entity_type}' defaults to Novel-Overlay (Policy iii)"
        else:
            target_scope = "novel"
            reason = "Series-Canon is non-empty; new entries stay as Novel-Overlay (Policy alpha)"
        return JoinEntryTreatment(
            entry_id=entry.id,
            slug=entry.slug,
            entity_type=entity_type,
            current_scope="novel",
            target_scope=target_scope,
            reason=reason,
        )
