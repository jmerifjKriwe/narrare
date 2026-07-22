"""Router-level tests for the adaptive endpoints (thin-delegation check).

Integration tests (DB + auth) live in tests/integration/adaptive/test_endpoints.py.
These tests verify the router delegates to the service with the right
arguments and returns the response schema.

Plan-Bug #10 (fixed inline): the plan's verbatim test code used integration
fixtures (``client``, ``auth_headers`` from ``tests/integration/conftest.py``)
which are invisible to ``tests/unit/`` (pytest conftest scoping). Adapted to
local ``app`` + ``client`` fixtures per codebase convention
(``test_chapter_router.py:48-74``). Auth is overridden directly via
``dependency_overrides[get_current_user_id]``; no ``auth_headers`` needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from narrare._app.database import get_async_session
from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare.adaptive.schemas import (
    AdaptiveContextResponse,
    AdaptiveSettingsResponse,
    AdaptiveSourceSummary,
    AdaptiveWeightsInput,
    AdaptiveWeightsResponse,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

TEST_USER_ID = "00000000-0000-0000-0000-0000000000ff"


# ---------------------------------------------------------------------------
# Fixtures (mirror tests/unit/api/chapters/test_chapter_router.py:48-74)
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Create test app with overridden DB session + auth dependencies."""
    application = create_app()

    async def _mock_session():
        mock = AsyncMock()
        mock.execute = AsyncMock()
        yield mock

    async def _mock_auth() -> str:
        return TEST_USER_ID

    application.dependency_overrides[get_async_session] = _mock_session
    application.dependency_overrides[get_current_user_id] = _mock_auth
    return application


@pytest.fixture
async def client(app):
    """Async HTTP client for testing (auth overridden — no auth_headers)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Origin": "http://localhost:3000"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


class _StubService:
    """Stub AdaptiveContextServiceProtocol for router tests."""

    def __init__(self) -> None:
        self.get_calls: list[tuple[object, object]] = []
        self.toggle_calls: list[tuple[object, object, bool]] = []
        self.weights_calls: list[tuple[object, object, AdaptiveWeightsInput]] = []

    async def get_context(self, project_id: object, user_id: object) -> AdaptiveContextResponse:
        self.get_calls.append((project_id, user_id))
        return AdaptiveContextResponse(
            project_id=str(project_id),
            enabled=True,
            weights=AdaptiveWeightsResponse(),
            sources=AdaptiveSourceSummary(),
            has_any_signal=False,
        )

    async def set_enabled(
        self, project_id: object, user_id: object, enabled: bool
    ) -> AdaptiveSettingsResponse:
        self.toggle_calls.append((project_id, user_id, enabled))
        return AdaptiveSettingsResponse(enabled=enabled)

    async def set_weights(
        self, project_id: object, user_id: object, weights: AdaptiveWeightsInput
    ) -> AdaptiveSettingsResponse:
        self.weights_calls.append((project_id, user_id, weights))
        return AdaptiveSettingsResponse(enabled=True, weights=AdaptiveWeightsResponse())


@pytest.mark.asyncio
async def test_get_context_returns_200(app: FastAPI, client: AsyncClient) -> None:
    """GET /adaptive/{project_id}/context returns the adaptive state."""
    from narrare.adaptive.dependencies import get_adaptive_context_service

    stub = _StubService()
    app.dependency_overrides[get_adaptive_context_service] = lambda: stub
    try:
        project_id = uuid4()
        response = await client.get(f"/api/v1/adaptive/{project_id}/context")
    finally:
        app.dependency_overrides.pop(get_adaptive_context_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["project_id"] == str(project_id)
    assert len(stub.get_calls) == 1


@pytest.mark.asyncio
async def test_toggle_returns_200(app: FastAPI, client: AsyncClient) -> None:
    """POST /adaptive/{project_id}/toggle persists the enabled flag."""
    from narrare.adaptive.dependencies import get_adaptive_context_service

    stub = _StubService()
    app.dependency_overrides[get_adaptive_context_service] = lambda: stub
    try:
        response = await client.post(
            f"/api/v1/adaptive/{uuid4()}/toggle",
            json={"enabled": False},
        )
    finally:
        app.dependency_overrides.pop(get_adaptive_context_service, None)

    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert stub.toggle_calls[0][2] is False


@pytest.mark.asyncio
async def test_set_weights_returns_200(app: FastAPI, client: AsyncClient) -> None:
    """POST /adaptive/{project_id}/weights updates the weights."""
    from narrare.adaptive.dependencies import get_adaptive_context_service

    stub = _StubService()
    app.dependency_overrides[get_adaptive_context_service] = lambda: stub
    try:
        response = await client.post(
            f"/api/v1/adaptive/{uuid4()}/weights",
            json={"preference": 0.3, "voice_fidelity": 0.5},
        )
    finally:
        app.dependency_overrides.pop(get_adaptive_context_service, None)

    assert response.status_code == 200
    assert stub.weights_calls[0][2].preference == 0.3
