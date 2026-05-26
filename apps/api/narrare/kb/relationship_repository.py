"""KB relationship repository — DB queries only.

Handles persistence of ``KBRelationship`` edges between KB entries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import or_, select

from narrare._app.base_repository import BaseRepository
from narrare.kb.models import KBRelationship

if TYPE_CHECKING:
    import uuid


class RelationshipRepository(BaseRepository):
    """Persistence operations for KB relationships."""

    async def create(self, rel: KBRelationship) -> KBRelationship:
        """Persist a new relationship."""
        self._session.add(rel)
        await self._flush_and_refresh(rel)
        return rel

    async def get_by_id(self, rel_id: uuid.UUID) -> KBRelationship | None:
        """Fetch a single relationship by its primary key."""
        result = await self._session.execute(
            select(KBRelationship).where(KBRelationship.id == rel_id)
        )
        return result.scalar_one_or_none()

    async def list_for_entry(
        self,
        entry_id: uuid.UUID,
        direction: str | None = None,
    ) -> list[KBRelationship]:
        """List relationships for an entry.

        Args:
            entry_id: The entry to find relationships for.
            direction: "outgoing" (source), "incoming" (target),
                       or None for both.

        Returns:
            List of matching relationships.
        """
        if direction == "outgoing":
            condition = KBRelationship.source_id == entry_id
        elif direction == "incoming":
            condition = KBRelationship.target_id == entry_id
        else:
            condition = or_(
                KBRelationship.source_id == entry_id,
                KBRelationship.target_id == entry_id,
            )

        result = await self._session.execute(
            select(KBRelationship).where(condition).order_by(KBRelationship.created_at.desc())
        )
        return list(result.scalars())

    async def delete(self, rel: KBRelationship) -> None:
        """Delete a relationship."""
        await self._session.delete(rel)
        await self._flush()

    async def exists(self, source_id: uuid.UUID, target_id: uuid.UUID, rel_type: str) -> bool:
        """Check if a specific relationship already exists."""
        from sqlalchemy import func as sa_func

        result = await self._session.execute(
            select(sa_func.count())
            .select_from(KBRelationship)
            .where(
                KBRelationship.source_id == source_id,
                KBRelationship.target_id == target_id,
                KBRelationship.rel_type == rel_type,
            )
        )
        return result.scalar_one() > 0

    async def list_all_for_novel(
        self,
        novel_id: uuid.UUID,
    ) -> list[KBRelationship]:
        """List all relationships for a novel in a single query.

        Used by GraphService to build edges efficiently.

        Args:
            novel_id: The novel to query relationships for.

        Returns:
            List of all relationships for the novel.
        """
        from narrare.kb.models import KBEntry

        result = await self._session.execute(
            select(KBRelationship)
            .join(KBEntry, KBEntry.id == KBRelationship.source_id)
            .where(KBEntry.novel_id == novel_id)
            .order_by(KBRelationship.created_at.desc())
        )
        return list(result.scalars())

    async def get_adjacency_map(
        self,
        novel_id: uuid.UUID,
        entity_ids: set[uuid.UUID] | None = None,
    ) -> dict[str, set[str]]:
        """Build an entity_connections adjacency map from relationship edges.

        For each entity, finds all first-degree connected entities
        (both outgoing and incoming relationships).

        Args:
            novel_id: The novel to query relationships for.
            entity_ids: Optional set of entity IDs to filter by.
                When provided, only returns connections for these entities.
                When None, returns all relationships in the novel.

        Returns:
            Dict mapping entity_id (as str) → set of connected
            entity_ids (as str).
        """
        from narrare.kb.models import KBEntry

        query = (
            select(KBRelationship.source_id, KBRelationship.target_id)
            .join(KBEntry, KBEntry.id == KBRelationship.source_id)
            .where(KBEntry.novel_id == novel_id)
        )

        if entity_ids:
            query = query.where(
                or_(
                    KBRelationship.source_id.in_(entity_ids),
                    KBRelationship.target_id.in_(entity_ids),
                )
            )

        result = await self._session.execute(query)
        rows = result.all()

        adjacency: dict[str, set[str]] = {}
        for source_id, target_id in rows:
            src = str(source_id)
            tgt = str(target_id)
            adjacency.setdefault(src, set()).add(tgt)
            adjacency.setdefault(tgt, set()).add(src)

        return adjacency
