"""Application lifespan — startup and shutdown handlers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI

logger = structlog.get_logger(__name__)


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

    # TaskIQ broker startup (skip in worker process — it handles its own)
    try:
        from narrare.tasks.broker import broker  # type: ignore[import]  # Phase 4+ module

        if not broker.is_worker_process:  # type: ignore[attr-defined]  # untyped TaskIQ
            await broker.startup()  # type: ignore[attr-defined]  # untyped TaskIQ
            logger.info("taskiq_broker_started")
    except ImportError:
        pass  # Tasks not yet configured in Phase 2

    logger.info("narrare_api_ready")

    yield

    # --- Shutdown ---
    logger.info("narrare_api_stopping")

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
