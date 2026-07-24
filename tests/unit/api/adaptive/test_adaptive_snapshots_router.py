"""Router tests for GET /adaptive/{project_id}/snapshots (ADR-070 Task 5).

Thin-delegation check: the route must forward ``project_id`` and ``limit`` to
``AdaptiveContextService.get_adaptive_snapshots`` and return the response
schema. No business logic lives here (RULE-06).

Plan-Bug #12 (found + fixed inline): the plan's verbatim test code keyed
``dependency_overrides`` on ``CurrentUserIdDep`` — an ``Annotated`` type
alias rather than the underlying dependency callable. FastAPI resolves that
alias to ``Depends(get_current_user_id)`` and matches overrides by the
*callable*, so keying on the alias is a silent no-op (the real auth runs and
returns 401). Verified empirically:

    dependency_overrides[CurrentUserIdDep]   -> 401 {'detail': 'Not authenticated'}
    dependency_overrides[get_current_user_id] -> 200 {'uid': 'OVR-B'}

This mirrors the ``test_router.py`` Plan-Bug #10 adaptation: override
``get_current_user_id`` directly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from narrare._app.dependencies import get_current_user_id
from narrare.adaptive.dependencies import get_adaptive_context_service
from narrare.adaptive.router import router
from narrare.adaptive.schemas import (
    AdaptiveSnapshotItem,
    AdaptiveSnapshotsResponse,
)

if TYPE_CHECKING:
    from uuid import UUID


class _StubService:
    """Stub AdaptiveContextServiceProtocol — records the snapshots call args."""

    def __init__(self, response: AdaptiveSnapshotsResponse) -> None:
        self._response = response
        self.last_project_id: UUID | None = None
        self.last_limit: int | None = None

    async def get_adaptive_snapshots(
        self,
        project_id: UUID,
        user_id: UUID,
        limit: int = 20,
    ) -> AdaptiveSnapshotsResponse:
        del user_id  # ownership handled at the router boundary
        self.last_project_id = project_id
        self.last_limit = limit
        return self._response


@pytest.fixture
def stub_service() -> _StubService:
    """Return a stub service yielding one adaptive snapshot."""
    return _StubService(
        response=AdaptiveSnapshotsResponse(
            project_id=str(uuid4()),
            items=[
                AdaptiveSnapshotItem(
                    intent="dialogue_coach",
                    mode="dialogue_coach",
                    created_at=datetime(2026, 7, 23, tzinfo=UTC),
                    source_summary={"summary": "preferences"},
                )
            ],
        )
    )


def _make_app(stub: _StubService | None = None) -> FastAPI:
    """Build a bare app mounting only the adaptive router.

    When ``stub`` is provided, auth is overridden to a fixed user and the
    adaptive service is replaced by ``stub``. When ``stub`` is ``None``, auth
    is left real so a request without credentials receives 401.
    """
    app = FastAPI()
    app.include_router(router)
    if stub is not None:
        app.dependency_overrides[get_current_user_id] = lambda: str(uuid4())
        app.dependency_overrides[get_adaptive_context_service] = lambda: stub
    return app


@pytest.fixture
async def client(stub_service: _StubService):
    """Async HTTP client with auth + service overridden."""
    app = _make_app(stub_service)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestGetSnapshotsEndpoint:
    async def test_returns_200_with_items(
        self,
        client: AsyncClient,
        stub_service: _StubService,
    ) -> None:
        """GET /snapshots returns 200 and forwards project_id + limit."""
        novel = uuid4()
        resp = await client.get(f"/adaptive/{novel}/snapshots?limit=20")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["source_summary"] == {"summary": "preferences"}
        assert stub_service.last_project_id == novel
        assert stub_service.last_limit == 20

    async def test_default_limit_is_20(
        self,
        client: AsyncClient,
        stub_service: _StubService,
    ) -> None:
        """Omitting ``limit`` defaults to 20."""
        await client.get(f"/adaptive/{uuid4()}/snapshots")

        assert stub_service.last_limit == 20

    async def test_missing_auth_returns_401(self) -> None:
        """A request without credentials is rejected with 401."""
        app = _make_app(stub=None)  # no auth override -> real auth -> 401
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(f"/adaptive/{uuid4()}/snapshots")

        assert resp.status_code == 401
