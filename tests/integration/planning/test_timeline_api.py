"""Integration tests for timeline API endpoints.

Full API test cycle: create novel + chapters → POST event → GET events →
GET event → PUT event → DELETE event → verify deletion.
Also tests AI analysis endpoint backward compatibility.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.fixture
async def novel_with_chapters(
    client: AsyncClient, auth_headers: dict[str, str]
) -> dict[str, object]:
    """Create a novel with 3 chapters and return IDs."""
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": "Timeline Test Novel", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_ids = []
    for i in range(3):
        ch_resp = await client.post(
            f"/api/v1/novels/{novel_id}/chapters",
            json={"title": f"Chapter {i + 1}", "content": f"Content for chapter {i + 1}."},
            headers=auth_headers,
        )
        assert ch_resp.status_code == 201
        chapter_ids.append(ch_resp.json()["id"])

    return {"novel_id": novel_id, "chapter_ids": chapter_ids}


class TestCreateTimelineEvent:
    async def test_create_event_returns_201(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        novel_id = novel_with_chapters["novel_id"]

        resp = await client.post(
            f"/api/v1/planning/timeline/{novel_id}/events",
            json={
                "event_name": "Battle of Helm's Deep",
                "description": "The great battle at Helm's Deep",
                "event_type": "battle",
                "timestamp_raw": "Day 15",
                "temporal_order": 1,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()

        assert data["event_name"] == "Battle of Helm's Deep"
        assert data["event_type"] == "battle"
        assert data["source"] == "manual"
        assert data["is_confirmed"] is True
        assert "id" in data
        assert "created_at" in data

    async def test_create_event_with_chapter_ref(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        novel_id = novel_with_chapters["novel_id"]
        chapter_ids = cast("list[str]", novel_with_chapters["chapter_ids"])

        resp = await client.post(
            f"/api/v1/planning/timeline/{novel_id}/events",
            json={
                "event_name": "Arrival",
                "chapter_id": chapter_ids[0],
                "character_refs": [{"id": str(chapter_ids[0]), "name": "Aragorn"}],
                "location_ref": {"id": str(chapter_ids[1]), "name": "Rivendell"},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["character_refs"]) == 1
        assert data["location_ref"]["name"] == "Rivendell"

    async def test_create_event_nonexistent_novel_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        import uuid

        resp = await client.post(
            f"/api/v1/planning/timeline/{uuid.uuid4()}/events",
            json={"event_name": "Event"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_create_event_invalid_chapter_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        import uuid

        novel_id = novel_with_chapters["novel_id"]

        resp = await client.post(
            f"/api/v1/planning/timeline/{novel_id}/events",
            json={
                "event_name": "Event",
                "chapter_id": str(uuid.uuid4()),
            },
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestListTimelineEvents:
    async def test_list_events_returns_all(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        novel_id = novel_with_chapters["novel_id"]

        # Create 2 events
        for i in range(2):
            await client.post(
                f"/api/v1/planning/timeline/{novel_id}/events",
                json={"event_name": f"Event {i + 1}", "temporal_order": i + 1},
                headers=auth_headers,
            )

        resp = await client.get(
            f"/api/v1/planning/timeline/{novel_id}/events",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_list_events_with_event_type_filter(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        novel_id = novel_with_chapters["novel_id"]

        # Create events of different types
        await client.post(
            f"/api/v1/planning/timeline/{novel_id}/events",
            json={"event_name": "Plot Event", "event_type": "plot_point"},
            headers=auth_headers,
        )
        await client.post(
            f"/api/v1/planning/timeline/{novel_id}/events",
            json={"event_name": "Battle", "event_type": "battle"},
            headers=auth_headers,
        )

        resp = await client.get(
            f"/api/v1/planning/timeline/{novel_id}/events",
            params={"event_type": "battle"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["event_type"] == "battle"


class TestGetTimelineEvent:
    async def test_get_event_by_id(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        novel_id = novel_with_chapters["novel_id"]

        create_resp = await client.post(
            f"/api/v1/planning/timeline/{novel_id}/events",
            json={"event_name": "Get Me"},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        event_id = create_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/planning/timeline/{novel_id}/events/{event_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["event_name"] == "Get Me"

    async def test_get_nonexistent_event_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        import uuid

        novel_id = novel_with_chapters["novel_id"]

        resp = await client.get(
            f"/api/v1/planning/timeline/{novel_id}/events/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestUpdateTimelineEvent:
    async def test_update_event_changes_name(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        novel_id = novel_with_chapters["novel_id"]

        create_resp = await client.post(
            f"/api/v1/planning/timeline/{novel_id}/events",
            json={"event_name": "Old Name"},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        event_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/planning/timeline/{novel_id}/events/{event_id}",
            json={"event_name": "New Name", "description": "Updated desc"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_name"] == "New Name"
        assert data["description"] == "Updated desc"


class TestDeleteTimelineEvent:
    async def test_delete_event_returns_204(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        novel_id = novel_with_chapters["novel_id"]

        create_resp = await client.post(
            f"/api/v1/planning/timeline/{novel_id}/events",
            json={"event_name": "Delete Me"},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        event_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/planning/timeline/{novel_id}/events/{event_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

        # Verify it's gone
        get_resp = await client.get(
            f"/api/v1/planning/timeline/{novel_id}/events/{event_id}",
            headers=auth_headers,
        )
        assert get_resp.status_code == 404


class TestTimelineAnalysisBackwardCompat:
    async def test_analysis_endpoint_still_works(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        """Verify the existing GET /timeline/{novel_id} endpoint still responds.

        Note: The actual AI analysis requires a configured LLM provider.
        In integration tests without AI, this returns 500 or 422 depending
        on whether a provider is configured. The important thing is the route
        exists and is accessible (not 404).
        """
        novel_id = novel_with_chapters["novel_id"]

        resp = await client.get(
            f"/api/v1/planning/timeline/{novel_id}",
            headers=auth_headers,
        )
        # Should not be 404 — route exists. May be 500 if no AI provider.
        assert resp.status_code != 404
