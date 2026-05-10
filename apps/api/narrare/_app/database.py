"""
Database engine and session factory.

SQLAlchemy async engine configured from settings.
All DB access goes through get_async_session dependency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from narrare._app.config import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


def _create_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.active_database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        echo=settings.db_echo,
        pool_pre_ping=True,
    )


# Module-level engine and session factory
# Re-created per test run via override_database_url()
_engine = _create_engine()
_async_session_factory = async_sessionmaker(
    bind=_engine,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    """
    FastAPI dependency that provides a database session.

    Commits on success, rolls back on exception.
    Use via: session: AsyncSession = Depends(get_async_session)
    """
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_engine() -> AsyncEngine:
    """Return the async engine (for migrations and health checks)."""
    return _engine
