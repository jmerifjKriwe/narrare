"""
App-level exception handlers: domain errors mapped to machine-readable HTTP.

Extracted from ``main.py`` (RULE-04 — the app factory hit the 400-line hard
limit when the E03 503 handler was added): one responsibility per file —
the factory wires middleware/routers, this module owns error → HTTP mapping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi.responses import JSONResponse

from narrare_core.notes.types import ScopeError
from narrare_core.shared.errors import NarrareError

if TYPE_CHECKING:
    from fastapi import FastAPI, Request

logger = structlog.get_logger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """Register all domain exception handlers on *app*."""

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

    # --- Notes scope-invariant handler (NOTES-001, T7 review carry-over) ---
    # ScopeError deliberately subclasses ValueError (NOT NarrareError) so the
    # pydantic schemas can raise it inside model_validators — pydantic wraps
    # it into a 422 automatically. The service re-validates the same
    # invariant on the MERGED PATCH state (stored note + patch), where the
    # raw ScopeError escapes pydantic and would otherwise surface as 500.
    # 422 matches the schema-level mapping of the identical invariant — one
    # error type, one status, regardless of the enforcing layer. Registered
    # app-level so the router stays free of try/except (RULE-06), mirroring
    # the ExportError handler below.
    @app.exception_handler(ScopeError)
    async def _scope_error_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: ScopeError
    ) -> JSONResponse:
        logger.warning("scope_error", detail=str(exc))
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc), "code": "SCOPE_CONFLICT"},
        )

    # --- Export-domain error handler (IO-001 / ADR-081) ---
    # ExportError is its own hierarchy (NOT a NarrareError subclass — the
    # contracts keep export errors decoupled from the shared error infra), so
    # it needs a dedicated handler. Maps the typed errors to HTTP so the
    # router stays free of try/except (RULE-06): 404 unknown job, 410
    # gone/expired artifact, 503 format-unavailable (binary missing), 400 for
    # any other ExportError (e.g. ExportRenderError surfacing unexpectedly).
    from narrare.export.errors import (
        ExportArtifactExpiredError,
        ExportError,
        ExportFormatUnavailableError,
        ExportJobNotFoundError,
    )

    @app.exception_handler(ExportError)
    async def _export_error_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: ExportError
    ) -> JSONResponse:
        if isinstance(exc, ExportJobNotFoundError):
            status_code = 404
        elif isinstance(exc, ExportArtifactExpiredError):
            status_code = 410
        elif isinstance(exc, ExportFormatUnavailableError):
            status_code = 503
        else:
            status_code = 400
        code = type(exc).__name__
        logger.warning("export_error", code=code, detail=str(exc))
        return JSONResponse(
            status_code=status_code,
            content={"detail": str(exc), "code": code},
        )

    # --- Analytics invalid-month handler (STATS-002 / ADR-093, spec §4) ---
    # Decorator form (mirrors the ScopeError handler above) —
    # ``add_exception_handler`` fails pyright on the narrow exc type.
    # Regex-valid but unconstructible months (``"0000-01"``, ``"9999-12"``)
    # pass the Query pattern and are rejected by the service's defensive
    # validation; this maps them to 422 instead of 500. Registered app-level
    # so the router stays free of try/except (RULE-06).
    from narrare.analytics.router import invalid_month_error_handler
    from narrare.analytics.service import InvalidMonthError

    app.exception_handler(InvalidMonthError)(invalid_month_error_handler)

    # --- Budget-exceeded handler (STATS-002 / ADR-094, spec A-2) ---
    # BudgetExceededError subclasses NarrareError, so without this specific
    # registration the generic NarrareError mapping above would answer 400.
    # Starlette resolves handlers by walking type(exc).__mro__ (most specific
    # first), so the narrower registration wins. 429 because the semantics
    # are quota exhaustion ("too many requests for this user this month") —
    # 402 implies payment processing, 403 implies authorization (ADR-094 D4).
    # Decorator form (InvalidMonthError precedent): ``add_exception_handler``
    # fails pyright on the narrow exc type.
    from narrare_core.shared.errors import BudgetExceededError

    @app.exception_handler(BudgetExceededError)
    async def _budget_exceeded_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: BudgetExceededError
    ) -> JSONResponse:
        logger.warning(
            "budget_exceeded",
            user_id=str(exc.user_id),
            month_spend_usd=exc.month_spend_usd,
            monthly_budget_usd=exc.monthly_budget_usd,
        )
        return JSONResponse(
            status_code=429,
            content={"detail": str(exc), "code": "BUDGET_EXCEEDED"},
        )

    # --- NLP-not-configured handler (audit E03 / spec §8) ---
    # NLPProviderError IS a NarrareError; without this registration the
    # generic mapping answers 400 (and a pre-wrap absent package escaped as
    # a raw 500). 503: the capability is not configured in this deployment —
    # the request is valid, retrying unchanged cannot succeed (same
    # semantics as ExportFormatUnavailableError).
    from narrare_core.shared.errors import NLPProviderError

    @app.exception_handler(NLPProviderError)
    async def _nlp_provider_error_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: NLPProviderError
    ) -> JSONResponse:
        logger.warning("nlp_provider_unavailable", detail=str(exc))
        return JSONResponse(
            status_code=503,
            content={"detail": str(exc), "code": "NLP_NOT_CONFIGURED"},
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
