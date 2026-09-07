"""KB entry repository — DB queries only.

Handles persistence of ``KBEntry`` entities with filtering,
pagination, and text search (ILIKE-based).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select

from narrare.kb.models import KBEntry
from narrare.kb.scope_repository import KBScopeRepository

if TYPE_CHECKING:
    import uuid


class KBRepository(KBScopeRepository):
    """Persistence operations for KB entries."""

    async def create(self, entry: KBEntry) -> KBEntry:
        """Persist a new KB entry."""
        self._session.add(entry)
        await self._flush_and_refresh(entry)
        return entry

    async def get_by_id(self, entry_id: uuid.UUID) -> KBEntry | None:
        """Fetch a single entry by its primary key."""
        result = await self._session.execute(select(KBEntry).where(KBEntry.id == entry_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, novel_id: uuid.UUID, slug: str) -> KBEntry | None:
        """Fetch an entry by novel and slug (for uniqueness checks)."""
        result = await self._session.execute(
            select(KBEntry).where(
                KBEntry.novel_id == novel_id,
                KBEntry.slug == slug,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, novel_id: uuid.UUID, name: str) -> KBEntry | None:
        """Find an entry by exact name match within a novel (case-insensitive)."""
        result = await self._session.execute(
            select(KBEntry).where(
                KBEntry.novel_id == novel_id,
                KBEntry.name.ilike(name),
            )
        )
        return result.scalar_one_or_none()

    async def search_by_name_prefix(
        self,
        novel_id: uuid.UUID,
        prefix: str,
        limit: int = 10,
    ) -> list[KBEntry]:
        """Search entries by name prefix (for auto-complete)."""
        result = await self._session.execute(
            select(KBEntry)
            .where(
                KBEntry.novel_id == novel_id,
                KBEntry.name.ilike(f"{prefix}%"),
            )
            .order_by(KBEntry.name)
            .limit(limit)
        )
        return list(result.scalars())

    async def list_entries(
        self,
        novel_id: uuid.UUID,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        review_status: str | None = None,
        page: int = 1,
        page_size: int = 50,
        include_deprecated: bool = False,
    ) -> tuple[list[KBEntry], int]:
        """List entries for a novel with optional filters and pagination.

        Deprecated entries (ADR-085 merge losers) are non-authoritative
        (spec §6.7/§9(c)): excluded — from rows AND total count — unless
        explicitly requested via ``include_deprecated``.
        """
        query = select(KBEntry).where(KBEntry.novel_id == novel_id)
        count_query = select(func.count()).select_from(KBEntry).where(KBEntry.novel_id == novel_id)

        if not include_deprecated:
            query = query.where(KBEntry.status != "deprecated")
            count_query = count_query.where(KBEntry.status != "deprecated")

        if entity_type is not None:
            query = query.where(KBEntry.entity_type == entity_type)
            count_query = count_query.where(KBEntry.entity_type == entity_type)

        if tags:
            query = query.where(KBEntry.tags.contains(tags))
            count_query = count_query.where(KBEntry.tags.contains(tags))

        if review_status is not None:
            query = query.where(KBEntry.review_status == review_status)
            count_query = count_query.where(KBEntry.review_status == review_status)

        # Total count
        total_result = await self._session.execute(count_query)
        total = total_result.scalar_one()

        # Paginated results
        query = query.order_by(KBEntry.name)
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self._session.execute(query)
        entries = list(result.scalars())

        return entries, total

    async def update(self, entry: KBEntry, data: dict[str, object]) -> KBEntry:
        """Update fields on an existing entry."""
        for field, value in data.items():
            setattr(entry, field, value)
        await self._flush_and_refresh(entry)
        return entry

    async def delete(self, entry: KBEntry) -> None:
        """Delete an entry from the database."""
        await self._session.delete(entry)
        await self._flush()

    async def search(
        self,
        novel_id: uuid.UUID,
        query: str,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
        include_deprecated: bool = False,
    ) -> tuple[list[KBEntry], int]:
        """Search entries by name and body using ILIKE.

        Deprecated entries are excluded (rows AND count) unless
        explicitly requested (spec §6.7/§9(c) visibility policy).
        """
        pattern = f"%{query}%"
        search_filter = or_(
            KBEntry.name.ilike(pattern),
            KBEntry.body.ilike(pattern),
        )

        base = select(KBEntry).where(KBEntry.novel_id == novel_id, search_filter)
        count_base = (
            select(func.count())
            .select_from(KBEntry)
            .where(KBEntry.novel_id == novel_id, search_filter)
        )

        if not include_deprecated:
            base = base.where(KBEntry.status != "deprecated")
            count_base = count_base.where(KBEntry.status != "deprecated")

        if entity_type is not None:
            base = base.where(KBEntry.entity_type == entity_type)
            count_base = count_base.where(KBEntry.entity_type == entity_type)

        if tags:
            base = base.where(KBEntry.tags.contains(tags))
            count_base = count_base.where(KBEntry.tags.contains(tags))

        total_result = await self._session.execute(count_base)
        total = total_result.scalar_one()

        result = await self._session.execute(
            base.order_by(KBEntry.name).offset((page - 1) * page_size).limit(page_size)
        )
        entries = list(result.scalars())

        return entries, total

    async def count_by_novel(self, novel_id: uuid.UUID) -> int:
        """Count total entries for a novel."""
        result = await self._session.execute(
            select(func.count()).select_from(KBEntry).where(KBEntry.novel_id == novel_id)
        )
        return result.scalar_one()
