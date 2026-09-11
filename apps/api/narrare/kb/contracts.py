"""Knowledge Base service contracts — Protocol definitions.

Defines the interfaces for KB entry and relationship operations.
Contracts are written before implementation (RULE-03).

The reusable KB-context surface (ADR-067 — :class:`KBContextBundle` value
type and :class:`KBContextProviderProtocol`) lives in the sibling
:mod:`narrare.kb.context_contracts` module (extracted to respect the 200-line
contracts file-size limit, RULE-04).

The relationship Protocols (:class:`RelationshipRepositoryProtocol`,
:class:`RelationshipServiceProtocol`) live in
:mod:`narrare.kb.contracts_relationships` (same RULE-04 split) and are
re-exported here so historical import sites stay stable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from narrare.kb.contracts_relationships import (
    RelationshipRepositoryProtocol,
    RelationshipServiceProtocol,
)

if TYPE_CHECKING:
    import uuid

    from narrare.kb.models import KBEntry
    from narrare.kb.schemas import (
        KBEntryCreate,
        KBEntryUpdate,
        ResolveReferencesResponse,
    )
    from narrare_core.kb.schemas.entry import NovelKBEntry, SeriesKBEntry

__all__ = [
    "KBRepositoryProtocol",
    "KBServiceProtocol",
    "RelationshipRepositoryProtocol",
    "RelationshipServiceProtocol",
]


@runtime_checkable
class KBRepositoryProtocol(Protocol):
    """Protocol for KB entry persistence operations."""

    async def create(self, entry: KBEntry) -> KBEntry: ...
    async def get_by_id(self, entry_id: uuid.UUID) -> KBEntry | None: ...
    async def get_by_slug(self, novel_id: uuid.UUID, slug: str) -> KBEntry | None: ...
    async def get_by_name(self, novel_id: uuid.UUID, name: str) -> KBEntry | None: ...
    async def search_by_name_prefix(
        self,
        novel_id: uuid.UUID,
        prefix: str,
        limit: int = 10,
    ) -> list[KBEntry]: ...
    async def list_entries(
        self,
        novel_id: uuid.UUID,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        review_status: str | None = None,
        page: int = 1,
        page_size: int = 50,
        include_deprecated: bool = False,
    ) -> tuple[list[KBEntry], int]: ...
    async def update(self, entry: KBEntry, data: dict[str, object]) -> KBEntry: ...
    async def delete(self, entry: KBEntry) -> None: ...
    async def search(
        self,
        novel_id: uuid.UUID,
        query: str,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
        include_deprecated: bool = False,
    ) -> tuple[list[KBEntry], int]: ...
    async def count_by_novel(self, novel_id: uuid.UUID) -> int: ...
    async def filter_ids_in_novel(
        self, novel_id: uuid.UUID, entry_ids: set[uuid.UUID]
    ) -> set[uuid.UUID]: ...
    async def find_canon_for_series(self, series_id: uuid.UUID) -> list[SeriesKBEntry]: ...
    async def find_canon_by_slug(self, series_id: uuid.UUID, slug: str) -> KBEntry | None: ...
    async def find_overlay_for_novel(self, novel_id: uuid.UUID) -> list[NovelKBEntry]: ...
    async def find_merged_for_novel(
        self, novel_id: uuid.UUID
    ) -> list[NovelKBEntry | SeriesKBEntry]: ...
    async def promote_to_canon(self, novel_id: uuid.UUID, entry_id: uuid.UUID) -> SeriesKBEntry: ...
    async def demote_to_overlay(
        self,
        series_id: uuid.UUID,
        entry_id: uuid.UUID,
        target_novel_id: uuid.UUID,
    ) -> NovelKBEntry: ...


@runtime_checkable
class KBServiceProtocol(Protocol):
    """Protocol for KB entry business logic."""

    async def create(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        data: KBEntryCreate,
    ) -> KBEntry: ...
    async def get(
        self, novel_id: uuid.UUID, entry_id: uuid.UUID, user_id: uuid.UUID
    ) -> KBEntry: ...
    async def list_entries(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        review_status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[KBEntry], int]: ...
    async def update(
        self,
        novel_id: uuid.UUID,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
        data: KBEntryUpdate,
    ) -> KBEntry: ...
    async def delete(
        self, novel_id: uuid.UUID, entry_id: uuid.UUID, user_id: uuid.UUID
    ) -> None: ...
    async def resolve_references(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        text: str,
    ) -> ResolveReferencesResponse: ...
    async def autocomplete(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        q: str,
        limit: int = 10,
    ) -> list[dict[str, str]]: ...
    async def search(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        query: str,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[KBEntry], int]: ...
