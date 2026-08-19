"""Unit tests for ``narrare._app.main`` CSRF middleware registration (AUFG-05-13).

``create_app()`` registers ``OriginValidationMiddleware`` only when
``settings.is_test`` is ``False`` (the CSRF block in ``main.py``). Unit
tests run with ``ENVIRONMENT=test`` (``tests/conftest.py``), so that
registration branch — and the middleware's validation dispatch through
the real app stack — is never exercised by the module-level ``app``.

These tests flip the cached settings instance to a non-test environment
(monkeypatched; restored on teardown), build a fresh ``create_app()``
instance, and drive it through ``TestClient``:

* POST with a disallowed ``Origin`` → 403 ``CSRF_ORIGIN_MISMATCH``.
* POST with a valid ``Authorization: Bearer`` token and no
  Origin/Referer → exempt (programmatic client, AUFG-05-13 semantics).

No context manager → no lifespan startup (no DB, no registries) — same
convention as ``test_main_errors.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from narrare._app.middleware import OriginValidationMiddleware
from narrare.auth.security import create_access_token

if TYPE_CHECKING:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient


@pytest.fixture
def non_test_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient for a fresh app built in non-test mode (AUFG-05-13).

    Patches the cached settings instance to ``environment="development"``
    so ``create_app()`` takes the ``not settings.is_test`` branch and
    registers ``OriginValidationMiddleware`` with ``_test_mode=False``
    (the ``create_app()`` default). Monkeypatch restores the original
    environment value on teardown.
    """
    from fastapi.testclient import TestClient

    from narrare._app.config import get_settings
    from narrare._app.main import create_app

    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "development")

    app = create_app()

    @app.post("/_test/echo")
    def _echo() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(app)


class TestOriginValidationRegistration:
    """``create_app()`` registers + enforces origin validation outside test mode."""

    def test_middleware_registered_when_not_test_mode(self, non_test_client: TestClient) -> None:
        app = cast("FastAPI", non_test_client.app)
        registered = any(
            middleware.cls is OriginValidationMiddleware for middleware in app.user_middleware
        )
        assert registered, (
            "OriginValidationMiddleware must be registered when settings.is_test is False"
        )

    def test_post_with_disallowed_origin_rejected(self, non_test_client: TestClient) -> None:
        response = non_test_client.post("/_test/echo", headers={"Origin": "https://evil.example"})

        assert response.status_code == 403
        assert response.json() == {
            "detail": "Origin not allowed",
            "code": "CSRF_ORIGIN_MISMATCH",
        }

    def test_post_with_bearer_and_no_origin_exempt(self, non_test_client: TestClient) -> None:
        from narrare._app.config import get_settings

        token = create_access_token(
            subject="test-user",
            secret_key=get_settings().secret_key,
        )

        response = non_test_client.post("/_test/echo", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
