"""Integration tests for POST /api/v1/settings/models/refresh.

Mocks the underlying ``refresh_models`` and ``get_cached_data`` calls
to avoid real HTTP requests to models.dev.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


pytestmark = pytest.mark.requires_db


class TestModelsRefresh:
    """Tests for the models.dev cache refresh endpoint."""

    async def test_refresh_without_previous_cache_returns_all_as_new(
        self,
        client: AsyncClient,
    ) -> None:
        """Happy path: no previous cache, all models appear as new."""
        mock_new_data = {
            "models": {
                "gpt-4o": {"cost": {"input": 2.5, "output": 10.0}},
                "claude-sonnet-4-5-20251020": {"cost": {"input": 3.0, "output": 15.0}},
            },
        }

        with (
            patch("narrare.settings.models_router.refresh_models", return_value=mock_new_data),
            patch("narrare.settings.models_router.get_cached_data", return_value=None),
        ):
            response = await client.post("/api/v1/settings/models/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert set(data["new_models"]) == {"gpt-4o", "claude-sonnet-4-5-20251020"}
        assert data["removed_models"] == []
        assert data["total_models"] == 2
        assert "cached_at" in data

    async def test_refresh_with_previous_cache_shows_diff(
        self,
        client: AsyncClient,
    ) -> None:
        """With existing cache: response shows added and removed models."""
        mock_old_data = {
            "models": {
                "gpt-4o": {"cost": {"input": 2.5, "output": 10.0}},
                "gpt-3.5-turbo": {"cost": {"input": 0.5, "output": 1.5}},
            },
        }
        mock_new_data = {
            "models": {
                "gpt-4o": {"cost": {"input": 2.5, "output": 10.0}},
                "claude-sonnet-4-5-20251020": {"cost": {"input": 3.0, "output": 15.0}},
            },
        }

        with (
            patch("narrare.settings.models_router.refresh_models", return_value=mock_new_data),
            patch("narrare.settings.models_router.get_cached_data", return_value=mock_old_data),
        ):
            response = await client.post("/api/v1/settings/models/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["new_models"] == ["claude-sonnet-4-5-20251020"]
        assert data["removed_models"] == ["gpt-3.5-turbo"]
        assert data["total_models"] == 2

    async def test_refresh_when_fetch_fails_returns_error_status(
        self,
        client: AsyncClient,
    ) -> None:
        """Error case: refresh_models returns empty dict, endpoint still 200.

        The endpoint must never return 500 — it degrades gracefully.
        """
        with (
            patch("narrare.settings.models_router.refresh_models", return_value={}),
            patch("narrare.settings.models_router.get_cached_data", return_value=None),
        ):
            response = await client.post("/api/v1/settings/models/refresh")

        assert response.status_code == 200  # Never 500
        data = response.json()
        assert data["status"] == "error"
        assert "message" in data
        assert "cached_at" in data

    async def test_refresh_with_empty_models_data(
        self,
        client: AsyncClient,
    ) -> None:
        """Edge case: models.dev returns data with no models key."""
        with (
            patch("narrare.settings.models_router.refresh_models", return_value={"models": {}}),
            patch("narrare.settings.models_router.get_cached_data", return_value=None),
        ):
            response = await client.post("/api/v1/settings/models/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["new_models"] == []
        assert data["total_models"] == 0

    async def test_refresh_invalid_data_no_models_key(
        self,
        client: AsyncClient,
    ) -> None:
        """Edge case: response has no 'models' key at all."""
        with (
            patch("narrare.settings.models_router.refresh_models", return_value={"foo": "bar"}),
            patch("narrare.settings.models_router.get_cached_data", return_value=None),
        ):
            response = await client.post("/api/v1/settings/models/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["new_models"] == []
        assert data["total_models"] == 0
