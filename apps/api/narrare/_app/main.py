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
from narrare._app.middleware import (
    OriginValidationMiddleware,
    RequestLoggingMiddleware,
    get_trusted_origins,
)
from narrare._app.telemetry import setup_telemetry
from narrare_core.shared.errors import NarrareError

logger = structlog.get_logger(__name__)


def create_app(*, test_mode: bool = False) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        test_mode: If ``True``, pass ``_test_mode`` to
            :class:`OriginValidationMiddleware <narrare._app.middleware.OriginValidationMiddleware>`
            so state-changing requests without Origin/Referer headers (e.g.
            httpx ``AsyncClient``) are not rejected with 403.
    """
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

    # --- CSRF Origin/Referer validation (defense-in-depth, AUFG-05-13) ---
    # Skipped in test environment — TestClient simulates programmatic API
    # calls which never carry an Origin header.
    if not settings.is_test:
        app.add_middleware(
            OriginValidationMiddleware,
            trusted_origins=get_trusted_origins(settings),
            _test_mode=test_mode,
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
            ValidationError,
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
        elif isinstance(exc, ValidationError):
            status_code = 422

        # NOTE: exc_info is intentionally omitted — NarrareError subclasses
        # are expected domain errors (not bugs), not unexpected crashes.
        # The code + detail fields are sufficient for diagnostics.
        # Keeping exc_info=True would trigger structlog's rich traceback
        # rendering (ConsoleRenderer) which adds ~2.7s per error due to
        # deep exception chains (NotFoundError ← IntegrityError ← DBError).
        logger.error(
            "narrare_error",
            code=exc.code,
            detail=str(exc),
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

    # --- Ensure all SQLAlchemy models are registered with Base.metadata ---
    # Must happen before any DB operation (some models have cross-module FKs).
    import narrare._app.models  # noqa: F401  # pyright: ignore[reportUnusedImport]

    # --- Routers ---
    _register_routers(app)

    return app


def _register_routers(app: FastAPI) -> None:
    """Register all domain routers."""
    from narrare.adaptive.router import router as adaptive_router
    from narrare.ai_assist.router import router as ai_assist_router
    from narrare.analysis.router import router as analysis_router
    from narrare.analysis.router_author_voice import (
        router as analysis_author_voice_router,
    )
    from narrare.analysis.router_author_voice_drift import (
        router as analysis_author_voice_drift_router,
    )
    from narrare.analysis.router_character_voice import (
        router as analysis_character_voice_router,
    )
    from narrare.analysis.router_coreference import router as analysis_coreference_router
    from narrare.analysis.router_pov import router as analysis_pov_router
    from narrare.analysis.router_readability import router as analysis_readability_router
    from narrare.analysis.router_voice_check import router as analysis_voice_check_router
    from narrare.analysis.router_voice_drift import router as analysis_voice_drift_router
    from narrare.auth.router import router as auth_router
    from narrare.auth.router_me import router as auth_me_router
    from narrare.chapters.router import router as chapters_router
    from narrare.chapters.router_versions import router as chapter_versions_router
    from narrare.chat.router import router as chat_router
    from narrare.embeddings.router import router as embeddings_router
    from narrare.generation.router import router as generation_router
    from narrare.kb.router import router as kb_router
    from narrare.kb.router_consistency import router as kb_consistency_router
    from narrare.kb.router_extraction import router as kb_extraction_router
    from narrare.kb.router_graph import router as kb_graph_router
    from narrare.kb.router_improve import router as kb_improve_router
    from narrare.kb.router_relationships import router as kb_relationships_router
    from narrare.kb.router_sessions import router as kb_sessions_router
    from narrare.kb.router_sessions_complete import router as kb_sessions_complete_router
    from narrare.kb.router_suggestions import router as kb_suggestions_router
    from narrare.kb.router_worldbuilding import router as kb_worldbuilding_router
    from narrare.memory.router import router as memory_router
    from narrare.memory.router_analysis import router as memory_analysis_router
    from narrare.metrics.router import router as metrics_router
    from narrare.novels.router import router as novels_router
    from narrare.planning.router import router as planning_router
    from narrare.prompts.router import router as prompts_router
    from narrare.prompts.router_prompt_history import (
        router as prompts_prompt_history_router,
    )
    from narrare.prompts.router_prompt_ux import router as prompts_prompt_ux_router
    from narrare.series.router import router as series_router
    from narrare.series.router_band_summary import router as series_band_summary_router
    from narrare.series.router_consistency import router as series_consistency_router
    from narrare.series.router_novels import router as series_novels_router
    from narrare.series.router_voice import router as series_voice_router
    from narrare.series.router_voice_drift import router as series_voice_drift_router
    from narrare.settings.router import router as settings_router
    from narrare.setup.router import router as setup_router
    from narrare.tasks.router import router as tasks_router
    from narrare.templates.router import router as templates_router
    from narrare.volumes.router import router as volumes_router
    from narrare.wiki.router import router as wiki_router
    from narrare.writing.router import router as writing_router
    from narrare.writing.router_coauthor import router as coauthor_router
    from narrare.writing.router_extend import router as writing_extend_router
    from narrare.writing.router_rewrite import router as writing_rewrite_router
    from narrare.writing.router_sessions import router as writing_sessions_router
    from narrare.writing.router_stats import router as writing_stats_router
    from narrare.writing.router_story_suggest import (
        router as writing_story_suggest_router,
    )
    from narrare.writing.router_style_variants import (
        router as writing_style_variants_router,
    )
    from narrare.writing.router_suggest import router as writing_suggest_router
    from narrare.writing.summary_router import router as summary_router

    prefix = "/api/v1"

    app.include_router(auth_router, prefix=prefix)
    app.include_router(auth_me_router, prefix=prefix)
    app.include_router(novels_router, prefix=prefix)
    app.include_router(series_router, prefix=prefix)
    app.include_router(series_novels_router, prefix=prefix)
    app.include_router(series_band_summary_router, prefix=prefix)
    app.include_router(series_voice_router, prefix=prefix)
    app.include_router(series_consistency_router, prefix=prefix)
    app.include_router(series_voice_drift_router, prefix=prefix)
    app.include_router(planning_router, prefix=prefix)
    app.include_router(chapters_router, prefix=prefix)
    app.include_router(chapter_versions_router, prefix=prefix)
    app.include_router(analysis_router, prefix=prefix)
    app.include_router(analysis_readability_router, prefix=prefix)
    app.include_router(analysis_pov_router, prefix=prefix)
    app.include_router(analysis_coreference_router, prefix=prefix)
    app.include_router(analysis_character_voice_router, prefix=prefix)
    app.include_router(analysis_voice_check_router, prefix=prefix)
    app.include_router(analysis_voice_drift_router, prefix=prefix)
    app.include_router(analysis_author_voice_router, prefix=prefix)
    app.include_router(analysis_author_voice_drift_router, prefix=prefix)
    app.include_router(adaptive_router, prefix=prefix)
    app.include_router(ai_assist_router, prefix=prefix)
    app.include_router(embeddings_router)  # Full paths already include /api/v1/admin/embeddings/
    app.include_router(volumes_router, prefix=prefix)
    app.include_router(kb_router, prefix=prefix)
    app.include_router(kb_consistency_router, prefix=prefix)
    app.include_router(kb_graph_router, prefix=prefix)
    app.include_router(kb_relationships_router, prefix=prefix)
    app.include_router(kb_extraction_router, prefix=prefix)
    app.include_router(kb_sessions_router, prefix=prefix)
    app.include_router(kb_sessions_complete_router, prefix=prefix)
    app.include_router(kb_improve_router, prefix=prefix)
    app.include_router(kb_suggestions_router, prefix=prefix)
    app.include_router(kb_worldbuilding_router, prefix=prefix)
    app.include_router(settings_router, prefix=prefix)
    app.include_router(memory_router, prefix=prefix)
    app.include_router(memory_analysis_router, prefix=prefix)
    # CR-AUFG-07-19: history routes MUST precede the prompts catch-all
    # GET /{prompt_id:path} in prompts_router (path-greedy ordering), so they
    # are included first.
    app.include_router(prompts_prompt_history_router, prefix=prefix)
    app.include_router(prompts_router, prefix=prefix)
    app.include_router(prompts_prompt_ux_router, prefix=prefix)
    app.include_router(generation_router, prefix=prefix)
    app.include_router(setup_router, prefix=prefix)
    app.include_router(templates_router, prefix=prefix)
    app.include_router(metrics_router)  # No prefix — /health, /ready, /metrics
    app.include_router(tasks_router)  # No prefix — /tasks/status (monitoring)
    app.include_router(writing_router, prefix=prefix)
    app.include_router(writing_extend_router, prefix=prefix)
    app.include_router(writing_rewrite_router, prefix=prefix)
    app.include_router(writing_style_variants_router, prefix=prefix)
    app.include_router(writing_sessions_router, prefix=prefix)
    app.include_router(writing_stats_router, prefix=prefix)
    app.include_router(writing_suggest_router, prefix=prefix)
    app.include_router(writing_story_suggest_router, prefix=prefix)
    app.include_router(coauthor_router, prefix=prefix)
    app.include_router(summary_router, prefix=prefix)
    app.include_router(wiki_router, prefix=prefix)
    app.include_router(chat_router, prefix=prefix)


# Application instance
app = create_app()
