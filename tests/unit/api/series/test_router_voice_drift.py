"""Unit tests for the series voice-drift router endpoint (Spec 4 Task 3).

Exercises the HTTP contract: status code, request parsing, response shaping,
delegation to ``SeriesVoiceDriftService``, and error mapping. Ownership is
verified INSIDE the service, so the router test overrides the service
dependency with an ``AsyncMock`` (ADR-030: non-domain infrastructure mock at the
thin delegation boundary).

Shared ``app``/``client`` fixtures live in ``conftest.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import status

from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftResponse
from narrare.series.dependencies_voice_drift import get_series_voice_drift_service
from narrare_core.shared.errors import ForbiddenError

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient


def _make_response(novel_id) -> AuthorVoiceDriftResponse:  # type: ignore[no-untyped-def]
    """A minimal successful drift response for the mock return value."""
    return AuthorVoiceDriftResponse(novel_id=str(novel_id))


def _use_service(app: FastAPI, mock: AsyncMock) -> None:
    """Override the voice-drift-service dependency with ``mock``."""
    app.dependency_overrides[get_series_voice_drift_service] = lambda: mock


class TestCheckSeriesVoiceDrift:
    """POST /api/v1/series/{series_id}/voice-drift/check."""

    async def test_post_returns_200_and_delegates(self, app: FastAPI, client: AsyncClient) -> None:
        novel_id = uuid4()
        mock = AsyncMock()
        mock.check.return_value = _make_response(novel_id)
        _use_service(app, mock)

        response = await client.post(
            f"/api/v1/series/{uuid4()}/voice-drift/check",
            json={"novel_id": str(novel_id)},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["novel_id"] == str(novel_id)
        mock.check.assert_awaited_once()
        _args, kwargs = mock.check.call_args
        assert kwargs["novel_id"] == novel_id

    async def test_post_forbidden_maps_to_403(self, app: FastAPI, client: AsyncClient) -> None:
        mock = AsyncMock()
        mock.check.side_effect = ForbiddenError("You do not have access to this series")
        _use_service(app, mock)

        response = await client.post(
            f"/api/v1/series/{uuid4()}/voice-drift/check",
            json={"novel_id": str(uuid4())},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["code"] == "FORBIDDEN"

    async def test_post_missing_novel_id_body_returns_422(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        _use_service(app, AsyncMock())

        response = await client.post(
            f"/api/v1/series/{uuid4()}/voice-drift/check",
            json={},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_post_with_chapter_ids_delegates_filter(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        """The optional chapter_ids filter is forwarded to the service request."""
        novel_id = uuid4()
        ch1, ch2 = uuid4(), uuid4()
        mock = AsyncMock()
        mock.check.return_value = _make_response(novel_id)
        _use_service(app, mock)

        response = await client.post(
            f"/api/v1/series/{uuid4()}/voice-drift/check",
            json={"novel_id": str(novel_id), "chapter_ids": [str(ch1), str(ch2)]},
        )

        assert response.status_code == status.HTTP_200_OK
        _args, kwargs = mock.check.call_args
        assert kwargs["request"].chapter_ids == [str(ch1), str(ch2)]
