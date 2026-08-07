"""KBScopeService — business logic for the promote/demote scope toggle.

Series Foundation Spec 1, Slice 3 Task 3.7.

Thin ownership + delegation layer over the :class:`KBRepository` scope mutations
(Task 2.2). Ownership is verified at the scope-appropriate boundary before any
mutation (C1 / IDOR fix):

* **Promote** (overlay → canon) → NOVEL ownership (the ``novel_id`` promoted).
* **Demote** (canon → overlay) → SERIES ownership (the canon's series) AND
  target-novel ownership.

A missing or not-owned resource surfaces as ``ForbiddenError`` (HTTP 403,
anti-enumeration — never ``NotFoundError`` / 404). The repository raises
``ConflictError`` directly on a scope-invariant violation or the Canon-integrity
guard (D4) — the service re-raises it unchanged (RULE-06: no error-translation
logic here; the global ``NarrareError`` handler maps it to HTTP 409).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.shared.errors import ForbiddenError

if TYPE_CHECKING:
    import uuid

    from narrare.kb.scope_contracts import KBScopeMutationProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare_core.kb.schemas.entry import NovelKBEntry, SeriesKBEntry

logger = structlog.get_logger(__name__)


class KBScopeService:
    """Business logic for toggling a KB entry's scope (Canon ↔ Overlay).

    Depends solely on injected repositories — no LLM, no HTTP, no raw SQL
    (RULE-06). Ownership is enforced here; invariant/guard conflicts are raised
    by the repository and surface unchanged.
    """

    def __init__(
        self,
        kb_repo: KBScopeMutationProtocol,
        novel_repo: NovelRepositoryProtocol,
        series_repo: SeriesRepositoryProtocol,
    ) -> None:
        self._kb_repo = kb_repo
        self._novel_repo = novel_repo
        self._series_repo = series_repo

    # -- ownership -------------------------------------------------------

    async def _verify_novel_ownership(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Raise ``ForbiddenError`` (403) if the novel is missing/not owned."""
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise ForbiddenError("You do not have access to this novel")

    async def _verify_series_ownership(self, series_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Raise ``ForbiddenError`` (403) if the series is missing/not owned.

        Anti-enumeration: a missing series and a not-owned series both surface
        as 403 (mirrors ``KBCanonService._verify_series_ownership``).
        """
        series = await self._series_repo.get(series_id)
        if series is None or series.user_id != user_id:
            raise ForbiddenError("You do not have access to this series")

    # -- scope toggle ----------------------------------------------------

    async def promote_to_canon(
        self,
        novel_id: uuid.UUID,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> SeriesKBEntry:
        """Promote a Novel-Overlay entry to Series-Canon.

        Verifies NOVEL ownership first. The repository raises ``ConflictError``
        (HTTP 409) if the entry is not an overlay of ``novel_id`` or the novel is
        not in a series (scope invariant violation).

        Raises:
            ForbiddenError: Novel missing or not owned by ``user_id`` (403).
            ConflictError: Scope invariant violation (409).
        """
        await self._verify_novel_ownership(novel_id, user_id)
        promoted = await self._kb_repo.promote_to_canon(novel_id, entry_id)
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
        user_id: uuid.UUID,
    ) -> NovelKBEntry:
        """Demote a Series-Canon entry to a Novel-Overlay for ``target_novel_id``.

        Verifies SERIES ownership AND target-novel ownership first. The repository
        raises ``ConflictError`` (HTTP 409) if the entry is not canon of
        ``series_id`` (scope invariant) OR another member novel relies on this
        Canon entry and would lose it from its merged view (Canon-integrity guard,
        D4).

        Raises:
            ForbiddenError: Series or target novel missing / not owned (403).
            ConflictError: Scope invariant or Canon-integrity guard violation (409).
        """
        await self._verify_series_ownership(series_id, user_id)
        await self._verify_novel_ownership(target_novel_id, user_id)
        demoted = await self._kb_repo.demote_to_overlay(series_id, entry_id, target_novel_id)
        logger.info(
            "kb_entry_demoted_to_overlay",
            entry_id=str(entry_id),
            series_id=str(series_id),
            target_novel_id=str(target_novel_id),
        )
        return demoted
