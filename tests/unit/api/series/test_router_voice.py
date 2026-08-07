"""Unit tests for the Series Voice router endpoints (Spec 3 Task 3).

Exercises the HTTP contract: status codes, request parsing, response shaping,
delegation to ``SeriesVoiceService``, and error mapping via the global
``NarrareError`` handler. The service verifies ownership internally, so 403 is
exercised by making the mock service raise ``ForbiddenError``.

Shared ``app``/``client`` fixtures live in ``conftest.py``; mock builders in
``_router_helpers.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import status

from narrare_core.profiles.author_voice import AuthorVoiceProfile
from narrare_core.shared.errors import ForbiddenError, ValidationError

from ._router_helpers import (
    mock_series_voice_service,
    uid,
    use_series_voice_service,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient


def _profile() -> AuthorVoiceProfile:
    """A minimal AuthorVoiceProfile for mock return values."""
    return AuthorVoiceProfile(
        voice_analysis=None,
        author_examples=["The wind moved through the long grass."],
        author_metrics=None,
    )


class TestProfileSeriesVoice:
    async def test_post_returns_200_and_delegates(self, app: FastAPI, client: AsyncClient) -> None:
        novel_id = uid()
        series_id = uid()
        mock = mock_series_voice_service()
        mock.profile_from_novel.return_value = _profile()
        use_series_voice_service(app, mock)

        response = await client.post(
            f"/api/v1/series/{series_id}/voice/profile", json={"novel_id": str(novel_id)}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["series_id"] == str(series_id)
        assert data["novel_id"] == str(novel_id)
        assert data["author_voice"]["author_examples"]
        mock.profile_from_novel.assert_awaited_once()

    async def test_post_missing_body_returns_422(self, app: FastAPI, client: AsyncClient) -> None:
        use_series_voice_service(app, mock_series_voice_service())

        response = await client.post(f"/api/v1/series/{uid()}/voice/profile", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_post_ownership_denied_returns_403(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        mock = mock_series_voice_service()
        mock.profile_from_novel.side_effect = ForbiddenError("not yours")
        use_series_voice_service(app, mock)

        response = await client.post(
            f"/api/v1/series/{uid()}/voice/profile", json={"novel_id": str(uid())}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["code"] == "FORBIDDEN"

    async def test_post_no_chapters_returns_422(self, app: FastAPI, client: AsyncClient) -> None:
        mock = mock_series_voice_service()
        mock.profile_from_novel.side_effect = ValidationError("no chapters")
        use_series_voice_service(app, mock)

        response = await client.post(
            f"/api/v1/series/{uid()}/voice/profile", json={"novel_id": str(uid())}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestGetSeriesVoice:
    async def test_get_returns_200_with_profile(self, app: FastAPI, client: AsyncClient) -> None:
        series_id = uid()
        mock = mock_series_voice_service()
        mock.get.return_value = _profile()
        use_series_voice_service(app, mock)

        response = await client.get(f"/api/v1/series/{series_id}/voice")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["series_id"] == str(series_id)
        assert data["author_voice"] is not None

    async def test_get_returns_200_with_null_when_empty(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        mock = mock_series_voice_service()
        mock.get.return_value = None
        use_series_voice_service(app, mock)

        response = await client.get(f"/api/v1/series/{uid()}/voice")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["author_voice"] is None

    async def test_get_ownership_denied_returns_403(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        mock = mock_series_voice_service()
        mock.get.side_effect = ForbiddenError("not yours")
        use_series_voice_service(app, mock)

        response = await client.get(f"/api/v1/series/{uid()}/voice")

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestUpdateSeriesVoiceOverride:
    async def test_patch_returns_200_and_sets_override(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        series_id = uid()
        mock = mock_series_voice_service()
        mock.update_override.return_value = _profile()
        use_series_voice_service(app, mock)

        response = await client.patch(
            f"/api/v1/series/{series_id}/voice",
            json={"author_voice": {"voice_analysis": {"formality": 0.7}}},
        )

        assert response.status_code == status.HTTP_200_OK
        mock.update_override.assert_awaited_once()

    async def test_patch_missing_body_returns_422(self, app: FastAPI, client: AsyncClient) -> None:
        use_series_voice_service(app, mock_series_voice_service())

        response = await client.patch(f"/api/v1/series/{uid()}/voice", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_patch_invalid_override_returns_422(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        mock = mock_series_voice_service()
        mock.update_override.side_effect = ValidationError("not a valid profile")
        use_series_voice_service(app, mock)

        response = await client.patch(
            f"/api/v1/series/{uid()}/voice",
            json={"author_voice": {"voice_analysis": "bad"}},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestClearSeriesVoiceOverride:
    async def test_delete_returns_204_and_clears(self, app: FastAPI, client: AsyncClient) -> None:
        series_id = uid()
        mock = mock_series_voice_service()
        mock.clear_override.return_value = None
        use_series_voice_service(app, mock)

        response = await client.delete(f"/api/v1/series/{series_id}/voice/override")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock.clear_override.assert_awaited_once()

    async def test_delete_ownership_denied_returns_403(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        mock = mock_series_voice_service()
        mock.clear_override.side_effect = ForbiddenError("not yours")
        use_series_voice_service(app, mock)

        response = await client.delete(f"/api/v1/series/{uid()}/voice/override")

        assert response.status_code == status.HTTP_403_FORBIDDEN
