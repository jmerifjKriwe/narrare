"""HTTP-level lazy-resolution node pins for the wiki refresh endpoint.

ADR-086 L30: FastAPI solves sub-dependencies BEFORE body validation —
with the old eager factory an unconfigured provider preempted legitimate
422s with a 400 (the defect class this migration eradicates). These pins
hold the migrated node in place:

- Invalid body + failing resolver -> 422; the resolver is never awaited
  (lazy wiring proof at the HTTP boundary).
- Valid body + failing resolver   -> 400 (ConfigurationError propagates
  loudly post-validation — RULE-11; wiki is AI-mandatory).

Non-SSE endpoint — no pre-header pin needed (L14 REST precedent).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from narrare._app.database import get_async_session
from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.shared.errors import ConfigurationError

TEST_USER_ID = "00000000-0000-0000-0000-0000000000ff"
_REFRESH_URL = (
    "/api/v1/novels/00000000-0000-0000-0000-000000000001/wiki/summaries/"
    "00000000-0000-0000-0000-000000000002/refresh"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def failing_resolver() -> MagicMock:
    """Spec'd resolver whose resolve() raises (unconfigured provider)."""
    resolver = MagicMock(spec=ModelRoutingResolverImpl, name="ModelRoutingResolver")
    resolver.resolve = AsyncMock(
        side_effect=ConfigurationError("No AI provider configured.", code="NO_AI_PROVIDER")
    )
    return resolver


class _FakeDbResult:
    """Sync stand-in for a SQLAlchemy Result — one truthy row.

    Repos call ``session.execute(...).scalar_one_or_none()``; the real
    rows never materialize (resolution fails first), so a truthy
    sentinel row is all the ownership gate needs.
    """

    def __init__(self) -> None:
        self._row: object = object()

    def scalar_one_or_none(self) -> object | None:
        return self._row


@pytest.fixture
def app(failing_resolver: MagicMock):
    """Test app: real wiki factory, resolver patched to fail, no DB."""
    application = create_app()

    async def _mock_session():
        mock = AsyncMock()
        mock.execute = AsyncMock(return_value=_FakeDbResult())
        yield mock

    async def _mock_auth() -> str:
        return TEST_USER_ID

    application.dependency_overrides[get_async_session] = _mock_session
    application.dependency_overrides[get_current_user_id] = _mock_auth
    return application


@pytest.fixture
async def client(app: Any):
    """Async HTTP client wired to the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"Origin": "http://localhost:3000"}
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Pins
# ---------------------------------------------------------------------------


class TestLazyResolutionHTTPNodes:
    """The refresh endpoint's 422 node must precede any model resolution."""

    async def test_invalid_body_returns_422_without_resolution(
        self,
        app: Any,
        client: AsyncClient,
        failing_resolver: MagicMock,
    ) -> None:
        """Invalid body wins with 422 even though the provider is unconfigured."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "narrare.wiki.dependencies.get_model_routing_resolver",
                lambda _session: failing_resolver,
            )
            response = await client.post(_REFRESH_URL, json={"entity_id": "not-a-uuid"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        failing_resolver.resolve.assert_not_awaited()

    async def test_valid_body_unconfigured_provider_returns_400(
        self,
        app: Any,
        client: AsyncClient,
        failing_resolver: MagicMock,
    ) -> None:
        """RULE-11: with a valid body the ConfigurationError surfaces as 400."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "narrare.wiki.dependencies.get_model_routing_resolver",
                lambda _session: failing_resolver,
            )
            response = await client.post(_REFRESH_URL, json={"force": True})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        failing_resolver.resolve.assert_awaited_once()
