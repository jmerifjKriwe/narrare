"""Knowledge Base service contracts — Protocol definitions.

Defines the interfaces for KB entry and relationship operations.
Contracts are written before implementation (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.kb.models import KBEntry, KBRelationship
    from narrare.kb.relationship_repository import RelationshipEdgeRow
    from narrare.kb.schemas import (
        KBEntryCreate,
        KBEntryUpdate,
        KBRelationshipCreate,
        ResolveReferencesResponse,
    )


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
        page: int = 1,
        page_size: int = 50,
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
    ) -> tuple[list[KBEntry], int]: ...
    async def count_by_novel(self, novel_id: uuid.UUID) -> int: ...


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


@runtime_checkable
class RelationshipRepositoryProtocol(Protocol):
    """Protocol for KB relationship persistence operations."""

    async def create(self, rel: KBRelationship) -> KBRelationship: ...
    async def get_by_id(self, rel_id: uuid.UUID) -> KBRelationship | None: ...
    async def list_for_entry(
        self,
        entry_id: uuid.UUID,
        direction: str | None = None,
    ) -> list[KBRelationship]: ...
    async def delete(self, rel: KBRelationship) -> None: ...
    async def exists(self, source_id: uuid.UUID, target_id: uuid.UUID, rel_type: str) -> bool: ...
    async def list_all_for_novel(
        self,
        novel_id: uuid.UUID,
    ) -> list[KBRelationship]:
        """List all relationships for a novel in a single query.

        Used by GraphService to build edges efficiently.
        """
        ...

    async def get_adjacency_map(
        self,
        novel_id: uuid.UUID,
        entity_ids: set[uuid.UUID] | None = None,
    ) -> dict[str, set[str]]: ...

    async def get_relationships_with_names(
        self,
        novel_id: uuid.UUID,
        entity_ids: set[uuid.UUID] | None = None,
    ) -> list[RelationshipEdgeRow]:
        """Fetch relationship edges with entity names.

        Returns list of RelationshipEdgeRow namedtuples.
        """
        ...


@runtime_checkable
class RelationshipServiceProtocol(Protocol):
    """Protocol for KB relationship business logic."""

    async def create(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        data: KBRelationshipCreate,
    ) -> KBRelationship: ...
    async def list_for_entry(
        self,
        novel_id: uuid.UUID,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
        direction: str | None = None,
    ) -> list[KBRelationship]: ...
    async def delete(self, novel_id: uuid.UUID, rel_id: uuid.UUID, user_id: uuid.UUID) -> None: ...
    def get_inverse_suggestion(self, rel_type: str) -> str | None: ...
