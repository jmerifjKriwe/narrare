"""Integration tests for memory API endpoints — including analyze endpoint.

These tests are marked as skip because they require a running database.
They serve as documentation and can be run in CI with proper infrastructure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from httpx import AsyncClient

import pytest

pytestmark = pytest.mark.skip(reason="temporarily disabled due to test infrastructure issues")


class TestRecordFeedback:
    async def test_record_feedback_with_rating_returns_201(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """POST /memory/feedback with rating returns 201."""
        response = await client.post(
            "/api/v1/memory/feedback",
            json={
                "action": "accept",
                "suggestion_id": str(uuid4()),
                "intent": "write",
                "suggestion_text": "The forest was dark.",
                "rating": 4,
                "project_id": str(uuid4()),
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["action"] == "accept"

    async def test_record_feedback_with_enriched_context(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """POST /memory/feedback with chapter_id, genre, mode."""
        response = await client.post(
            "/api/v1/memory/feedback",
            json={
                "action": "accept",
                "suggestion_id": str(uuid4()),
                "intent": "write",
                "suggestion_text": "The forest was dark.",
                "project_id": str(uuid4()),
                "chapter_id": str(uuid4()),
                "genre": "Fantasy",
                "mode": "creative",
                "rating": 5,
            },
            headers=auth_headers,
        )
        assert response.status_code == 201

    async def test_record_feedback_invalid_rating_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """POST /memory/feedback with rating > 5 returns 422."""
        response = await client.post(
            "/api/v1/memory/feedback",
            json={
                "action": "accept",
                "suggestion_id": str(uuid4()),
                "intent": "write",
                "suggestion_text": "Text",
                "project_id": str(uuid4()),
                "rating": 6,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_record_feedback_rating_zero_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """POST /memory/feedback with rating 0 returns 422."""
        response = await client.post(
            "/api/v1/memory/feedback",
            json={
                "action": "accept",
                "suggestion_id": str(uuid4()),
                "intent": "write",
                "suggestion_text": "Text",
                "project_id": str(uuid4()),
                "rating": 0,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestAnalyzePreferences:
    async def test_analyze_with_too_few_events_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """POST /memory/analyze with < 5 events returns 422."""
        response = await client.post(
            "/api/v1/memory/analyze",
            json={"project_id": str(uuid4())},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_analyze_without_auth_returns_401(self, client: AsyncClient) -> None:
        """POST /memory/analyze without auth returns 401."""
        response = await client.post(
            "/api/v1/memory/analyze",
            json={"project_id": str(uuid4())},
        )
        assert response.status_code == 401

    async def test_analyze_returns_correct_schema(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """POST /memory/analyze returns AnalyzeResponse schema.

        This test requires seeding 5+ feedback events first.
        """
        project_id = uuid4()

        # Seed 5 feedback events
        for _ in range(5):
            await client.post(
                "/api/v1/memory/feedback",
                json={
                    "action": "accept",
                    "suggestion_id": str(uuid4()),
                    "intent": "write",
                    "suggestion_text": "Good text.",
                    "project_id": str(project_id),
                    "rating": 4,
                },
                headers=auth_headers,
            )

        response = await client.post(
            "/api/v1/memory/analyze",
            json={"project_id": str(project_id)},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "user_id" in data
        assert "project_id" in data
        assert "confidence" in data
        assert "summary" in data
        assert "style_patterns" in data
        assert "content_patterns" in data
        assert "avoidance_patterns" in data
        assert "event_count_at_analysis" in data
