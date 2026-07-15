"""Integration tests for dismissed-finding API endpoints.

Tests POST/GET/DELETE consistency dismiss endpoints with a mocked
DismissedFindingService via dependency_overrides (same pattern as
test_router_consistency.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import quote
from uuid import UUID

import pytest

from narrare.kb.consistency_contracts import DismissedFindingsResponse
from narrare.kb.dismissed_service import DismissedFindingService

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_dismissed_service() -> MagicMock:
    """Create a mocked DismissedFindingService for dependency override."""
    service = MagicMock(spec=DismissedFindingService)
    service.dismiss_finding = AsyncMock(
        return_value=DismissedFindingsResponse(fingerprints=["fp-1", "fp-2"]),
    )
    service.list_dismissed = AsyncMock(
        return_value=DismissedFindingsResponse(fingerprints=["fp-1"]),
    )
    service.undismiss_finding = AsyncMock(
        return_value=DismissedFindingsResponse(fingerprints=[]),
    )
    return service


# ---------------------------------------------------------------------------
# Tests: POST /consistency/dismiss
# ---------------------------------------------------------------------------


class TestDismissEndpoint:
    """Test POST /novels/{id}/kb/consistency/dismiss."""

    async def test_dismiss_returns_200_with_fingerprints(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_dismissed_service: MagicMock,
    ) -> None:
        """POST dismiss returns 200 with DismissedFindingsResponse."""
        from narrare.kb.dependencies import get_dismissed_service

        novel_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_dismissed_service] = (
            lambda: mock_dismissed_service  # type: ignore[assignment]
        )

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/consistency/dismiss",
            json={"fingerprint": "fp-1", "reason": "Accepted"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "fingerprints" in data
        assert data["fingerprints"] == ["fp-1", "fp-2"]

    async def test_dismiss_returns_401_without_auth(
        self,
        client: AsyncClient,
        app: FastAPI,
        mock_dismissed_service: MagicMock,
    ) -> None:
        """POST dismiss returns 401 without auth token."""
        from narrare.kb.dependencies import get_dismissed_service

        novel_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_dismissed_service] = (
            lambda: mock_dismissed_service  # type: ignore[assignment]
        )

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/consistency/dismiss",
            json={"fingerprint": "fp-1"},
        )

        assert resp.status_code == 401

    async def test_dismiss_returns_422_without_fingerprint(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_dismissed_service: MagicMock,
    ) -> None:
        """POST dismiss returns 422 when fingerprint is missing."""
        from narrare.kb.dependencies import get_dismissed_service

        novel_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_dismissed_service] = (
            lambda: mock_dismissed_service  # type: ignore[assignment]
        )

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/consistency/dismiss",
            json={"reason": "no fingerprint"},
            headers=auth_headers,
        )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: GET /consistency/dismissed
# ---------------------------------------------------------------------------


class TestListDismissedEndpoint:
    """Test GET /novels/{id}/kb/consistency/dismissed."""

    async def test_list_dismissed_returns_200(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_dismissed_service: MagicMock,
    ) -> None:
        """GET dismissed returns 200 with fingerprints list."""
        from narrare.kb.dependencies import get_dismissed_service

        novel_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_dismissed_service] = (
            lambda: mock_dismissed_service  # type: ignore[assignment]
        )

        resp = await client.get(
            f"/api/v1/novels/{novel_id}/kb/consistency/dismissed",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "fingerprints" in data
        assert data["fingerprints"] == ["fp-1"]

    async def test_list_dismissed_returns_401_without_auth(
        self,
        client: AsyncClient,
        app: FastAPI,
        mock_dismissed_service: MagicMock,
    ) -> None:
        """GET dismissed returns 401 without auth token."""
        from narrare.kb.dependencies import get_dismissed_service

        novel_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_dismissed_service] = (
            lambda: mock_dismissed_service  # type: ignore[assignment]
        )

        resp = await client.get(
            f"/api/v1/novels/{novel_id}/kb/consistency/dismissed",
        )

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tests: DELETE /consistency/dismissed/{fingerprint}
# ---------------------------------------------------------------------------


class TestUndismissEndpoint:
    """Test DELETE /novels/{id}/kb/consistency/dismissed/{fingerprint}."""

    async def test_undismiss_returns_200(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_dismissed_service: MagicMock,
    ) -> None:
        """DELETE undismiss returns 200 with updated fingerprints."""
        from narrare.kb.dependencies import get_dismissed_service

        novel_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_dismissed_service] = (
            lambda: mock_dismissed_service  # type: ignore[assignment]
        )

        resp = await client.delete(
            f"/api/v1/novels/{novel_id}/kb/consistency/dismissed/fp-1",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["fingerprints"] == []

    async def test_undismiss_url_encodes_fingerprint(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_dismissed_service: MagicMock,
    ) -> None:
        """DELETE handles URL-encoded fingerprints with special characters."""
        from narrare.kb.dependencies import get_dismissed_service

        novel_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_dismissed_service] = (
            lambda: mock_dismissed_service  # type: ignore[assignment]
        )

        raw_fingerprint = "Ages conflict::Alice,Bob"
        encoded = quote(raw_fingerprint, safe="")

        resp = await client.delete(
            f"/api/v1/novels/{novel_id}/kb/consistency/dismissed/{encoded}",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        # Verify the service received the decoded fingerprint
        mock_dismissed_service.undismiss_finding.assert_called_once_with(
            novel_id=UUID(novel_id),
            fingerprint=raw_fingerprint,
        )

    async def test_undismiss_returns_401_without_auth(
        self,
        client: AsyncClient,
        app: FastAPI,
        mock_dismissed_service: MagicMock,
    ) -> None:
        """DELETE undismiss returns 401 without auth token."""
        from narrare.kb.dependencies import get_dismissed_service

        novel_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_dismissed_service] = (
            lambda: mock_dismissed_service  # type: ignore[assignment]
        )

        resp = await client.delete(
            f"/api/v1/novels/{novel_id}/kb/consistency/dismissed/fp-1",
        )

        assert resp.status_code == 401
