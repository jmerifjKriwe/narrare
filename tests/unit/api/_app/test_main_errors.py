"""Unit tests for ``narrare._app.main`` exception handlers.

Tests the NarrareError → HTTP status-code mapping and the unhandled
exception fallback handler by calling the handler closures registered
on the module-level FastAPI app.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

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
