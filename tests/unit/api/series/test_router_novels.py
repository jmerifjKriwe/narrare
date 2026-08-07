"""Unit tests for the novels-in-series router endpoints.

Join preview/apply, list, reorder and remove — with mocked services
(canonical pattern from ``tests/unit/api/wiki/test_router_router.py``).
Exercises the HTTP contract: status codes, request parsing, response
shaping, and error mapping via the global ``NarrareError`` handler in
``_app/main.py``.

Shared ``app``/``client`` fixtures live in ``conftest.py``; mock builders in
``_router_helpers.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import status

from narrare.novels.schemas import NovelSummaryResponse
from narrare.series.join_service import NovelAlreadyInSeriesError
from narrare.series.schemas import (
    JoinEntryTreatment,
    JoinPreview,
    JoinResult,
)

from ._router_helpers import (
    mock_join_service,
    mock_series_service,
    uid,
    use_join_service,
    use_series_service,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient


class TestListNovelsInSeries:
    async def test_get_returns_200_list(self, app: FastAPI, client: AsyncClient) -> None:
        now = datetime.now(UTC)
        mock = mock_series_service()
        mock.list_novels.return_value = [
            NovelSummaryResponse(
                id=uid(),
                title="Novel One",
                author="A",
                genre="sci-fi",
                writing_language="en",
                is_demo=False,
                updated_at=now,
            ),
        ]
        use_series_service(app, mock)

        response = await client.get(f"/api/v1/series/{uid()}/novels")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["title"] == "Novel One"


class TestPreviewJoin:
    async def test_post_returns_200_preview(self, app: FastAPI, client: AsyncClient) -> None:
        series_id, novel_id = uid(), uid()
        mock = mock_join_service()
        mock.preview_join.return_value = JoinPreview(
            series_id=series_id,
            novel_id=novel_id,
            canon_empty=True,
            treatments=[
                JoinEntryTreatment(
                    entry_id=uid(),
                    slug="magic",
                    entity_type="system",
                    current_scope="novel",
                    target_scope="series",
                    reason_code="entity_default_canon",
                    reason="Entity type 'system' defaults to Canon (Policy iii)",
                ),
            ],
        )
        use_join_service(app, mock)

        response = await client.post(
            f"/api/v1/series/{series_id}/novels", json={"novel_id": str(novel_id)}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["canon_empty"] is True
        assert data["treatments"][0]["target_scope"] == "series"
        # preview must NOT call apply.
        mock.apply_join.assert_not_awaited()

    async def test_post_already_in_series_returns_409(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        mock = mock_join_service()
        mock.preview_join.side_effect = NovelAlreadyInSeriesError(uid(), uid())
        use_join_service(app, mock)

        response = await client.post(
            f"/api/v1/series/{uid()}/novels", json={"novel_id": str(uid())}
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["code"] == "CONFLICT"

    async def test_post_missing_body_returns_422(self, app: FastAPI, client: AsyncClient) -> None:
        use_join_service(app, mock_join_service())

        response = await client.post(f"/api/v1/series/{uid()}/novels", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestApplyJoin:
    async def test_post_returns_200_result(self, app: FastAPI, client: AsyncClient) -> None:
        series_id, novel_id = uid(), uid()
        mock = mock_join_service()
        mock.apply_join.return_value = JoinResult(
            series_id=series_id,
            novel_id=novel_id,
            position=1,
            promoted_to_canon=5,
            kept_as_overlay=2,
        )
        use_join_service(app, mock)

        response = await client.post(
            f"/api/v1/series/{series_id}/novels/{novel_id}/apply", json={"position": 1}
        )

        assert response.status_code == status.HTTP_200_OK
        JoinResult.model_validate(response.json())
        assert response.json()["promoted_to_canon"] == 5

    async def test_post_already_in_series_returns_409(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        mock = mock_join_service()
        mock.apply_join.side_effect = NovelAlreadyInSeriesError(uid(), uid())
        use_join_service(app, mock)

        response = await client.post(
            f"/api/v1/series/{uid()}/novels/{uid()}/apply", json={"position": 1}
        )

        assert response.status_code == status.HTTP_409_CONFLICT


class TestRemoveNovelFromSeries:
    async def test_delete_returns_204(self, app: FastAPI, client: AsyncClient) -> None:
        mock = mock_join_service()
        mock.remove_novel.return_value = None
        use_join_service(app, mock)

        response = await client.delete(f"/api/v1/series/{uid()}/novels/{uid()}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock.remove_novel.assert_awaited_once()


class TestReorderNovels:
    async def test_patch_returns_204(self, app: FastAPI, client: AsyncClient) -> None:
        mock = mock_series_service()
        mock.reorder_novels.return_value = None
        use_series_service(app, mock)

        novel_ids = [str(uid()), str(uid())]
        response = await client.patch(
            f"/api/v1/series/{uid()}/novels/reorder", json={"novel_ids": novel_ids}
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock.reorder_novels.assert_awaited_once()

    async def test_patch_missing_body_returns_422(self, app: FastAPI, client: AsyncClient) -> None:
        use_series_service(app, mock_series_service())

        response = await client.patch(f"/api/v1/series/{uid()}/novels/reorder", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
