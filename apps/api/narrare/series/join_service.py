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
from sqlalchemy.exc import IntegrityError

from narrare.series._join_errors import map_join_integrity_error
from narrare.series.schemas import JoinEntryTreatment, JoinPreview, JoinResult
from narrare_core.shared.errors import ConflictError, ForbiddenError

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.novels.models import Novel
    from narrare.series.join_contracts import SeriesJoinRepositoryProtocol
    from narrare_core.kb.schemas.entry import NovelKBEntry
    from narrare_core.series.schemas import Series

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
        series_repo: SeriesJoinRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
        kb_repo: KBRepositoryProtocol,
    ) -> None:
        self._session = session
        # ``series_repo`` verifies SERIES ownership (C1 / IDOR fix) and detaches
        # a leaving novel's KB rows on remove (T7/D6).
        self._series_repo = series_repo
        self._novel_repo = novel_repo
        self._kb_repo = kb_repo

    # -- ownership -------------------------------------------------------

    async def _verify_series_ownership(self, series_id: uuid.UUID, user_id: uuid.UUID) -> Series:
        """Load the series and verify the caller owns it (anti-enumeration 403).

        Mirrors ``KBCanonService._verify_series_ownership``: a missing or
        not-owned series surfaces as ``ForbiddenError`` (never 404).
        """
        series = await self._series_repo.get(series_id)
        if series is None or series.user_id != user_id:
            raise ForbiddenError("You do not have access to this series")
        return series

    async def _verify_join_access(
        self, series_id: uuid.UUID, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[Series, Novel]:
        """Verify the caller owns BOTH the series and the novel (C1 fix).

        Returns the loaded ``(series, novel)`` so callers avoid a second fetch.
        Raises ``ForbiddenError`` (403, anti-enumeration) on a missing/not-owned
        series or novel.
        """
        series = await self._verify_series_ownership(series_id, user_id)
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise ForbiddenError("You do not have access to this novel")
        return series, novel

    async def preview_join(
        self,
        series_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> JoinPreview:
        """Compute per-entry treatments without mutating state.

        Args:
            series_id: The series the novel would join.
            novel_id: The novel joining the series.
            user_id: The caller (ownership of BOTH series + novel verified).

        Raises:
            ForbiddenError: Series or novel missing / not owned by ``user_id``.
            NovelAlreadyInSeriesError: If the novel is already in another series.
        """
        _, novel = await self._verify_join_access(series_id, novel_id, user_id)
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
        self,
        series_id: uuid.UUID,
        novel_id: uuid.UUID,
        position: int,
        user_id: uuid.UUID,
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
            user_id: The caller (ownership of BOTH series + novel verified).

        Raises:
            ForbiddenError: Series or novel missing / not owned by ``user_id``.
            NovelAlreadyInSeriesError: If the novel is already in another series.
            ConflictError: Position/slug conflicts (HTTP 409).
            NotFoundError: Series vanished in a commit race (HTTP 404).
        """
        # Authoritative: re-derive treatments from current state. Ownership +
        # the same-owner invariant are verified up front (before the
        # transaction so neither commit nor rollback is touched on rejection).
        series, novel = await self._verify_join_access(series_id, novel_id, user_id)
        if novel.series_id is not None and novel.series_id != series_id:
            raise NovelAlreadyInSeriesError(novel_id, novel.series_id)
        # Defense-in-depth (Q2): per-resource ownership is verified above, so
        # ``novel.user_id == series.user_id`` holds transitively. Assert it
        # explicitly so a future refactor that loosens ownership fails loudly
        # rather than silently joining a cross-owner novel into a series.
        if novel.user_id != series.user_id:
            raise ConflictError("Novel and series must belong to the same user")

        preview = await self.preview_join(series_id, novel_id, user_id)

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
        except IntegrityError as exc:
            logger.warning(
                "join_apply_integrity_conflict",
                series_id=str(series_id),
                novel_id=str(novel_id),
                error=str(exc),
            )
            await self._session.rollback()
            raise map_join_integrity_error(exc, series_id) from exc
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

    async def remove_novel(
        self,
        series_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Remove a novel from a series — the inverse of :meth:`apply_join`.

        Clears ``series_id`` / ``series_position`` on the novel (→ standalone)
        and detaches the leaving novel's overlay KB ``series_id`` (T7/D6 — a
        no-op in the post-D6 steady state, defence-in-depth for legacy rows).
        Idempotent: a novel not currently in ``series_id`` is a no-op (still 204).

        Args:
            series_id: The series the novel should leave.
            novel_id: The novel to remove.
            user_id: The caller (ownership of BOTH series + novel verified).

        Raises:
            ForbiddenError: Series or novel missing / not owned by ``user_id``.
        """
        await self._verify_series_ownership(series_id, user_id)
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise ForbiddenError("You do not have access to this novel")
        if novel.series_id == series_id:
            await self._novel_repo.clear_series_membership(novel_id)
            # Detach the leaving novel's overlay KB rows from the series (T7/D6).
            await self._series_repo.detach_overlay_series_id(novel_id, series_id)
            await self._session.commit()
        logger.info(
            "novel_removed_from_series",
            series_id=str(series_id),
            novel_id=str(novel_id),
        )

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _treatment_for(entry: NovelKBEntry, canon_empty: bool) -> JoinEntryTreatment:
        """Derive a JoinEntryTreatment for one novel entry under Policy alpha."""
        entity_type = entry.entity_type
        if canon_empty and entity_type in _CANON_TYPES:
            target_scope = "series"
            reason_code = "entity_default_canon"
            reason = f"Entity type '{entity_type}' defaults to Canon (Policy iii)"
        elif canon_empty and entity_type in _OVERLAY_TYPES:
            target_scope = "novel"
            reason_code = "entity_default_overlay"
            reason = f"Entity type '{entity_type}' defaults to Novel-Overlay (Policy iii)"
        else:
            target_scope = "novel"
            reason_code = "canon_nonempty_overlay"
            reason = "Series-Canon is non-empty; new entries stay as Novel-Overlay (Policy alpha)"
        return JoinEntryTreatment(
            entry_id=entry.id,
            slug=entry.slug,
            entity_type=entity_type,
            current_scope="novel",
            target_scope=target_scope,
            reason_code=reason_code,
            reason=reason,
        )
