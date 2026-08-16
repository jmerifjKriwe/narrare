"""Router tests for GET /series/{id}/settings/context-preview (C1).

Mirrors test_router.py conventions: the conftest app/client fixtures with
DB + auth overridden; the preview service is mocked per-test via the
dependency override (service logic is covered by its own unit tests).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from fastapi import status

from narrare.series.dependencies_context_preview import (
    get_series_history_preview_service,
)
from narrare.series.series_history_preview_schemas import (
    SeriesHistoryPreviewEntry,
    SeriesHistoryPreviewResponse,
)
from narrare_core.shared.errors import ForbiddenError

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient


def _response(series_id: uuid.UUID) -> SeriesHistoryPreviewResponse:
    return SeriesHistoryPreviewResponse(
        series_id=series_id,
        current_window_size=3,
        effective_series_history_budget=16_000,
        effective_context_total=32_000,
        effective_tier_base=16_000,
        model_context_window=128_000,
        budget_source="cascade:uncapped",
        previews=[
            SeriesHistoryPreviewEntry(
                window_size=k,
                token_budget=16_000,
                estimated_tokens=100 * k,
                bands_total=4,
                bands_full=min(k, 4),
                bands_short=max(4 - k, 0),
                bands_truncated=0,
                bands_dropped=0,
                bands_missing=0,
                budget_clipped=False,
            )
            for k in range(1, 11)
        ],
    )


def _use_preview_service(app: FastAPI, service: AsyncMock) -> None:
    app.dependency_overrides[get_series_history_preview_service] = lambda: service


class TestGetSettingsContextPreview:
    async def test_returns_200_with_preview(self, app: FastAPI, client: AsyncClient) -> None:
        series_id = uid()
        mock = AsyncMock()
        mock.get_preview.return_value = _response(series_id)
        _use_preview_service(app, mock)

        response = await client.get(f"/api/v1/series/{series_id}/settings/context-preview")

        assert response.status_code == status.HTTP_200_OK
        body = SeriesHistoryPreviewResponse.model_validate(response.json())
        assert body.series_id == series_id
        assert [p.window_size for p in body.previews] == list(range(1, 11))
        mock.get_preview.assert_awaited_once_with(series_id, uuid.UUID(TEST_USER_ID))

    async def test_missing_or_foreign_series_maps_to_403(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        mock = AsyncMock()
        mock.get_preview.side_effect = ForbiddenError("You do not have access to this series")
        _use_preview_service(app, mock)

        response = await client.get(f"/api/v1/series/{uid()}/settings/context-preview")

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestWindowDefaultPin:
    """Review-carry from the Task 3 review (minor: window-default drift risk).

    Pins both module-level ``_DEFAULT_WINDOW_SIZE`` constants (preview
    service + provider) to the Core ``SeriesSettings`` schema default so the
    mirrored defaults (ORM column, migration 0038 server_default, provider
    constant, service constant, Core schema) cannot drift apart silently.
    """

    def test_window_defaults_match_core_schema_default(self) -> None:
        """Task 3 review carry: the window default lives in five mirrored
        places; this pin fails the suite when any pair drifts."""
        from narrare.series.series_history_preview_service import (
            _DEFAULT_WINDOW_SIZE as service_default,
        )
        from narrare.series.series_history_provider import (
            _DEFAULT_WINDOW_SIZE as provider_default,
        )
        from narrare_core.series.schemas import SeriesSettings

        core_default = SeriesSettings.model_fields["context_window_size"].default

        assert service_default == provider_default
        assert core_default == service_default


def uid() -> uuid.UUID:
    return uuid.uuid4()


# Must equal the conftest fixture's authenticated user constant so the
# router's ``uuid.UUID(user_id)`` argument matches the asserted call.
TEST_USER_ID = "00000000-0000-0000-0000-0000000000ff"
