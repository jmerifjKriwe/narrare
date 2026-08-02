"""KB Canon + Scope service contracts — Protocol definitions (RULE-03).

Extracted from ``contracts.py`` to respect the 200-line contracts file-size
limit (RULE-04), mirroring the ``context_contracts.py`` extraction. Holds the
*service* Protocols for the Canon/Overlay scope surface; the repository
Protocol (``KBRepositoryProtocol``, including ``promote_to_canon`` /
``demote_to_overlay`` / ``find_canon_for_series``) stays in ``contracts.py``.

These formalise two services that previously had NO Protocol (I-A1 / RULE-03
gap closed): :class:`~narrare.kb.canon_service.KBCanonService` and
:class:`~narrare.kb.scope_service.KBScopeService`.

Ownership contract (C1 / IDOR fix — mirrors ``KBCanonService._verify_series_ownership``
and ``KBService._verify_novel_ownership``): every method takes ``user_id`` and
verifies ownership at the scope-appropriate boundary before any read/mutation:

* **Canon CRUD** → SERIES ownership (the entry's ``series_id``).
* **Promote** (overlay → canon) → NOVEL ownership (the ``novel_id`` being promoted).
* **Demote** (canon → overlay) → SERIES ownership (the canon's series) AND
  target-novel ownership.

A missing or not-owned resource surfaces as ``ForbiddenError`` (HTTP 403,
anti-enumeration — never ``NotFoundError`` / 404).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.kb.schemas import KBEntryCreate, KBEntryUpdate
    from narrare_core.kb.schemas.entry import NovelKBEntry, SeriesKBEntry


@runtime_checkable
class KBScopeMutationProtocol(Protocol):
    """Focused KB-repo surface consumed by :class:`KBScopeService`.

    The scope toggle uses only ``promote_to_canon`` / ``demote_to_overlay``;
    declaring this focused Protocol (Interface Segregation) lets a test fake
    implement just these two methods without ``# type: ignore`` (RULE-23). The
    concrete :class:`~narrare.kb.repository.KBRepository` satisfies it.
    """

    async def promote_to_canon(self, novel_id: uuid.UUID, entry_id: uuid.UUID) -> SeriesKBEntry: ...

    async def demote_to_overlay(
        self,
        series_id: uuid.UUID,
        entry_id: uuid.UUID,
        target_novel_id: uuid.UUID,
    ) -> NovelKBEntry: ...


@runtime_checkable
class KBCanonServiceProtocol(Protocol):
    """Protocol for Series-Canon KB CRUD (``novel_id IS NULL``).

    Formalises :class:`~narrare.kb.canon_service.KBCanonService`. Every method
    verifies SERIES ownership (``ForbiddenError`` 403 on missing/not-owned),
    mirroring the existing service implementation.
    """

    async def list_canon(self, series_id: uuid.UUID, user_id: uuid.UUID) -> list[SeriesKBEntry]: ...

    async def get_canon(
        self, series_id: uuid.UUID, entry_id: uuid.UUID, user_id: uuid.UUID
    ) -> SeriesKBEntry: ...

    async def create_canon(
        self,
        series_id: uuid.UUID,
        user_id: uuid.UUID,
        data: KBEntryCreate,
    ) -> SeriesKBEntry: ...

    async def update_canon(
        self,
        series_id: uuid.UUID,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
        data: KBEntryUpdate,
    ) -> SeriesKBEntry: ...

    async def delete_canon(
        self, series_id: uuid.UUID, entry_id: uuid.UUID, user_id: uuid.UUID
    ) -> None: ...


@runtime_checkable
class KBScopeServiceProtocol(Protocol):
    """Protocol for the promote/demote scope toggle (Canon ↔ Overlay).

    Formalises :class:`~narrare.kb.scope_service.KBScopeService`. Ownership:

    * ``promote_to_canon`` verifies NOVEL ownership (the overlay's novel).
    * ``demote_to_overlay`` verifies SERIES ownership (the canon's series) AND
      target-novel ownership, and enforces the Canon-integrity guard
      (SERIES-001 §151-152): a 409 ``ConflictError`` is raised if demoting would
      remove the Canon entry from the merged view of any OTHER member novel that
      relies on it as Canon (no silent breakage — RULE-11 / D4 decision).
    """

    async def promote_to_canon(
        self,
        novel_id: uuid.UUID,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> SeriesKBEntry:
        """Promote a Novel-Overlay to Series-Canon.

        Raises:
            ForbiddenError: Novel missing or not owned by ``user_id`` (403).
            ConflictError: Entry is not an overlay of ``novel_id``, or the novel
                is not in a series (scope invariant violation → 409).
        """
        ...

    async def demote_to_overlay(
        self,
        series_id: uuid.UUID,
        entry_id: uuid.UUID,
        target_novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> NovelKBEntry:
        """Demote a Series-Canon entry to a Novel-Overlay for ``target_novel_id``.

        Clears ``series_id`` on the demoted overlay (derivable from
        ``novel.series_id`` — ADR-075 §D6: overlays never persist ``series_id``).

        Raises:
            ForbiddenError: Series or target novel missing / not owned by
                ``user_id`` (403).
            ConflictError: Entry is not canon of ``series_id`` (scope invariant,
                409), OR another member novel relies on this Canon entry and
                would lose it from its merged view (Canon-integrity guard, 409).
        """
        ...
