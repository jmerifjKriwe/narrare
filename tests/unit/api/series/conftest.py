"""Shared pytest fixtures for the Series router unit tests.

Builds a FastAPI test app with the DB session + auth dependencies overridden
(services are overridden per-test in each test module). Mirrors the canonical
pattern in ``tests/unit/api/wiki/test_router.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from narrare._app.database import get_async_session
from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI

TEST_USER_ID = "00000000-0000-0000-0000-0000000000ff"


@pytest.fixture
def app() -> FastAPI:
    """Test app with DB session + auth bypassed (services overridden per-test)."""
    application = create_app()

    async def _mock_session() -> Any:
        mock = AsyncMock()
        mock.execute = AsyncMock()
        yield mock

    async def _mock_auth() -> str:
        return TEST_USER_ID

    application.dependency_overrides[get_async_session] = _mock_session
    application.dependency_overrides[get_current_user_id] = _mock_auth
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    """Async HTTP client. Origin header satisfies CSRF middleware if active."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Origin": "http://localhost:3000"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
