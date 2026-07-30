"""KBScopeService — business logic for the promote/demote scope toggle.

Series Foundation Spec 1, Slice 3 Task 3.7.

Thin wrapper over the :class:`KBRepository` scope mutations (Task 2.2). The
only business logic here is translating the repository's invariant-violation
``ValueError`` into a domain ``ConflictError`` so the global ``NarrareError``
handler maps it to HTTP 409 (RULE-06: the router stays free of error-
translation logic; RULE-11: external exceptions are wrapped at the service
boundary with the original chained as ``__cause__``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.shared.errors import ConflictError

if TYPE_CHECKING:
    import uuid

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare_core.kb.schemas.entry import NovelKBEntry, SeriesKBEntry

logger = structlog.get_logger(__name__)


class KBScopeService:
    """Business logic for toggling a KB entry's scope (Canon ↔ Overlay).

    Depends solely on the repository scope surface — no LLM, no HTTP, no
    raw SQL (RULE-06). All dependencies are injected via ``__init__``.
    """

    def __init__(self, kb_repo: KBRepositoryProtocol) -> None:
        self._kb_repo = kb_repo

    async def promote_to_canon(self, novel_id: uuid.UUID, entry_id: uuid.UUID) -> SeriesKBEntry:
        """Promote a Novel-Overlay entry to Series-Canon.

        Args:
            novel_id: The novel whose overlay entry is being promoted.
            entry_id: The overlay entry to promote.

        Returns:
            The promoted entry as a Series-Canon value object.

        Raises:
            ConflictError: The entry is not an overlay of ``novel_id``, or the
                novel is not in a series (scope invariant violation → HTTP 409).
        """
        try:
            promoted = await self._kb_repo.promote_to_canon(novel_id, entry_id)
        except ValueError as exc:
            logger.warning(
                "kb_promote_rejected",
                novel_id=str(novel_id),
                entry_id=str(entry_id),
                reason=str(exc),
            )
            raise ConflictError(str(exc)) from exc

        logger.info(
            "kb_entry_promoted_to_canon",
            entry_id=str(entry_id),
            novel_id=str(novel_id),
            series_id=str(promoted.series_id),
        )
        return promoted

    async def demote_to_overlay(
        self,
        series_id: uuid.UUID,
        entry_id: uuid.UUID,
        target_novel_id: uuid.UUID,
    ) -> NovelKBEntry:
        """Demote a Series-Canon entry to a Novel-Overlay for ``target_novel_id``.

        Args:
            series_id: The series whose canon entry is being demoted.
            entry_id: The canon entry to demote.
            target_novel_id: The novel the entry becomes an overlay of.

        Returns:
            The demoted entry as a Novel-Overlay value object.

        Raises:
            ConflictError: The entry is not canon of ``series_id`` (scope
                invariant violation → HTTP 409).
        """
        try:
            demoted = await self._kb_repo.demote_to_overlay(series_id, entry_id, target_novel_id)
        except ValueError as exc:
            logger.warning(
                "kb_demote_rejected",
                series_id=str(series_id),
                entry_id=str(entry_id),
                target_novel_id=str(target_novel_id),
                reason=str(exc),
            )
            raise ConflictError(str(exc)) from exc

        logger.info(
            "kb_entry_demoted_to_overlay",
            entry_id=str(entry_id),
            series_id=str(series_id),
            target_novel_id=str(target_novel_id),
        )
        return demoted
