"""Unit tests for the Series-Canon KB CRUD router endpoints.

Series Foundation Spec 1, Slice 3 Task 3.8.

Exercises the FastAPI router under the real app (``create_app``) with the canon
service replaced by an ``AsyncMock`` — the canonical pattern from
``tests/unit/api/series/test_router.py``. These tests cover the HTTP contract
only: routing, status codes, request parsing, response shaping, error mapping
(via the global ``NarrareError`` handler in ``_app/main.py``) and auth. The
service business logic is covered by ``test_canon_service.py`` (RULE-04 split).

Endpoints under ``/api/v1/series/{series_id}/kb``:
    GET    /                  -> 200  list[SeriesKBEntry]
    POST   /                  -> 201  SeriesKBEntry
    GET    /{entry_id}        -> 200  SeriesKBEntry  (404 missing / not canon)
    PATCH  /{entry_id}        -> 200  SeriesKBEntry
    DELETE /{entry_id}        -> 204
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from narrare._app.database import get_async_session
from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare.kb.dependencies import get_kb_canon_service
from narrare_core.kb.schemas.entry import SeriesKBEntry
from narrare_core.shared.errors import ConflictError, ForbiddenError, NotFoundError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI

TEST_USER_ID = "00000000-0000-0000-0000-0000000000ff"


def _series_entry(*, name: str = "Magic System", entity_type: str = "system") -> SeriesKBEntry:
    """A minimal valid SeriesKBEntry (canon scope)."""
    return SeriesKBEntry(
        id=uuid.uuid4(),
        entity_type=entity_type,
        name=name,
        slug=name.lower().replace(" ", "-"),
        status="canon",
        body="Hard magic.",
        series_id=uuid.uuid4(),
        novel_id=None,
        base_entry_id=None,
    )


def mock_canon_service() -> AsyncMock:
    """A mock KBCanonService exposing the router-facing surface."""
    service = AsyncMock()
    for method in ("list_canon", "create_canon", "get_canon", "update_canon", "delete_canon"):
        setattr(service, method, AsyncMock())
    return service


def use_canon_service(app: FastAPI, service: AsyncMock) -> None:
    app.dependency_overrides[get_kb_canon_service] = lambda: service


@pytest.fixture
def app() -> FastAPI:
    """Test app with DB session + auth bypassed (service overridden per-test)."""
    application = create_app()

    async def _mock_session() -> object:
        mock = AsyncMock()
        mock.execute = AsyncMock()
        yield mock

    application.dependency_overrides[get_async_session] = _mock_session
    application.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Origin": "http://localhost:3000"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


class TestListCanon:
    async def test_get_returns_200_list(self, app: FastAPI, client: AsyncClient) -> None:
        mock = mock_canon_service()
        mock.list_canon.return_value = [_series_entry(name="A"), _series_entry(name="B")]
        use_canon_service(app, mock)

        response = await client.get(f"/api/v1/series/{uuid.uuid4()}/kb")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["scope"] == "series"
        assert data[0]["novel_id"] is None

    async def test_get_forbidden_returns_403(self, app: FastAPI, client: AsyncClient) -> None:
        mock = mock_canon_service()
        mock.list_canon.side_effect = ForbiddenError("You do not have access to this series")
        use_canon_service(app, mock)

        response = await client.get(f"/api/v1/series/{uuid.uuid4()}/kb")

        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateCanon:
    async def test_post_returns_201(self, app: FastAPI, client: AsyncClient) -> None:
        entry = _series_entry()
        mock = mock_canon_service()
        mock.create_canon.return_value = entry
        use_canon_service(app, mock)

        response = await client.post(
            f"/api/v1/series/{entry.series_id}/kb",
            json={"entity_type": "system", "name": "Magic System"},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["id"] == str(entry.id)
        assert body["scope"] == "series"
        assert body["novel_id"] is None
        assert body["series_id"] == str(entry.series_id)
        # user_id from the auth override is converted to UUID before the call.
        mock.create_canon.assert_awaited_once()
        called_series_id, called_user_id, _ = mock.create_canon.call_args[0]
        assert called_series_id == entry.series_id
        assert called_user_id == uuid.UUID(TEST_USER_ID)

    async def test_post_missing_fields_returns_422(self, app: FastAPI, client: AsyncClient) -> None:
        use_canon_service(app, mock_canon_service())

        response = await client.post(f"/api/v1/series/{uuid.uuid4()}/kb", json={})

        assert response.status_code == 422

    async def test_post_duplicate_slug_returns_409(self, app: FastAPI, client: AsyncClient) -> None:
        mock = mock_canon_service()
        mock.create_canon.side_effect = ConflictError("already exists in this series")
        use_canon_service(app, mock)

        response = await client.post(
            f"/api/v1/series/{uuid.uuid4()}/kb",
            json={"entity_type": "system", "name": "Magic System"},
        )

        assert response.status_code == 409
        assert response.json()["code"] == "CONFLICT"


# ---------------------------------------------------------------------------
# Get single
# ---------------------------------------------------------------------------


class TestGetCanon:
    async def test_get_returns_200(self, app: FastAPI, client: AsyncClient) -> None:
        entry = _series_entry()
        mock = mock_canon_service()
        mock.get_canon.return_value = entry
        use_canon_service(app, mock)

        response = await client.get(f"/api/v1/series/{entry.series_id}/kb/{entry.id}")

        assert response.status_code == 200
        assert response.json()["id"] == str(entry.id)

    async def test_get_non_canon_or_missing_returns_404(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        """An entry that is missing or not canon surfaces as 404."""
        mock = mock_canon_service()
        mock.get_canon.side_effect = NotFoundError("KBEntry", identifier=str(uuid.uuid4()))
        use_canon_service(app, mock)

        response = await client.get(f"/api/v1/series/{uuid.uuid4()}/kb/{uuid.uuid4()}")

        assert response.status_code == 404
        assert response.json()["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestUpdateCanon:
    async def test_patch_returns_200(self, app: FastAPI, client: AsyncClient) -> None:
        entry = _series_entry()
        mock = mock_canon_service()
        mock.update_canon.return_value = entry
        use_canon_service(app, mock)

        response = await client.patch(
            f"/api/v1/series/{entry.series_id}/kb/{entry.id}",
            json={"name": "Renamed"},
        )

        assert response.status_code == 200
        assert response.json()["id"] == str(entry.id)

    async def test_patch_missing_returns_404(self, app: FastAPI, client: AsyncClient) -> None:
        mock = mock_canon_service()
        mock.update_canon.side_effect = NotFoundError("KBEntry", identifier=str(uuid.uuid4()))
        use_canon_service(app, mock)

        response = await client.patch(
            f"/api/v1/series/{uuid.uuid4()}/kb/{uuid.uuid4()}", json={"name": "X"}
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDeleteCanon:
    async def test_delete_returns_204(self, app: FastAPI, client: AsyncClient) -> None:
        mock = mock_canon_service()
        mock.delete_canon.return_value = None
        use_canon_service(app, mock)

        response = await client.delete(f"/api/v1/series/{uuid.uuid4()}/kb/{uuid.uuid4()}")

        assert response.status_code == 204
        mock.delete_canon.assert_awaited_once()

    async def test_delete_missing_returns_404(self, app: FastAPI, client: AsyncClient) -> None:
        mock = mock_canon_service()
        mock.delete_canon.side_effect = NotFoundError("KBEntry", identifier=str(uuid.uuid4()))
        use_canon_service(app, mock)

        response = await client.delete(f"/api/v1/series/{uuid.uuid4()}/kb/{uuid.uuid4()}")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestUnauthorized:
    async def test_no_auth_returns_401(self) -> None:
        """A request with no auth override (no token) is rejected at the auth dep."""
        bare_app = create_app()

        async def _no_auth_session() -> object:
            mock = AsyncMock()
            mock.execute = AsyncMock()
            yield mock

        bare_app.dependency_overrides[get_async_session] = _no_auth_session

        async with AsyncClient(
            transport=ASGITransport(app=bare_app), base_url="http://test"
        ) as bare_client:
            response = await bare_client.get(f"/api/v1/series/{uuid.uuid4()}/kb")

        assert response.status_code == 401
