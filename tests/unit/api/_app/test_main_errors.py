"""Unit tests for ``narrare._app.main`` exception handlers.

Tests the NarrareError → HTTP status-code mapping and the unhandled
exception fallback handler by calling the handler closures registered
on the module-level FastAPI app.

The ExportError handler (IO-001 / ADR-081) is additionally exercised
through ``TestClient`` requests so the errors pass through Starlette's
real exception dispatch to the handler registered by ``create_app()`` —
verifying registration AND the isinstance mapping end-to-end.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import pytest

from narrare_core.shared.errors import (
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    NarrareError,
    NotFoundError,
    ValidationError,
)

if TYPE_CHECKING:
    from fastapi import Request
    from fastapi.testclient import TestClient


def _get_handler(exc_class: type) -> Any:
    """Return the exception handler for *exc_class* from the app."""
    from narrare._app.main import app

    return app.exception_handlers[exc_class]


def _body(response: Any) -> dict[str, Any]:
    """Decode a JSONResponse body."""
    return json.loads(response.body)


# ---------------------------------------------------------------------------
# NarrareError handler — status-code mapping
# ---------------------------------------------------------------------------


class TestNarrareErrorHandler:
    async def test_not_found_maps_to_404(self) -> None:
        handler = _get_handler(NarrareError)
        response = await handler(cast("Request", None), NotFoundError("Novel", identifier="42"))
        assert response.status_code == 404

    async def test_forbidden_maps_to_403(self) -> None:
        handler = _get_handler(NarrareError)
        response = await handler(cast("Request", None), ForbiddenError("nope"))
        assert response.status_code == 403

    async def test_conflict_maps_to_409(self) -> None:
        handler = _get_handler(NarrareError)
        response = await handler(cast("Request", None), ConflictError("dup"))
        assert response.status_code == 409

    async def test_authentication_maps_to_401(self) -> None:
        handler = _get_handler(NarrareError)
        response = await handler(cast("Request", None), AuthenticationError("bad"))
        assert response.status_code == 401

    async def test_validation_maps_to_422(self) -> None:
        handler = _get_handler(NarrareError)
        response = await handler(cast("Request", None), ValidationError("bad"))
        assert response.status_code == 422

    async def test_generic_narrare_error_maps_to_400(self) -> None:
        handler = _get_handler(NarrareError)
        response = await handler(cast("Request", None), NarrareError("oops"))
        assert response.status_code == 400
        body = _body(response)
        assert body["detail"] == "oops"


# ---------------------------------------------------------------------------
# Unhandled exception handler
# ---------------------------------------------------------------------------


class TestUnhandledExceptionHandler:
    async def test_returns_500_with_generic_message(self) -> None:
        handler = _get_handler(Exception)
        response = await handler(cast("Request", None), RuntimeError("boom"))
        assert response.status_code == 500
        body = _body(response)
        assert body["detail"] == "Internal server error"


# ---------------------------------------------------------------------------
# Export error handler — TestClient round-trip (IO-001 / ADR-081)
# ---------------------------------------------------------------------------

# Probe route error kinds → (expected status, expected response code).
# 400 is the fallback for any ExportError without a more specific mapping
# (e.g. ExportRenderError surfacing unexpectedly outside the job flow).
_EXPORT_ERROR_CASES = [
    ("job_not_found", 404, "ExportJobNotFoundError"),
    ("artifact_expired", 410, "ExportArtifactExpiredError"),
    ("format_unavailable", 503, "ExportFormatUnavailableError"),
    ("render", 400, "ExportRenderError"),
    ("generic", 400, "ExportError"),
]


class TestExportErrorHandler:
    """ExportError → HTTP mapping via the real app's exception dispatch.

    ExportError is its own hierarchy (NOT a NarrareError subclass), so a
    registration regression would silently fall through to the generic
    Exception handler (500). Driving a probe route on a fresh
    ``create_app()`` instance pins both the registration and the
    isinstance mapping.
    """

    @pytest.fixture
    def client(self) -> TestClient:
        """TestClient for a fresh app with a route raising export errors.

        No context manager → no lifespan startup (no DB, no registries).
        """
        from fastapi.testclient import TestClient

        from narrare._app.main import create_app
        from narrare.export.errors import (
            ExportArtifactExpiredError,
            ExportError,
            ExportFormatUnavailableError,
            ExportJobNotFoundError,
            ExportRenderError,
        )

        errors: dict[str, type[ExportError]] = {
            "job_not_found": ExportJobNotFoundError,
            "artifact_expired": ExportArtifactExpiredError,
            "format_unavailable": ExportFormatUnavailableError,
            "render": ExportRenderError,
            "generic": ExportError,
        }

        app = create_app(test_mode=True)

        @app.get("/_test/export-error")
        def _raise_export_error(kind: str) -> None:
            raise errors[kind]("export failed")

        return TestClient(app)

    @pytest.mark.parametrize(
        ("kind", "expected_status", "expected_code"),
        _EXPORT_ERROR_CASES,
    )
    def test_export_error_maps_to_status_and_code(
        self,
        client: TestClient,
        kind: str,
        expected_status: int,
        expected_code: str,
    ) -> None:
        response = client.get("/_test/export-error", params={"kind": kind})

        assert response.status_code == expected_status
        body = response.json()
        assert body == {"detail": "export failed", "code": expected_code}
