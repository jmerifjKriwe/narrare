"""Integration tests for scene plan API endpoints (PLAN-001 T5).

Full API cycle: create novel + chapter → seed scene rows → GET the
aggregate → PUT diff-sync round-trip → verify the fresh aggregate.
Ownership is uid-scoped: an unknown novel AND another user's novel are
both 404 (foreign ≡ unknown).

PUT bodies always ROUND-TRIP a fetched aggregate (GET → mutate → PUT):
``SceneSchema`` requires client timestamps, so tests never hand-craft
them (T4 binding carry-forward).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from tests.integration.planning._scenes_api_helpers import (
    _seed_foreign_users_novel,
    _seed_scene,
)

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

_SCENE_WIRE_FIELDS = {
    "id",
    "position",
    "title",
    "pov_character_ref",
    "location_ref",
    "present_characters",
    "purpose",
    "conflict",
    "resolution",
    "beats",
    "status",
    "created_at",
    "updated_at",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class TestGetScenePlans:
    async def test_get_returns_seeded_scenes_ordered_by_position(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_and_chapter: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        novel_id = novel_and_chapter["novel_id"]
        chapter_id = novel_and_chapter["chapter_id"]
        await _seed_scene(db_session, chapter_id, 2, title="Scene B", status="in_progress")
        scene_a_id = await _seed_scene(db_session, chapter_id, 1, title="Scene A")

        resp = await client.get(
            f"/api/v1/planning/scenes/{novel_id}/{chapter_id}",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["chapter_id"] == chapter_id
        assert "version_updated_at" in data
        assert [scene["position"] for scene in data["scenes"]] == [1, 2]
        assert data["scenes"][0]["id"] == str(scene_a_id)
        assert data["scenes"][0]["title"] == "Scene A"
        assert data["scenes"][0]["status"] == "planned"
        assert data["scenes"][1]["status"] == "in_progress"
        for scene in data["scenes"]:
            assert set(scene) == _SCENE_WIRE_FIELDS

    async def test_get_returns_empty_aggregate_without_scenes(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_and_chapter: dict[str, str],
    ) -> None:
        novel_id = novel_and_chapter["novel_id"]
        chapter_id = novel_and_chapter["chapter_id"]

        resp = await client.get(
            f"/api/v1/planning/scenes/{novel_id}/{chapter_id}",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["chapter_id"] == chapter_id
        assert data["scenes"] == []
        assert "version_updated_at" in data

    async def test_get_unknown_novel_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_and_chapter: dict[str, str],
    ) -> None:
        chapter_id = novel_and_chapter["chapter_id"]

        resp = await client.get(
            f"/api/v1/planning/scenes/{uuid.uuid4()}/{chapter_id}",
            headers=auth_headers,
        )

        assert resp.status_code == 404

    async def test_get_chapter_of_other_novel_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_and_chapter: dict[str, str],
    ) -> None:
        """Chapter guard: a real chapter id presented under a foreign novel → 404."""
        second_novel_resp = await client.post(
            "/api/v1/novels",
            json={"title": "Second Novel", "language": "en"},
            headers=auth_headers,
        )
        assert second_novel_resp.status_code == 201
        second_novel_id = second_novel_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/planning/scenes/{second_novel_id}/{novel_and_chapter['chapter_id']}",
            headers=auth_headers,
        )

        assert resp.status_code == 404

    async def test_get_foreign_users_novel_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        """Another user's novel is indistinguishable from an unknown one."""
        foreign_novel_id, foreign_chapter_id = await _seed_foreign_users_novel(db_session)

        resp = await client.get(
            f"/api/v1/planning/scenes/{foreign_novel_id}/{foreign_chapter_id}",
            headers=auth_headers,
        )

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /planning/scenes/{novel_id}/{chapter_id} — diff-sync round-trip
# ---------------------------------------------------------------------------


