"""Integration tests for KB consistency check API endpoint.

Tests POST /novels/{id}/kb/consistency-check with mocked
KBConsistencyService via dependency_overrides.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.kb.consistency_contracts import ConsistencyCheckResponse
from narrare.kb.consistency_service import KBConsistencyService

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_consistency_service() -> MagicMock:
    """Create a mocked KBConsistencyService for dependency override."""
    service = MagicMock(spec=KBConsistencyService)

    # Default: check returns a valid response
    service.check = AsyncMock(
        return_value=ConsistencyCheckResponse(
            novel_id=str(uuid4()),
            entity_count=5,
            issues=[],
            summary={"entry_internal": 0, "asymmetry": 0, "cross_entity": 0},
            checked_at="2025-01-01T00:00:00Z",
        )
    )

    return service


# ---------------------------------------------------------------------------
# Tests: POST /consistency-check
# ---------------------------------------------------------------------------


class TestConsistencyCheckEndpoint:
    """Test POST /novels/{id}/kb/consistency-check."""

    async def test_consistency_check_endpoint_returns_200(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_consistency_service: MagicMock,
    ) -> None:
        """POST /consistency-check returns 200 with ConsistencyCheckResponse schema."""
        from narrare.kb.dependencies import get_consistency_service

        novel_id = uuid4()

        app.dependency_overrides[get_consistency_service] = lambda: mock_consistency_service  # type: ignore[assignment]

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/consistency-check",
            json={"include_entry_internal": True, "include_asymmetry": True},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "issues" in data
        assert "summary" in data
        assert "entity_count" in data
        assert "novel_id" in data
        assert "checked_at" in data

    async def test_consistency_check_endpoint_returns_401_without_auth(
        self,
        client: AsyncClient,
        app: FastAPI,
        mock_consistency_service: MagicMock,
    ) -> None:
        """POST /consistency-check returns 401 when no auth token is provided."""
        from narrare.kb.dependencies import get_consistency_service

        novel_id = uuid4()

        app.dependency_overrides[get_consistency_service] = lambda: mock_consistency_service  # type: ignore[assignment]

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/consistency-check",
            json={"include_entry_internal": True},
        )

        assert resp.status_code == 401
