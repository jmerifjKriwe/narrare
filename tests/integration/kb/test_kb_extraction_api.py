"""Integration tests for KB extraction API endpoints.

Tests POST /novels/{novel_id}/kb/extract/{chapter_id} and
POST /novels/{novel_id}/kb/extract/apply with mocked
ExtractionService via dependency_overrides.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.kb.extraction_service import ExtractionService
from narrare.kb.schemas_extraction import ApplyExtractionEntryResult, ApplyExtractionResponse
from narrare_core.agents.extraction_types import ExtractionItem, ExtractionOutput

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_item(name: str, entity_type: str) -> MagicMock:
    """Create a mock extraction result item with model_dump."""
    item = MagicMock(spec=ExtractionItem)
    item.model_dump.return_value = {
        "type": "new_entity",
        "name": name,
        "entity_type": entity_type,
    }
    return item


@pytest.fixture
def mock_extraction_service() -> MagicMock:
    """Create a mocked ExtractionService for dependency override."""
    service = MagicMock(spec=ExtractionService)

    # Default: extract_from_chapter returns 2 items
    mock_result = MagicMock(spec=ExtractionOutput)
    mock_result.results = [
        _make_mock_item("Alice", "character"),
        _make_mock_item("Wonderland", "location"),
    ]
    mock_result.analysis_notes = [
        "Found 2 entities in chapter text.",
        "1 potential relationship detected.",
    ]
    service.extract_from_chapter = AsyncMock(return_value=mock_result)

    # Default: apply_extraction returns created entries
    service.apply_extraction = AsyncMock(
        return_value=ApplyExtractionResponse(
            created_entries=[
                ApplyExtractionEntryResult(
                    id=str(uuid4()),
                    name="Alice",
                    entity_type="character",
                ),
            ],
            updated_entries=[],
        ),
    )

    return service


@pytest.fixture
def mock_extraction_service_empty(mock_extraction_service: MagicMock) -> MagicMock:
    """ExtractionService mock returning empty results."""
    mock_result = MagicMock(spec=ExtractionOutput)
    mock_result.results = []
    mock_result.analysis_notes = ["No entities found in chapter text."]
    mock_extraction_service.extract_from_chapter = AsyncMock(return_value=mock_result)
    return mock_extraction_service


@pytest.fixture
def mock_extraction_service_empty_apply(mock_extraction_service: MagicMock) -> MagicMock:
    """ExtractionService mock returning empty apply results."""
    mock_extraction_service.apply_extraction = AsyncMock(
        return_value=ApplyExtractionResponse(
            created_entries=[],
            updated_entries=[],
        ),
    )
    return mock_extraction_service


# ---------------------------------------------------------------------------
# Tests: POST /novels/{novel_id}/kb/extract/{chapter_id}
# ---------------------------------------------------------------------------


class TestExtractChapter:
    """Test POST /novels/{novel_id}/kb/extract/{chapter_id}."""

    async def test_extract_returns_200_with_results(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_extraction_service: MagicMock,
    ) -> None:
        """POST /extract returns 200 with results and analysis_notes."""
        from narrare.kb.dependencies import get_extraction_service

        novel_id = uuid4()
        chapter_id = uuid4()

        app.dependency_overrides[get_extraction_service] = lambda: mock_extraction_service  # type: ignore[assignment]

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/extract/{chapter_id}",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "analysis_notes" in data
        assert len(data["results"]) == 2
        assert data["results"][0]["name"] == "Alice"
        assert data["results"][0]["entity_type"] == "character"
        assert data["results"][1]["name"] == "Wonderland"
        assert data["analysis_notes"] == [
            "Found 2 entities in chapter text.",
            "1 potential relationship detected.",
        ]

    async def test_extract_returns_200_with_empty_results(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_extraction_service_empty: MagicMock,
    ) -> None:
        """POST /extract returns 200 with empty results when nothing found."""
        from narrare.kb.dependencies import get_extraction_service

        novel_id = uuid4()
        chapter_id = uuid4()

        app.dependency_overrides[get_extraction_service] = lambda: mock_extraction_service_empty  # type: ignore[assignment]

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/extract/{chapter_id}",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []
        assert data["analysis_notes"] == ["No entities found in chapter text."]

    async def test_extract_returns_401_without_auth(
        self,
        client: AsyncClient,
        app: FastAPI,
        mock_extraction_service: MagicMock,
    ) -> None:
        """POST /extract returns 401 when no auth token is provided."""
        from narrare.kb.dependencies import get_extraction_service

        novel_id = uuid4()
        chapter_id = uuid4()

        app.dependency_overrides[get_extraction_service] = lambda: mock_extraction_service  # type: ignore[assignment]

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/extract/{chapter_id}",
        )

        assert resp.status_code == 401

    async def test_extract_returns_422_with_invalid_uuid(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_extraction_service: MagicMock,
    ) -> None:
        """POST /extract returns 422 when novel_id is not a valid UUID."""
        from narrare.kb.dependencies import get_extraction_service

        chapter_id = uuid4()

        app.dependency_overrides[get_extraction_service] = lambda: mock_extraction_service  # type: ignore[assignment]

        resp = await client.post(
            f"/api/v1/novels/not-a-uuid/kb/extract/{chapter_id}",
            headers=auth_headers,
        )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: POST /novels/{novel_id}/kb/extract/apply
# ---------------------------------------------------------------------------


class TestApplyExtraction:
    """Test POST /novels/{novel_id}/kb/extract/apply."""

    async def test_apply_returns_200_with_created_entries(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_extraction_service: MagicMock,
    ) -> None:
        """POST /extract/apply returns 200 with ApplyExtractionResponse schema."""
        from narrare.kb.dependencies import get_extraction_service

        novel_id = uuid4()

        app.dependency_overrides[get_extraction_service] = lambda: mock_extraction_service  # type: ignore[assignment]

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/extract/apply",
            json={
                "items": [
                    {
                        "item_type": "new_entity",
                        "name": "Alice",
                        "entity_type": "character",
                        "proposed_content": {"description": "A curious girl"},
                        "source_text": "Alice was beginning to get very tired",
                    },
                ],
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "created_entries" in data
        assert "updated_entries" in data
        assert len(data["created_entries"]) == 1
        assert data["created_entries"][0]["name"] == "Alice"
        assert data["created_entries"][0]["entity_type"] == "character"
        assert "id" in data["created_entries"][0]
        assert data["updated_entries"] == []

    async def test_apply_returns_200_with_empty_results(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_extraction_service_empty_apply: MagicMock,
    ) -> None:
        """POST /extract/apply returns 200 when nothing is created or updated."""
        from narrare.kb.dependencies import get_extraction_service

        novel_id = uuid4()

        app.dependency_overrides[get_extraction_service] = lambda: (
            mock_extraction_service_empty_apply
        )  # type: ignore[assignment]

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/extract/apply",
            json={
                "items": [
                    {
                        "item_type": "conflict",
                        "name": "Unknown",
                        "source_text": "Ambiguous reference",
                    },
                ],
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["created_entries"] == []
        assert data["updated_entries"] == []

    async def test_apply_returns_401_without_auth(
        self,
        client: AsyncClient,
        app: FastAPI,
        mock_extraction_service: MagicMock,
    ) -> None:
        """POST /extract/apply returns 401 when no auth token is provided."""
        from narrare.kb.dependencies import get_extraction_service

        novel_id = uuid4()

        app.dependency_overrides[get_extraction_service] = lambda: mock_extraction_service  # type: ignore[assignment]

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/extract/apply",
            json={
                "items": [
                    {
                        "item_type": "new_entity",
                        "name": "Alice",
                        "entity_type": "character",
                    },
                ],
            },
        )

        assert resp.status_code == 401

    async def test_apply_returns_422_with_invalid_body(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_extraction_service: MagicMock,
    ) -> None:
        """POST /extract/apply returns 422 when body is missing required fields."""
        from narrare.kb.dependencies import get_extraction_service

        novel_id = uuid4()

        app.dependency_overrides[get_extraction_service] = lambda: mock_extraction_service  # type: ignore[assignment]

        # Missing "items" field entirely
        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/extract/apply",
            json={},
            headers=auth_headers,
        )

        assert resp.status_code == 422

    async def test_apply_returns_422_with_invalid_item_type(
        self,
        client: AsyncClient,
        app: FastAPI,
        auth_headers: dict[str, str],
        mock_extraction_service: MagicMock,
    ) -> None:
        """POST /extract/apply returns 422 when item_type is not a valid literal."""
        from narrare.kb.dependencies import get_extraction_service

        novel_id = uuid4()

        app.dependency_overrides[get_extraction_service] = lambda: mock_extraction_service  # type: ignore[assignment]

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/extract/apply",
            json={
                "items": [
                    {
                        "item_type": "invalid_type",
                        "name": "Alice",
                    },
                ],
            },
            headers=auth_headers,
        )

        assert resp.status_code == 422
