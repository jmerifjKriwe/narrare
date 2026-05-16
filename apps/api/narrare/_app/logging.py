"""Logging configuration — dual-handler setup for development.

In development (when ``log_file`` is set), routes DEBUG/TRACE output to a
rotating log file while keeping the terminal clean at INFO+.  In production,
emits structured JSON to stdout only.

Uses the official structlog stdlib integration pattern:
    structlog.stdlib.LoggerFactory + ProcessorFormatter
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from structlog.types import Processor

logger = structlog.get_logger(__name__)


def configure_logging() -> None:
    """Configure structlog + stdlib logging with dual handlers in development."""
    from narrare._app.config import get_settings

    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.stdlib.PositionalArgumentsFormatter(),
    ]

    if settings.is_development and settings.log_file:
        _configure_development_logging(shared_processors, log_level, settings.log_file)
    else:
        _configure_production_logging(shared_processors, log_level)


def _configure_development_logging(
    shared_processors: list[Processor],
    log_level: int,
    log_file: str,
) -> None:
    """Development: console (INFO+) + file (DEBUG+)."""
    # Ensure log directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Clear existing handlers (idempotent)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG)  # Let everything through; handlers filter

    # Formatter using structlog's ProcessorFormatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(),
        ],
        foreign_pre_chain=shared_processors,  # type: ignore[arg-type]
    )

    # Console handler — INFO and above (terminal stays clean)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # File handler — DEBUG and above (everything to file)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Error file handler — ERROR and above, with full tracebacks
    error_file_handler = RotatingFileHandler(
        log_path.parent / "error.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(),
            ],
            foreign_pre_chain=shared_processors,  # type: ignore[arg-type]
        )
    )
    root.addHandler(error_file_handler)

    # Also route uvicorn's loggers to both handlers so uvicorn output
    # is captured in the log file too
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(logger_name)
        uv_logger.handlers.clear()
        uv_logger.propagate = False
        uv_logger.setLevel(logging.DEBUG)
        uv_logger.addHandler(console_handler)
        uv_logger.addHandler(file_handler)

    # Configure structlog to use stdlib logging
    structlog.configure(
        processors=[  # type: ignore[arg-type]
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def _configure_production_logging(
    shared_processors: list[Processor],
    log_level: int,
) -> None:
    """Production: JSON to stdout + error file with full tracebacks."""
    # Clear existing handlers (idempotent)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(log_level)

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,  # type: ignore[arg-type]
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Error file handler — ERROR and above, with full tracebacks
    log_path = Path("logs")
    log_path.mkdir(parents=True, exist_ok=True)

    error_file_handler = RotatingFileHandler(
        log_path / "error.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)
    root.addHandler(error_file_handler)

    structlog.configure(
        processors=[  # type: ignore[arg-type]
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        cache_logger_on_first_use=True,
    )
