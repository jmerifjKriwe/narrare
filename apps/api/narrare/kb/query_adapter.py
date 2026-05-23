"""KB Query Service Adapter — verbindet KBAgent mit dem KB-Repository.

Wrapped KBRepositoryProtocol + RelationshipRepositoryProtocol
als KBQueryService für die Nutzung in Agents.

Siehe ADR-015 Phase 3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare.kb.models import KBEntry, KBRelationship


class KBQueryServiceAdapter:
    """Adapter: KBQueryService Protocol → Repository calls.

    Fills in novel_id and translates between agent-friendly
    signatures and repository signatures.
    """

    def __init__(
        self,
        repository: KBRepositoryProtocol,
        relationship_repo: RelationshipRepositoryProtocol,
        novel_id: uuid.UUID,
    ) -> None:
        self._repo = repository
        self._rel_repo = relationship_repo
        self._novel_id = novel_id

    async def search(
        self,
        query: str,
        *,
        entity_type: str | None = None,
    ) -> list[KBEntry]:
        entries, _total = await self._repo.search(
            self._novel_id,
            query,
            entity_type=entity_type,
            page_size=10,
        )
        return entries

    async def get_by_name(self, name: str) -> KBEntry | None:
        return await self._repo.get_by_name(self._novel_id, name)

    async def get_related(
        self,
        entity_id: uuid.UUID,
        *,
        relation_type: str | None = None,
    ) -> list[KBRelationship]:
        rels = await self._rel_repo.list_for_entry(
            entity_id,
            direction=None,
        )
        if relation_type:
            rels = [r for r in rels if r.rel_type == relation_type]
        return rels

    async def adjacency_map(
        self,
        entity_ids: set[uuid.UUID] | None = None,
    ) -> dict[str, set[str]]:
        """Build adjacency map for KB entities in the current novel.

        Args:
            entity_ids: Optional set of entity IDs to filter by.

        Returns:
            Dict mapping entity_id (str) → set of connected entity_ids (str).
        """
        return await self._rel_repo.get_adjacency_map(
            self._novel_id,
            entity_ids=entity_ids,
        )
