"""Unit tests for the Series CRUD + settings router endpoints.

Tests the FastAPI router via ``httpx.AsyncClient`` with mocked services
(canonical pattern from ``tests/unit/api/wiki/test_wiki_router.py``). The
services are replaced with ``AsyncMock``s so these tests exercise the HTTP
contract only — routing, status codes, request parsing, response shaping,
error mapping (via the global ``NarrareError`` handler in ``_app/main.py``)
and auth.

Novels-in-series endpoints are in ``test_router_novels.py``; full end-to-end
coverage lives in ``tests/integration/series/``.

Shared ``app``/``client`` fixtures live in ``conftest.py``; mock builders in
``_router_helpers.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from fastapi import status
from httpx import ASGITransport, AsyncClient

from narrare._app.database import get_async_session
from narrare._app.main import create_app
from narrare.series.schemas import SeriesResponse, SeriesSettingsResponse, SeriesSummary
from narrare.series.service import InvalidStatusTransitionError, SeriesNotFoundError

from ._router_helpers import (
    mock_series_service,
    series_response,
    uid,
    use_series_service,
)

if TYPE_CHECKING:
    from fastapi import FastAPI


class TestCreateSeries:
    async def test_post_returns_201(self, app: FastAPI, client: AsyncClient) -> None:
        mock = mock_series_service()
        mock.create_series.return_value = series_response(title="The Expanse")
        use_series_service(app, mock)

        response = await client.post("/api/v1/series", json={"title": "The Expanse"})

        assert response.status_code == status.HTTP_201_CREATED
        SeriesResponse.model_validate(response.json())
        assert response.json()["title"] == "The Expanse"
        assert response.json()["status"] == "draft"
        mock.create_series.assert_awaited_once()

    async def test_post_missing_title_returns_422(self, app: FastAPI, client: AsyncClient) -> None:
        use_series_service(app, mock_series_service())

        response = await client.post("/api/v1/series", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestListSeries:
    async def test_get_returns_200_list(self, app: FastAPI, client: AsyncClient) -> None:
        mock = mock_series_service()
        mock.list_series.return_value = [
            SeriesSummary(id=uid(), title="A", subtitle=None, status="draft", novel_count=0),
            SeriesSummary(id=uid(), title="B", subtitle=None, status="active", novel_count=3),
        ]
        use_series_service(app, mock)

        response = await client.get("/api/v1/series")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[1]["novel_count"] == 3


class TestGetSeries:
    async def test_get_returns_200(self, app: FastAPI, client: AsyncClient) -> None:
        series = series_response()
        mock = mock_series_service()
        mock.get_series.return_value = series
        use_series_service(app, mock)

        response = await client.get(f"/api/v1/series/{series.id}")

        assert response.status_code == status.HTTP_200_OK
        SeriesResponse.model_validate(response.json())

    async def test_get_unknown_returns_404(self, app: FastAPI, client: AsyncClient) -> None:
        mock = mock_series_service()
        mock.get_series.side_effect = SeriesNotFoundError(uid())
        use_series_service(app, mock)

        response = await client.get(f"/api/v1/series/{uid()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["code"] == "NOT_FOUND"


class TestUpdateSeries:
    async def test_patch_returns_200(self, app: FastAPI, client: AsyncClient) -> None:
        series = series_response()
        mock = mock_series_service()
        mock.update_series.return_value = series
        use_series_service(app, mock)

        response = await client.patch(f"/api/v1/series/{series.id}", json={"status": "active"})

        assert response.status_code == status.HTTP_200_OK
        SeriesResponse.model_validate(response.json())

    async def test_patch_invalid_transition_returns_409(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        mock = mock_series_service()
        mock.update_series.side_effect = InvalidStatusTransitionError("draft", "completed")
        use_series_service(app, mock)

        response = await client.patch(f"/api/v1/series/{uid()}", json={"status": "completed"})

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["code"] == "INVALID_STATUS_TRANSITION"


class TestDeleteSeries:
    async def test_delete_returns_204(self, app: FastAPI, client: AsyncClient) -> None:
        mock = mock_series_service()
        mock.delete_series.return_value = None
        use_series_service(app, mock)

        response = await client.delete(f"/api/v1/series/{uid()}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_delete_unknown_returns_404(self, app: FastAPI, client: AsyncClient) -> None:
        mock = mock_series_service()
        mock.delete_series.side_effect = SeriesNotFoundError(uid())
        use_series_service(app, mock)

        response = await client.delete(f"/api/v1/series/{uid()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestSettings:
    async def test_get_settings_returns_200(self, app: FastAPI, client: AsyncClient) -> None:
        series_id = uid()
        mock = mock_series_service()
        mock.get_settings.return_value = SeriesSettingsResponse(
            series_id=series_id, author_voice=None
        )
        use_series_service(app, mock)

        response = await client.get(f"/api/v1/series/{series_id}/settings")

        assert response.status_code == status.HTTP_200_OK
        SeriesSettingsResponse.model_validate(response.json())
        assert response.json()["author_voice"] is None

    async def test_update_settings_returns_200(self, app: FastAPI, client: AsyncClient) -> None:
        series_id = uid()
        mock = mock_series_service()
        mock.update_settings.return_value = SeriesSettingsResponse(
            series_id=series_id, author_voice={"tone": "formal"}
        )
        use_series_service(app, mock)

        response = await client.patch(
            f"/api/v1/series/{series_id}/settings", json={"author_voice": {"tone": "formal"}}
        )

        assert response.status_code == status.HTTP_200_OK
        SeriesSettingsResponse.model_validate(response.json())
        assert response.json()["author_voice"] == {"tone": "formal"}


class TestUnauthorized:
    async def test_no_auth_returns_401(self, client: AsyncClient) -> None:
        """A client with no auth override (no token) is rejected at the auth dep."""
        bare_app = create_app()

        async def _no_auth_session():
            mock = AsyncMock()
            mock.execute = AsyncMock()
            yield mock

        bare_app.dependency_overrides[get_async_session] = _no_auth_session

        async with AsyncClient(
            transport=ASGITransport(app=bare_app), base_url="http://test"
        ) as bare_client:
            response = await bare_client.get("/api/v1/series")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
