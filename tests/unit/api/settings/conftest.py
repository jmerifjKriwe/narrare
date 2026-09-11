"""Settings unit-test fixtures — ownership-matrix app/client (IDOR S11).

The ``app``/``client`` fixtures give the S11 ownership suites a test app
with overridden auth; the DB session dependency is overridden per-test
(``_ownership_helpers.install_session``) so the REAL gate dependencies +
handlers + repositories run over queued fake DB results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app

if TYPE_CHECKING:
    from fastapi import FastAPI

from tests.unit.api.settings._ownership_helpers import USER_A


@pytest.fixture
def app():
    """Test app with overridden auth (caller starts as USER_A, the owner)."""
    application = create_app()

    async def _mock_auth() -> str:
        return application.state.auth_user

    application.state.auth_user = str(USER_A)
    application.dependency_overrides[get_current_user_id] = _mock_auth
    return application


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"Origin": "http://localhost:3000"}
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
