"""Unit tests for the series-consistency router endpoint (Spec 4 Task 2).

Exercises the HTTP contract: status code, request parsing, response shaping,
delegation to ``SeriesConsistencyService``, and error mapping via the global
``NarrareError`` handler. Ownership is verified INSIDE the service (the novel id
arrives in the body, not the path), so the router test overrides the service
dependency directly with an ``AsyncMock`` (ADR-030: a non-domain infrastructure
mock at the thin delegation boundary is acceptable).

Shared ``app``/``client`` fixtures live in ``conftest.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import status

from narrare.series.dependencies_consistency import get_series_consistency_service
from narrare.series.series_consistency_schemas import SeriesConsistencyCheckResponse
from narrare_core.shared.errors import ForbiddenError

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient


def _make_response(series_id, novel_id) -> SeriesConsistencyCheckResponse:  # type: ignore[no-untyped-def]
    """A minimal successful check response for the mock return value."""
    return SeriesConsistencyCheckResponse(
        series_id=series_id,
        novel_id=novel_id,
        conflicts=[],
        summary="No contradictions found.",
        canon_entry_count=2,
        chapter_count=5,
    )


def _use_service(app: FastAPI, mock: AsyncMock) -> None:
    """Override the consistency-service dependency with ``mock``."""
    app.dependency_overrides[get_series_consistency_service] = lambda: mock


class TestCheckSeriesConsistency:
    """POST /api/v1/series/{series_id}/consistency/check."""

    async def test_post_returns_200_and_delegates(self, app: FastAPI, client: AsyncClient) -> None:
        series_id = uuid4()
        novel_id = uuid4()
        mock = AsyncMock()
        mock.check_novel.return_value = _make_response(series_id, novel_id)
        _use_service(app, mock)

        response = await client.post(
            f"/api/v1/series/{series_id}/consistency/check",
            json={"novel_id": str(novel_id)},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["series_id"] == str(series_id)
        assert data["novel_id"] == str(novel_id)
        assert data["conflicts"] == []
        assert data["canon_entry_count"] == 2
        # Delegation: the route passed series_id + novel_id + the conftest user id.
        mock.check_novel.assert_awaited_once()
        _args, kwargs = mock.check_novel.call_args
        assert kwargs["series_id"] == series_id
        assert kwargs["novel_id"] == novel_id

    async def test_post_forbidden_maps_to_403(self, app: FastAPI, client: AsyncClient) -> None:
        """ForbiddenError from the service maps to 403 (anti-enumeration)."""
        mock = AsyncMock()
        mock.check_novel.side_effect = ForbiddenError("You do not have access to this series")
        _use_service(app, mock)

        response = await client.post(
            f"/api/v1/series/{uuid4()}/consistency/check",
            json={"novel_id": str(uuid4())},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["code"] == "FORBIDDEN"

    async def test_post_missing_novel_id_body_returns_422(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        """A request without ``novel_id`` in the body fails validation (422)."""
        _use_service(app, AsyncMock())

        response = await client.post(
            f"/api/v1/series/{uuid4()}/consistency/check",
            json={},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_post_invalid_novel_id_returns_422(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        """A non-UUID novel_id fails Pydantic validation (422)."""
        _use_service(app, AsyncMock())

        response = await client.post(
            f"/api/v1/series/{uuid4()}/consistency/check",
            json={"novel_id": "not-a-uuid"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
