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
from narrare.kb.dependencies import get_dismissed_service
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
        novel_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_dismissed_service] = (
            lambda: mock_dismissed_service  # type: ignore[assignment]
        )
        try:
            resp = await client.post(
                f"/api/v1/novels/{novel_id}/kb/consistency/dismiss",
                json={"fingerprint": "fp-1", "reason": "Accepted"},
                headers=auth_headers,
            )
        finally:
            # The app fixture is session-scoped — an override left behind
            # leaks into subsequent tests (order-dependent flakiness under
            # pytest-randomly). Same cleanup convention as
            # tests/integration/analysis/test_analysis_api.py.
            app.dependency_overrides.pop(get_dismissed_service, None)

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
        novel_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_dismissed_service] = (
            lambda: mock_dismissed_service  # type: ignore[assignment]
        )
        try:
            resp = await client.post(
                f"/api/v1/novels/{novel_id}/kb/consistency/dismiss",
                json={"fingerprint": "fp-1"},
            )
        finally:
            app.dependency_overrides.pop(get_dismissed_service, None)

        assert resp.status_code == 401

    async def test_dismiss_returns_422_without_fingerprint(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_dismissed_service: MagicMock,
    ) -> None:
        """POST dismiss returns 422 when fingerprint is missing."""
        novel_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_dismissed_service] = (
            lambda: mock_dismissed_service  # type: ignore[assignment]
        )
        try:
            resp = await client.post(
                f"/api/v1/novels/{novel_id}/kb/consistency/dismiss",
                json={"reason": "no fingerprint"},
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_dismissed_service, None)

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
        novel_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_dismissed_service] = (
            lambda: mock_dismissed_service  # type: ignore[assignment]
        )
        try:
            resp = await client.get(
                f"/api/v1/novels/{novel_id}/kb/consistency/dismissed",
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_dismissed_service, None)

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
        novel_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_dismissed_service] = (
            lambda: mock_dismissed_service  # type: ignore[assignment]
        )
        try:
            resp = await client.get(
                f"/api/v1/novels/{novel_id}/kb/consistency/dismissed",
            )
        finally:
            app.dependency_overrides.pop(get_dismissed_service, None)

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
        novel_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_dismissed_service] = (
            lambda: mock_dismissed_service  # type: ignore[assignment]
        )
        try:
            resp = await client.delete(
                f"/api/v1/novels/{novel_id}/kb/consistency/dismissed/fp-1",
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_dismissed_service, None)

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
        novel_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_dismissed_service] = (
            lambda: mock_dismissed_service  # type: ignore[assignment]
        )

        raw_fingerprint = "Ages conflict::Alice,Bob"
        encoded = quote(raw_fingerprint, safe="")

        try:
            resp = await client.delete(
                f"/api/v1/novels/{novel_id}/kb/consistency/dismissed/{encoded}",
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_dismissed_service, None)

        assert resp.status_code == 200
        # Verify the service received the decoded fingerprint — and the
        # authenticated identity threaded for the ownership gate (IDOR S10).
        # The user id is random per test run, so inspect kwargs instead of
        # exact-matching the call.
        call = mock_dismissed_service.undismiss_finding.call_args
        assert call is not None
        assert call.kwargs["novel_id"] == UUID(novel_id)
        assert call.kwargs["fingerprint"] == raw_fingerprint
        assert UUID(call.kwargs["user_id"])

    async def test_undismiss_returns_401_without_auth(
        self,
        client: AsyncClient,
        app: FastAPI,
        mock_dismissed_service: MagicMock,
    ) -> None:
        """DELETE undismiss returns 401 without auth token."""
        novel_id = "00000000-0000-0000-0000-000000000001"
        app.dependency_overrides[get_dismissed_service] = (
            lambda: mock_dismissed_service  # type: ignore[assignment]
        )
        try:
            resp = await client.delete(
                f"/api/v1/novels/{novel_id}/kb/consistency/dismissed/fp-1",
            )
        finally:
            app.dependency_overrides.pop(get_dismissed_service, None)

        assert resp.status_code == 401
