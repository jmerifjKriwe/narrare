"""Integration tests for timeline consistency and extraction API endpoints (PLAN-004 Phase 2).

Tests the GET /planning/timeline/{novel_id}/consistency and
POST /planning/timeline/{novel_id}/extract endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.fixture
async def novel_with_events(client: AsyncClient, auth_headers: dict[str, str]) -> dict[str, object]:
    """Create a novel with chapters and timeline events, return IDs."""
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": "Consistency Test Novel", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    # Create a chapter
    ch_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": "Chapter 1", "content": "The hero arrived three days later."},
        headers=auth_headers,
    )
    assert ch_resp.status_code == 201
    chapter_id = ch_resp.json()["id"]

    # Create some timeline events
    event_ids = []
    for i in range(3):
        event_resp = await client.post(
            f"/api/v1/planning/timeline/{novel_id}/events",
            json={
                "event_name": f"Event {i + 1}",
                "timestamp_raw": f"Day {i + 1}",
                "temporal_order": i + 1,
            },
            headers=auth_headers,
        )
        assert event_resp.status_code == 201
        event_ids.append(event_resp.json()["id"])

    return {"novel_id": novel_id, "chapter_id": chapter_id, "event_ids": event_ids}


class TestConsistencyEndpoint:
    """Test GET /planning/timeline/{novel_id}/consistency."""

    async def test_consistency_check_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_events: dict[str, object],
    ) -> None:
        """Consistency check should return 200 with deterministic results."""
        novel_id = novel_with_events["novel_id"]

        resp = await client.get(
            f"/api/v1/planning/timeline/{novel_id}/consistency",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert "issues" in data
        assert "deterministic_pass" in data
        assert "overall_assessment" in data
        assert isinstance(data["issues"], list)
        assert isinstance(data["deterministic_pass"], bool)

    async def test_consistency_check_nonexistent_novel_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Consistency check for nonexistent novel should return 404."""
        import uuid

        resp = await client.get(
            f"/api/v1/planning/timeline/{uuid.uuid4()}/consistency",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_consistency_check_unauthenticated_returns_401(
        self,
        client: AsyncClient,
        novel_with_events: dict[str, object],
    ) -> None:
        """Consistency check without auth should return 401."""
        novel_id = novel_with_events["novel_id"]

        resp = await client.get(
            f"/api/v1/planning/timeline/{novel_id}/consistency",
        )
        assert resp.status_code == 401

    async def test_consistency_with_duplicate_events(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Events with duplicate temporal_order should produce warnings."""
        # Create novel
        novel_resp = await client.post(
            "/api/v1/novels",
            json={"title": "Duplicate Events Novel", "language": "en"},
            headers=auth_headers,
        )
        assert novel_resp.status_code == 201
        novel_id = novel_resp.json()["id"]

        # Create two events with same temporal_order
        for _ in range(2):
            await client.post(
                f"/api/v1/planning/timeline/{novel_id}/events",
                json={
                    "event_name": "Duplicate Event",
                    "timestamp_raw": "Day 1",
                    "temporal_order": 1,
                },
                headers=auth_headers,
            )

        resp = await client.get(
            f"/api/v1/planning/timeline/{novel_id}/consistency",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        # Should have at least one issue about duplicate temporal_order
        duplicate_issues = [i for i in data["issues"] if i["rule_id"] == "duplicate_temporal_order"]
        assert len(duplicate_issues) >= 1


class TestExtractionEndpoint:
    """Test POST /planning/timeline/{novel_id}/extract."""

    async def test_extract_endpoint_exists(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_events: dict[str, object],
    ) -> None:
        """Extract endpoint should exist (not return 404).

        Note: The actual AI extraction requires a configured LLM provider.
        In integration tests without AI, this returns 500 or 422 depending
        on whether a provider is configured. The important thing is the
        route exists and is accessible.
        """
        novel_id = novel_with_events["novel_id"]

        resp = await client.post(
            f"/api/v1/planning/timeline/{novel_id}/extract",
            json={"chapter_ids": []},
            headers=auth_headers,
        )
        # Should not be 404 — route exists
        assert resp.status_code != 404

    async def test_extract_nonexistent_novel_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Extract for nonexistent novel should return 404."""
        import uuid

        resp = await client.post(
            f"/api/v1/planning/timeline/{uuid.uuid4()}/extract",
            json={"chapter_ids": []},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_extract_unauthenticated_returns_401(
        self,
        client: AsyncClient,
        novel_with_events: dict[str, object],
    ) -> None:
        """Extract without auth should return 401."""
        novel_id = novel_with_events["novel_id"]

        resp = await client.post(
            f"/api/v1/planning/timeline/{novel_id}/extract",
            json={"chapter_ids": []},
        )
        assert resp.status_code == 401

    async def test_extract_with_specific_chapter_ids(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_events: dict[str, object],
    ) -> None:
        """Extract with specific chapter_ids should not return 404."""
        novel_id = novel_with_events["novel_id"]
        chapter_id = novel_with_events["chapter_id"]

        resp = await client.post(
            f"/api/v1/planning/timeline/{novel_id}/extract",
            json={"chapter_ids": [chapter_id]},
            headers=auth_headers,
        )
        # Should not be 404 — route exists
        assert resp.status_code != 404
