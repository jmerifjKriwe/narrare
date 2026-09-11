"""Knowledge Base relationship contracts — Protocol definitions.

Extracted from ``contracts.py`` (RULE-04 split: the entry-domain and
relationship-domain contracts share one historical module; the PR-wave
``filter_ids_in_novel`` addition pushed the module over the 200-line
contract file-size limit). One responsibility (RULE-06): relationship
interfaces for KB persistence and business logic.

The canonical import sites remain unchanged — ``narrare.kb.contracts``
re-exports both Protocols (same stable-alias pattern as
``narrare.kb._novel_gate``).

Contracts are written before implementation (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.kb.models import KBRelationship
    from narrare.kb.relationship_repository import RelationshipEdgeRow
    from narrare.kb.schemas import KBRelationshipCreate


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
