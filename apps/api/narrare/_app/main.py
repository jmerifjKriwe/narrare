"""
Narrare FastAPI application factory.

Creates and configures the FastAPI app with all middleware,
routers, and exception handlers.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from narrare._app.config import get_settings
from narrare._app.lifespan import lifespan
from narrare._app.middleware import RequestLoggingMiddleware
from narrare._app.telemetry import setup_telemetry
from narrare_core.shared.errors import NarrareError

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Narrare API",
        description="AI-assisted creative writing environment",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # --- OpenTelemetry (no-op if not configured) ---
    setup_telemetry(app)

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"] if not settings.is_production else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Request logging ---
    app.add_middleware(RequestLoggingMiddleware)

    # --- Domain error handler ---
    @app.exception_handler(NarrareError)
    async def _narrare_error_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: NarrareError
    ) -> JSONResponse:
        from narrare_core.shared.errors import (
            AuthenticationError,
            ConflictError,
            ForbiddenError,
            NotFoundError,
        )

        status_code = 400  # default for NarrareError
        if isinstance(exc, NotFoundError):
            status_code = 404
        elif isinstance(exc, ForbiddenError):
            status_code = 403
        elif isinstance(exc, ConflictError):
            status_code = 409
        elif isinstance(exc, AuthenticationError):
            status_code = 401

        logger.error(
            "narrare_error",
            code=exc.code,
            detail=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=status_code,
            content={"detail": str(exc), "code": exc.code},
        )

    # --- Unhandled exception handler ---
    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            detail=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # --- Routers ---
    _register_routers(app)

    return app


def _register_routers(app: FastAPI) -> None:
    """Register all domain routers."""
    from narrare.auth.router import router as auth_router
    from narrare.chapters.router import router as chapters_router
    from narrare.generation.router import router as generation_router
    from narrare.memory.router import router as memory_router
    from narrare.metrics.router import router as metrics_router
    from narrare.novels.router import router as novels_router
    from narrare.prompts.router import router as prompts_router
    from narrare.settings.router import router as settings_router
    from narrare.setup.router import router as setup_router
    from narrare.volumes.router import router as volumes_router

    prefix = "/api/v1"

    app.include_router(auth_router, prefix=prefix)
    app.include_router(novels_router, prefix=prefix)
    app.include_router(chapters_router, prefix=prefix)
    app.include_router(volumes_router, prefix=prefix)
    app.include_router(settings_router, prefix=prefix)
    app.include_router(memory_router, prefix=prefix)
    app.include_router(prompts_router, prefix=prefix)
    app.include_router(generation_router, prefix=prefix)
    app.include_router(setup_router, prefix=prefix)
    app.include_router(metrics_router)  # No prefix — /health, /ready


# Application instance
app = create_app()
