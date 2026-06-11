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
from sqlalchemy.pool import NullPool

from narrare._app.config import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


def _create_engine() -> AsyncEngine:
    settings = get_settings()
    if settings.is_test:
        # NullPool prevents connection leaks in tests — each checkout creates
        # a fresh connection that is immediately closed on checkin. This avoids
        # the dispose/create cycles that accumulate unclosed connections across
        # hundreds of lifespan start/stop cycles per test session.
        return create_async_engine(
            settings.active_database_url,
            echo=settings.db_echo,
            poolclass=NullPool,
        )
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


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the module-level session factory for standalone sessions.

    Used by infrastructure code (lifespan startup cleanup, background tasks)
    that needs a DB session outside the FastAPI request lifecycle.
    Prefer ``get_async_session`` for normal request handling.
    """
    return _async_session_factory


async def get_engine() -> AsyncEngine:
    """Return the async engine (for migrations and health checks)."""
    return _engine


async def dispose_database() -> None:
    """Dispose the module-level engine and close all pooled connections.

    Called during application shutdown to ensure asyncpg connections are
    properly closed before the event loop stops.  Without this, connections
    are garbage-collected with unawaited ``_cancel`` coroutines that
    produce ``PytestUnraisableExceptionWarning`` under ``filterwarnings=["error"]``.
    """
    import structlog

    logger = structlog.get_logger(__name__)
    await _engine.dispose()
    logger.info("database_engine_disposed")
