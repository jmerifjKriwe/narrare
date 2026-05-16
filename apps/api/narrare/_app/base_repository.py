"""Base repository — provides shared async session utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare._app.database import Base


class BaseRepository:
    """Base class for all repositories.

    Provides `_flush_and_refresh()` which atomically flushes changes
    and refreshes the entity to load server-default columns
    (created_at, updated_at, etc.) — preventing MissingGreenlet errors.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _flush_and_refresh(self, entity: Base) -> None:
        """Flush changes and refresh entity from DB.

        Use this instead of separate flush() + refresh() calls.
        The refresh is essential because server_default columns
        (created_at, updated_at) are only populated by the DB,
        not by the ORM. Without refresh, serializing the entity
        via Pydantic triggers lazy-load → MissingGreenlet.
        """
        await self._session.flush()
        await self._session.refresh(entity)

    async def _flush(self) -> None:
        """Flush without refresh — for operations that don't return entities."""
        await self._session.flush()
