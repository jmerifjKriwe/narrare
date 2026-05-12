"""Application lifespan — startup and shutdown handlers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI

logger = structlog.get_logger(__name__)


async def _init_rate_limiter() -> None:
    """Initialize fastapi-limiter with Redis backend.

    Gracefully degrades if Redis is unavailable — requests proceed without limits.
    """
    try:
        import redis.asyncio as aioredis  # type: ignore[import-untyped]
        from fastapi_limiter import FastAPILimiter  # type: ignore[import-untyped]

        from narrare._app.config import get_settings

        settings = get_settings()
        redis_connection = aioredis.from_url(settings.redis_url)
        await FastAPILimiter.init(redis_connection)  # type: ignore[attr-defined]
        logger.info("rate_limiter_initialized")
    except Exception:
        logger.warning("rate_limiter_init_failed", exc_info=True)


async def _shutdown_rate_limiter() -> None:
    """Shut down fastapi-limiter, closing the Redis connection."""
    try:
        from fastapi_limiter import FastAPILimiter  # type: ignore[import-untyped]

        await FastAPILimiter.close()  # type: ignore[attr-defined]
        logger.info("rate_limiter_closed")
    except Exception:
        logger.warning("rate_limiter_shutdown_failed", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """
    FastAPI lifespan context manager.

    Startup: configure logging, warm up connections.
    Shutdown: close connections gracefully.
    """
    # --- Startup ---
    _configure_logging()
    logger.info("narrare_api_starting")

    # Rate limiter (Redis-backed, graceful degradation)
    await _init_rate_limiter()

    # TaskIQ broker startup (skip in worker process — it handles its own)
    try:
        from narrare.tasks.broker import broker  # type: ignore[import]  # Phase 4+ module

        if not broker.is_worker_process:  # type: ignore[attr-defined]  # untyped TaskIQ
            await broker.startup()  # type: ignore[attr-defined]  # untyped TaskIQ
            logger.info("taskiq_broker_started")
    except ImportError:
        pass  # Tasks not yet configured in Phase 2

    # Event bus startup (graceful — won't block if Redis is unavailable)
    try:
        from narrare._app.config import get_settings
        from narrare._app.events import init_event_bus

        _settings = get_settings()
        await init_event_bus(_settings.redis_url)
        logger.info("event_bus_initialized")
    except Exception:
        logger.warning("event_bus_init_failed", exc_info=True)

    logger.info("narrare_api_ready")

    yield

    # --- Shutdown ---
    logger.info("narrare_api_stopping")

    # Event bus shutdown
    try:
        from narrare._app.events import shutdown_event_bus

        await shutdown_event_bus()
    except Exception:
        logger.warning("event_bus_shutdown_failed", exc_info=True)

    # Rate limiter shutdown
    await _shutdown_rate_limiter()

    try:
        from narrare.tasks.broker import broker  # type: ignore[import]  # Phase 4+ module

        if not broker.is_worker_process:  # type: ignore[attr-defined]  # untyped TaskIQ
            await broker.shutdown()  # type: ignore[attr-defined]  # untyped TaskIQ
    except ImportError:
        pass

    logger.info("narrare_api_stopped")


def _configure_logging() -> None:
    """Configure structlog for the application."""
    import logging

    import structlog

    from narrare._app.config import get_settings

    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_development:
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(),
        ]
    else:
        processors = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,  # type: ignore[arg-type]
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
