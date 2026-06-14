"""Unit tests for ``narrare._app.middleware`` — exception handling path.

Extends ``test_middleware.py`` to cover the error logging branch
(lines 59-62) when ``call_next`` raises an exception.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

if TYPE_CHECKING:
    from starlette.responses import PlainTextResponse

from narrare._app.middleware import RequestLoggingMiddleware


async def _failing_handler(request: Any) -> PlainTextResponse:
    """Handler that raises to trigger the middleware exception path."""
    raise RuntimeError("middleware-test-failure")


def _make_failing_app() -> Starlette:
    app = Starlette(routes=[])
    app.add_middleware(RequestLoggingMiddleware)
    app.add_route("/", _failing_handler)
    return app


class TestMiddlewareExceptionPath:
    def test_middleware_logs_and_reraises_on_exception(self) -> None:
        """When call_next raises, middleware logs error and re-raises."""
        client = TestClient(_make_failing_app(), raise_server_exceptions=True)

        with pytest.raises(RuntimeError, match="middleware-test-failure"):
            client.get("/")
