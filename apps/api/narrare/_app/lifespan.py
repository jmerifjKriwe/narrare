"""Application lifespan — startup and shutdown handlers."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI

logger = structlog.get_logger(__name__)


def bind_writing_session_singletons(app: FastAPI) -> None:
    """Bind ADR-052 writing-session lifecycle singletons on ``app.state``.

    The in-memory implementations are process-local by design. Multi-worker
    deployments must replace them with Redis-backed metadata plus an
    in-process live-task map per ADR-052 Review Trigger #1.
    """
    try:
        from narrare.writing._ws_cache import InMemorySessionCache
        from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
        from narrare.writing.ws_session_control_service import WritingSessionControlService
        from narrare_core.writing.session_manager import SessionManager
        from narrare_core.writing.session_turn_state import SessionTurnStateStore

        session_cache = InMemorySessionCache(max_entries=10_000)
        session_manager = SessionManager(cache=session_cache)
        turn_state = SessionTurnStateStore()
        active_turn_registry = ActiveTurnRegistry()
        control_service = WritingSessionControlService(
            session_manager=session_manager,
            turn_state=turn_state,
            registry=active_turn_registry,
        )

        app.state.session_cache = session_cache
        app.state.session_manager = session_manager
        app.state.turn_state = turn_state
        app.state.active_turn_registry = active_turn_registry
        app.state.writing_session_control_service = control_service
        logger.info("writing_session_singletons_bound")
    except Exception:
        logger.error("writing_session_singletons_bind_failed", exc_info=True)
        raise


async def _get_db_version(db_url: str) -> str | None:
    """Query the current Alembic revision from the database.

    Returns ``None`` if the ``alembic_version`` table does not exist yet
    (fresh database).
    """
    engine = create_async_engine(db_url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.fetchone()
            return row[0] if row else None
    except Exception:
        # Table doesn't exist yet — fresh database
        return None
    finally:
        await engine.dispose()


async def _run_pending_migrations() -> None:
    """Run pending Alembic migrations at startup.

    Ensures the database schema is always up to date before the app
    starts serving requests.  Fails fast with a clear log if migrations
    cannot be applied.
    """
    import asyncio
    import os

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://narrare:narrare@localhost:5432/narrare_dev",
    )

    # Resolve alembic script location relative to this file:
    # _app/lifespan.py → _app/ → narrare/ → apps/api/ → alembic/
    _alembic_dir = Path(__file__).resolve().parent.parent.parent / "alembic"

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(_alembic_dir))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Log current version before migration
    current = await _get_db_version(db_url)
    logger.info("db_schema_version", current_version=current or "(fresh database)")

    # Alembic's command.upgrade is synchronous — offload to a thread
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: command.upgrade(alembic_cfg, "head"))

    # Log version after migration
    new = await _get_db_version(db_url)
    if new != current:
        logger.info(
            "db_migrations_applied",
            from_version=current or "(none)",
            to_version=new,
        )
    else:
        logger.info("db_schema_up_to_date", version=new)


async def _run_stale_cleanup() -> int:
    """Run stale generation cleanup using a standalone DB session.

    Creates a short-lived session outside of the request lifecycle,
    instantiates ``GenerationRepository``, and calls ``cleanup_stale()``.

    Returns:
        Number of stale requests marked as failed.
    """
    from narrare._app.database import get_session_factory
    from narrare.writing.repository import GenerationRepository

    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            repo = GenerationRepository(session)
            count = await repo.cleanup_stale()
            await session.commit()
            return count
        except Exception:
            await session.rollback()
            raise


async def _periodic_cleanup_loop() -> None:
    """Periodically clean up stale generation requests every 5 minutes.

    Runs indefinitely until cancelled.  Each iteration handles its own
    errors so a single failure does not stop the loop.
    """
    while True:
        await asyncio.sleep(300)
        try:
            count = await _run_stale_cleanup()
            if count > 0:
                logger.info("periodic_cleanup", stale_cleaned=count)
        except Exception:
            logger.warning("periodic_cleanup_failed", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """
    FastAPI lifespan context manager.

    Startup: configure logging, run migrations, register wiki listeners,
    bind writing-session singletons.
    Shutdown: cancel periodic cleanup, dispose database engine.
    """
    # --- Startup ---
    _configure_logging()
    logger.info("narrare_api_starting")

    from narrare._app.config import get_settings
    from narrare_core.settings import get_core_settings

    settings = get_settings()

    # NOTE (ADR-071 §5): the workaround that synced ``settings.encryption_key``
    # into ``os.environ`` for ``core/crypto.py`` to re-read has been REMOVED.
    # ``core/crypto.py`` now reads ``get_core_settings().encryption_key``
    # directly. The env-var bridge was an architectural-discipline §4 violation
    # (bypassing an abstraction "just to make it work") and is no longer needed.

    # Log E2E test mode if active. ``NARRARE_E2E_TEST`` is owned by CoreSettings
    # (ADR-071 §3) — read via get_core_settings(), not os.environ.
    if get_core_settings().e2e_test:
        logger.info(
            "e2e_test_mode_active",
            message="ALL LLM providers returning TestModel — no real API calls will be made.",
        )

    # Auto-migrate database on startup — skip in test environment where
    # the test infrastructure (conftest check_db_available) handles this.
    if not settings.is_test:
        try:
            await _run_pending_migrations()
        except Exception:
            logger.exception("db_migration_failed")
            raise

    # Wiki event listeners — register typed handlers on a global EventPublisher
    try:
        from narrare.events.publisher import EventPublisher
        from narrare.wiki.dependencies import build_core_wiki_service, make_system_wiki_factory
        from narrare.wiki.listeners import WikiEventListener

        core_wiki_service = await build_core_wiki_service()
        system_factory = make_system_wiki_factory(core_wiki_service)
        listener = WikiEventListener(wiki_service_factory=system_factory)

        publisher = EventPublisher()
        publisher.subscribe("kb.entry.updated", listener.on_kb_entry_updated)
        publisher.subscribe("chapter.finalized", listener.on_chapter_finalized)
        publisher.subscribe("wiki.prompt.changed", listener.on_wiki_prompt_changed)

        # Store on app.state for access from other modules if needed
        app.state.wiki_event_publisher = publisher
        logger.info("wiki_event_listeners_registered")
    except Exception:
        logger.warning("wiki_listeners_init_failed", exc_info=True)

    bind_writing_session_singletons(app)

    # Startup cleanup: remove stale generation requests — skip in test
    # environment (no real data to clean, and it uses the module-level engine).
    if not settings.is_test:
        try:
            count = await _run_stale_cleanup()
            if count > 0:
                logger.info("startup_cleanup", stale_cleaned=count)
        except Exception:
            logger.warning("startup_cleanup_failed", exc_info=True)

    # Periodic background task — skip in test environment (no real data,
    # and avoids creating long-lived asyncio tasks per test).
    cleanup_task: asyncio.Task[None] | None = None
    if not settings.is_test:
        cleanup_task = asyncio.create_task(_periodic_cleanup_loop())

    logger.info("narrare_api_ready")

    yield

    # --- Shutdown ---
    logger.info("narrare_api_stopping")

    # Cancel periodic cleanup task
    if cleanup_task is not None:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task
        logger.info("periodic_cleanup_cancelled")

    # Drain in-flight background tasks (ADR-080 in-process dispatch).  They
    # must be cancelled and awaited BEFORE the database engine is disposed
    # so no background coroutine touches a disposed pool.  Cancellation is
    # intentional — logged at info by the drain, never as an error.
    # Skip in test environment: unit tests manage their own tasks and there
    # is no engine to dispose (mirrors the database-dispose guard below).
    if not settings.is_test:
        try:
            from narrare._app.inflight import drain_inflight_tasks

            await drain_inflight_tasks()
        except Exception:
            logger.warning("inflight_drain_failed", exc_info=True)

    # Database engine shutdown — close all pooled connections.
    # Skip in test environment: the test infrastructure handles cleanup
    # via the session-scoped _dispose_module_engine fixture, and per-test
    # disposal creates race conditions with asyncpg connection cleanup.
    if not settings.is_test:
        try:
            from narrare._app.database import dispose_database

            await dispose_database()
            logger.info("database_engine_disposed_lifespan")
        except Exception:
            logger.warning("database_dispose_failed", exc_info=True)

    logger.info("narrare_api_stopped")


def _configure_logging() -> None:
    """Configure structlog for the application."""
    from narrare._app.logging import configure_logging

    configure_logging()
