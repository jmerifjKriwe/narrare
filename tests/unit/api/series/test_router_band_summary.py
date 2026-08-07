"""Unit tests for the band-summary router endpoints (Spec 2 Task 4).

Exercises the HTTP contract: status codes, request parsing, response shaping,
delegation to ``BandSummaryService``, and error mapping via the global
``NarrareError`` handler. Ownership is bypassed/denied via dependency overrides
(integration tests exercise the real check).

Shared ``app``/``client`` fixtures live in ``conftest.py``; mock builders in
``_router_helpers.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from fastapi import status

from narrare.series.band_summary_models import BandSummary
from narrare.series.schemas import BandSummaryResponse
from narrare_core.shared.errors import NotFoundError, ValidationError

from ._router_helpers import (
    bypass_novel_ownership,
    deny_novel_ownership,
    mock_band_summary_service,
    uid,
    use_band_summary_service,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient


def _make_band_summary(novel_id: UUID | None = None) -> BandSummary:
    """A minimal ``BandSummary`` ORM-model instance for mock return values."""
    return BandSummary(
        novel_id=novel_id or uuid4(),
        full_summary="The hero prevails and the realm is restored.",
        short_summary="A hero restores a fractured realm.",
        override=None,
        generated_at=datetime.now(UTC),
    )


class TestGenerateBandSummary:
    async def test_post_returns_200_and_delegates(self, app: FastAPI, client: AsyncClient) -> None:
        novel_id = uid()
        mock = mock_band_summary_service()
        mock.generate.return_value = _make_band_summary(novel_id)
        use_band_summary_service(app, mock)
        bypass_novel_ownership(app)

        response = await client.post(f"/api/v1/series/{uid()}/novels/{novel_id}/band-summary")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["novel_id"] == str(novel_id)
        assert data["full_summary"] is not None
        mock.generate.assert_awaited_once_with(novel_id)

    async def test_post_ownership_denied_returns_403(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        use_band_summary_service(app, mock_band_summary_service())
        deny_novel_ownership(app)

        response = await client.post(f"/api/v1/series/{uid()}/novels/{uid()}/band-summary")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["code"] == "FORBIDDEN"

    async def test_post_novel_not_found_returns_404(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        mock = mock_band_summary_service()
        mock.generate.side_effect = NotFoundError("Novel", identifier="x")
        use_band_summary_service(app, mock)
        bypass_novel_ownership(app)

        response = await client.post(f"/api/v1/series/{uid()}/novels/{uid()}/band-summary")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_post_no_chapter_summaries_returns_422(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        mock = mock_band_summary_service()
        mock.generate.side_effect = ValidationError("no chapter summaries")
        use_band_summary_service(app, mock)
        bypass_novel_ownership(app)

        response = await client.post(f"/api/v1/series/{uid()}/novels/{uid()}/band-summary")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestGetBandSummary:
    async def test_get_returns_200_when_exists(self, app: FastAPI, client: AsyncClient) -> None:
        novel_id = uid()
        mock = mock_band_summary_service()
        mock.get.return_value = _make_band_summary(novel_id)
        use_band_summary_service(app, mock)
        bypass_novel_ownership(app)

        response = await client.get(f"/api/v1/series/{uid()}/novels/{novel_id}/band-summary")

        assert response.status_code == status.HTTP_200_OK
        BandSummaryResponse.model_validate(response.json())
        mock.get.assert_awaited_once_with(novel_id)

    async def test_get_returns_404_when_missing(self, app: FastAPI, client: AsyncClient) -> None:
        mock = mock_band_summary_service()
        mock.get.side_effect = NotFoundError("BandSummary", identifier="x")
        use_band_summary_service(app, mock)
        bypass_novel_ownership(app)

        response = await client.get(f"/api/v1/series/{uid()}/novels/{uid()}/band-summary")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_does_not_call_generate(self, app: FastAPI, client: AsyncClient) -> None:
        mock = mock_band_summary_service()
        mock.get.return_value = _make_band_summary()
        use_band_summary_service(app, mock)
        bypass_novel_ownership(app)

        await client.get(f"/api/v1/series/{uid()}/novels/{uid()}/band-summary")

        mock.generate.assert_not_awaited()


class TestSetBandSummaryOverride:
    async def test_patch_returns_200_and_sets_override(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        novel_id = uid()
        mock = mock_band_summary_service()
        mock.update_override.return_value = _make_band_summary(novel_id)
        use_band_summary_service(app, mock)
        bypass_novel_ownership(app)

        response = await client.patch(
            f"/api/v1/series/{uid()}/novels/{novel_id}/band-summary",
            json={"override": "My custom summary"},
        )

        assert response.status_code == status.HTTP_200_OK
        mock.update_override.assert_awaited_once_with(novel_id, "My custom summary")

    async def test_patch_missing_body_returns_422(self, app: FastAPI, client: AsyncClient) -> None:
        use_band_summary_service(app, mock_band_summary_service())
        bypass_novel_ownership(app)

        response = await client.patch(
            f"/api/v1/series/{uid()}/novels/{uid()}/band-summary", json={}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_patch_empty_override_returns_422(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        """Empty string violates ``min_length=1`` on the schema."""
        use_band_summary_service(app, mock_band_summary_service())
        bypass_novel_ownership(app)

        response = await client.patch(
            f"/api/v1/series/{uid()}/novels/{uid()}/band-summary",
            json={"override": ""},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestClearBandSummaryOverride:
    async def test_delete_returns_204_and_clears(self, app: FastAPI, client: AsyncClient) -> None:
        novel_id = uid()
        mock = mock_band_summary_service()
        mock.update_override.return_value = _make_band_summary(novel_id)
        use_band_summary_service(app, mock)
        bypass_novel_ownership(app)

        response = await client.delete(
            f"/api/v1/series/{uid()}/novels/{novel_id}/band-summary/override"
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        # None override → service treats as "clear".
        mock.update_override.assert_awaited_once_with(novel_id, None)

    async def test_delete_ownership_denied_returns_403(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        use_band_summary_service(app, mock_band_summary_service())
        deny_novel_ownership(app)

        response = await client.delete(
            f"/api/v1/series/{uid()}/novels/{uid()}/band-summary/override"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