class TestPutScenePlans:
    async def test_put_round_trip_inserts_updates_deletes_and_renumbers(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_and_chapter: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        """GET → mutate → PUT exercises every diff-sync branch in one round-trip."""
        novel_id = novel_and_chapter["novel_id"]
        chapter_id = novel_and_chapter["chapter_id"]
        scene_a_id = await _seed_scene(db_session, chapter_id, 1, title="Scene A")
        scene_b_id = await _seed_scene(db_session, chapter_id, 2, title="Scene B")
        url = f"/api/v1/planning/scenes/{novel_id}/{chapter_id}"

        fetched = (await client.get(url, headers=auth_headers)).json()["scenes"]
        assert [scene["id"] for scene in fetched] == [str(scene_a_id), str(scene_b_id)]

        # Insert: new client UUID; timestamps derived from the fetched payload.
        scene_c = {**fetched[0], "id": str(uuid.uuid4()), "title": "Scene C", "position": 1}
        # Update: same id, edited fields (created_at preserved by the server).
        scene_a = {
            **fetched[0],
            "title": "Scene A revised",
            "position": 2,
            "status": "in_progress",
            "beats": ["wake up", "open the door"],
        }
        # Scene B is absent from the payload → deleted.

        resp = await client.put(url, json={"scenes": [scene_c, scene_a]}, headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["chapter_id"] == chapter_id
        assert [scene["position"] for scene in data["scenes"]] == [1, 2]
        assert [scene["title"] for scene in data["scenes"]] == ["Scene C", "Scene A revised"]
        assert data["scenes"][0]["id"] == scene_c["id"]  # client UUID became the PK
        assert data["scenes"][1]["id"] == str(scene_a_id)
        assert str(scene_b_id) not in [scene["id"] for scene in data["scenes"]]
        assert data["scenes"][1]["status"] == "in_progress"
        assert data["scenes"][1]["beats"] == ["wake up", "open the door"]
        # created_at is server-owned: preserved on update (the PUT payload's
        # client timestamps are ignored by the repository mapping).
        assert data["scenes"][1]["created_at"] == fetched[0]["created_at"]

    async def test_put_result_is_persisted_for_subsequent_get(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_and_chapter: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        novel_id = novel_and_chapter["novel_id"]
        chapter_id = novel_and_chapter["chapter_id"]
        await _seed_scene(db_session, chapter_id, 1, title="Scene A")
        url = f"/api/v1/planning/scenes/{novel_id}/{chapter_id}"

        fetched = (await client.get(url, headers=auth_headers)).json()["scenes"]
        renamed = {**fetched[0], "title": "Renamed", "position": 1}
        put_resp = await client.put(url, json={"scenes": [renamed]}, headers=auth_headers)
        assert put_resp.status_code == 200

        refetched = (await client.get(url, headers=auth_headers)).json()
        assert [scene["title"] for scene in refetched["scenes"]] == ["Renamed"]

    async def test_put_unknown_novel_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_and_chapter: dict[str, str],
    ) -> None:
        chapter_id = novel_and_chapter["chapter_id"]

        resp = await client.put(
            f"/api/v1/planning/scenes/{uuid.uuid4()}/{chapter_id}",
            json={"scenes": []},
            headers=auth_headers,
        )

        assert resp.status_code == 404

    async def test_put_foreign_users_novel_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        foreign_novel_id, foreign_chapter_id = await _seed_foreign_users_novel(db_session)

        resp = await client.put(
            f"/api/v1/planning/scenes/{foreign_novel_id}/{foreign_chapter_id}",
            json={"scenes": []},
            headers=auth_headers,
        )

        assert resp.status_code == 404

    async def test_put_duplicate_scene_id_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_and_chapter: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        novel_id = novel_and_chapter["novel_id"]
        chapter_id = novel_and_chapter["chapter_id"]
        await _seed_scene(db_session, chapter_id, 1, title="Scene A")
        url = f"/api/v1/planning/scenes/{novel_id}/{chapter_id}"

        fetched = (await client.get(url, headers=auth_headers)).json()["scenes"]
        duplicate = {**fetched[0], "position": 2}

        resp = await client.put(
            url,
            json={"scenes": [fetched[0], duplicate]},
            headers=auth_headers,
        )

        assert resp.status_code == 422
