"""Integration tests for KB improve API endpoints.

Tests POST /improve and POST /improve/apply with mocked
KBImproveService via dependency_overrides.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.kb.dependencies import get_kb_improve_service
from narrare.kb.improve_contracts import (
    ImproveSuggestionResponse,
    KBImproveAnalysisResponse,
    KBImproveApplyResponse,
)
from narrare.kb.improve_service import KBImproveService

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import FastAPI
    from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_improve_service() -> MagicMock:
    """Create a mocked KBImproveService for dependency override."""
    service = MagicMock(spec=KBImproveService)

    # Default: analyze returns 2 suggestions
    service.analyze = AsyncMock(
        return_value=KBImproveAnalysisResponse(
            suggestions=[
                ImproveSuggestionResponse(
                    type="add_field",
                    target="personality",
                    description="Add personality trait",
                    proposed_content="Brave and cunning",
                    confidence=0.85,
                    reasoning="Notable trait missing",
                    suggestion_id=0,
                ),
                ImproveSuggestionResponse(
                    type="connect",
                    target="mentor",
                    description="Connect to mentor figure",
                    proposed_content="Gandalf",
                    related_entity_id=str(uuid4()),
                    related_entity_name="Gandalf",
                    confidence=0.75,
                    reasoning="Mentor relationship",
                    suggestion_id=1,
                ),
            ],
            overall_assessment="Entry needs more detail",
            completeness_score=0.4,
        )
    )

    # Default: apply returns success
    service.apply = AsyncMock(
        return_value=KBImproveApplyResponse(
            success=True,
            entry_id=str(uuid4()),
            applied_count=2,
            message="2 improvement(s) applied (1 new connection(s)).",
        )
    )

    return service


# ---------------------------------------------------------------------------
# Tests: POST /improve
# ---------------------------------------------------------------------------


class TestImproveEndpoint:
    """Test POST /novels/{id}/kb/entities/{id}/improve."""

    async def test_improve_returns_200_with_suggestions(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_improve_service: MagicMock,
    ) -> None:
        """POST /improve returns 200 with KBImproveAnalysisResponse schema."""
        novel_id = uuid4()
        entry_id = uuid4()

        # Override the dependency
        app.dependency_overrides[get_kb_improve_service] = cast(
            "Callable[[], Any]", lambda: mock_improve_service
        )
        try:
            resp = await client.post(
                f"/api/v1/novels/{novel_id}/kb/entities/{entry_id}/improve",
                headers=auth_headers,
            )
        finally:
            # The app fixture is session-scoped — an override left behind
            # leaks into subsequent tests (order-dependent flakiness under
            # pytest-randomly). Same cleanup convention as
            # tests/integration/analysis/test_analysis_api.py.
            app.dependency_overrides.pop(get_kb_improve_service, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) == 2
        assert data["overall_assessment"] == "Entry needs more detail"
        assert data["completeness_score"] == 0.4

        # Verify suggestion schema
        first = data["suggestions"][0]
        assert first["type"] == "add_field"
        assert first["target"] == "personality"
        assert first["confidence"] == 0.85
        assert first["suggestion_id"] == 0

    async def test_improve_returns_401_without_auth(
        self,
        client: AsyncClient,
        app: FastAPI,
        mock_improve_service: MagicMock,
    ) -> None:
        """POST /improve returns 401 when no auth token is provided."""
        novel_id = uuid4()
        entry_id = uuid4()

        app.dependency_overrides[get_kb_improve_service] = cast(
            "Callable[[], Any]", lambda: mock_improve_service
        )
        try:
            resp = await client.post(
                f"/api/v1/novels/{novel_id}/kb/entities/{entry_id}/improve",
            )
        finally:
            app.dependency_overrides.pop(get_kb_improve_service, None)

        assert resp.status_code == 401

    async def test_improve_returns_422_with_invalid_novel_id(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_improve_service: MagicMock,
    ) -> None:
        """POST /improve returns 422 when novel_id is not a valid UUID."""
        app.dependency_overrides[get_kb_improve_service] = cast(
            "Callable[[], Any]", lambda: mock_improve_service
        )
        try:
            resp = await client.post(
                "/api/v1/novels/not-a-uuid/kb/entities/not-a-uuid/improve",
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_kb_improve_service, None)

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: POST /improve/apply
# ---------------------------------------------------------------------------


class TestImproveApplyEndpoint:
    """Test POST /novels/{id}/kb/entities/{id}/improve/apply."""

    async def test_apply_returns_200(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_improve_service: MagicMock,
    ) -> None:
        """POST /improve/apply returns 200 with KBImproveApplyResponse schema."""
        novel_id = uuid4()
        entry_id = uuid4()

        app.dependency_overrides[get_kb_improve_service] = cast(
            "Callable[[], Any]", lambda: mock_improve_service
        )
        try:
            resp = await client.post(
                f"/api/v1/novels/{novel_id}/kb/entities/{entry_id}/improve/apply",
                json={"suggestion_ids": [0, 1]},
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_kb_improve_service, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["applied_count"] == 2
        assert "entry_id" in data

    async def test_apply_returns_401_without_auth(
        self,
        client: AsyncClient,
        app: FastAPI,
        mock_improve_service: MagicMock,
    ) -> None:
        """POST /improve/apply returns 401 when no auth token is provided."""
        novel_id = uuid4()
        entry_id = uuid4()

        app.dependency_overrides[get_kb_improve_service] = cast(
            "Callable[[], Any]", lambda: mock_improve_service
        )
        try:
            resp = await client.post(
                f"/api/v1/novels/{novel_id}/kb/entities/{entry_id}/improve/apply",
                json={"suggestion_ids": [0]},
            )
        finally:
            app.dependency_overrides.pop(get_kb_improve_service, None)

        assert resp.status_code == 401

    async def test_apply_returns_422_with_invalid_body(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_improve_service: MagicMock,
    ) -> None:
        """POST /improve/apply returns 422 when body is malformed."""
        novel_id = uuid4()
        entry_id = uuid4()

        app.dependency_overrides[get_kb_improve_service] = cast(
            "Callable[[], Any]", lambda: mock_improve_service
        )
        try:
            # Missing suggestion_ids field
            resp = await client.post(
                f"/api/v1/novels/{novel_id}/kb/entities/{entry_id}/improve/apply",
                json={},
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_kb_improve_service, None)

        assert resp.status_code == 422

    async def test_apply_returns_422_with_invalid_suggestion_ids_type(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_improve_service: MagicMock,
    ) -> None:
        """POST /improve/apply returns 422 when suggestion_ids is not a list."""
        novel_id = uuid4()
        entry_id = uuid4()

        app.dependency_overrides[get_kb_improve_service] = cast(
            "Callable[[], Any]", lambda: mock_improve_service
        )
        try:
            # suggestion_ids as string instead of list
            resp = await client.post(
                f"/api/v1/novels/{novel_id}/kb/entities/{entry_id}/improve/apply",
                json={"suggestion_ids": "not-a-list"},
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_kb_improve_service, None)

        assert resp.status_code == 422
