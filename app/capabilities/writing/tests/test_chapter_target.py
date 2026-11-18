"""The chapter's word goal (W4 Task 19, D8/D20): read, set, clear.

The ribbon's chapter-target pill reads the row's own ``target_words`` and
the inline setter writes it through the chapter PUT. The field is
present-and-nullable — an absent field is no change, a carried ``null``
clears the goal back to the honest unset — and answers to the kernel
contract's shared word-goal bounds, the novel target's own.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.kernel.contracts.models import WORD_GOAL_MAX, WORD_GOAL_MIN
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _chapter(client: AsyncClient, title: str = "Ankunft") -> dict[str, Any]:
    novel = await client.post("/api/writing/novels", json={"title": "Der Nebel"})
    chapter = await client.post(
        f"/api/writing/novels/{novel.json()['id']}/chapters", json={"title": title}
    )
    assert chapter.status_code == 201
    return chapter.json()


async def test_a_new_chapter_carries_no_goal() -> None:
    async with _client() as client:
        chapter = await _chapter(client)
        assert chapter["target_words"] is None
        read = await client.get(f"/api/writing/chapters/{chapter['id']}")
        assert read.json()["target_words"] is None


async def test_the_goal_round_trips_through_the_chapter_put() -> None:
    async with _client() as client:
        chapter = await _chapter(client)
        written = await client.put(
            f"/api/writing/chapters/{chapter['id']}", json={"target_words": 1000}
        )
        assert written.status_code == 200
        assert written.json()["target_words"] == 1000

        read = await client.get(f"/api/writing/chapters/{chapter['id']}")
        assert read.json()["target_words"] == 1000
        # The list carries it too — the ribbon reads the row it already has.
        listed = await client.get(f"/api/writing/novels/{chapter['novel_id']}/chapters")
        assert listed.json()[0]["target_words"] == 1000


async def test_a_carried_null_clears_the_goal() -> None:
    async with _client() as client:
        chapter = await _chapter(client)
        await client.put(f"/api/writing/chapters/{chapter['id']}", json={"target_words": 1000})
        cleared = await client.put(
            f"/api/writing/chapters/{chapter['id']}", json={"target_words": None}
        )
        assert cleared.status_code == 200
        assert cleared.json()["target_words"] is None


async def test_an_absent_field_is_no_change() -> None:
    async with _client() as client:
        chapter = await _chapter(client)
        await client.put(f"/api/writing/chapters/{chapter['id']}", json={"target_words": 1000})
        # A title edit carries no goal — the goal stands.
        renamed = await client.put(
            f"/api/writing/chapters/{chapter['id']}", json={"title": "Nacht"}
        )
        assert renamed.json()["title"] == "Nacht"
        assert renamed.json()["target_words"] == 1000
        # An empty body carries nothing at all.
        empty = await client.put(f"/api/writing/chapters/{chapter['id']}", json={})
        assert empty.json()["target_words"] == 1000


@pytest.mark.parametrize("value", [0, -1, WORD_GOAL_MAX + 1])
async def test_a_goal_outside_the_shared_bounds_is_refused_by_name(value: int) -> None:
    async with _client() as client:
        chapter = await _chapter(client)
        refused = await client.put(
            f"/api/writing/chapters/{chapter['id']}", json={"target_words": value}
        )
        assert refused.status_code == 422
        assert "target_words" in refused.json()["detail"]


@pytest.mark.parametrize("value", [WORD_GOAL_MIN, WORD_GOAL_MAX])
async def test_the_boundaries_the_column_holds_are_accepted(value: int) -> None:
    async with _client() as client:
        chapter = await _chapter(client)
        written = await client.put(
            f"/api/writing/chapters/{chapter['id']}", json={"target_words": value}
        )
        assert written.status_code == 200
        assert written.json()["target_words"] == value


async def test_a_foreign_chapters_goal_cannot_be_written() -> None:
    await seed_user(OTHER_USER)
    async with Session() as session:
        novel_id, chapter_id = uuid4(), uuid4()
        await session.execute(
            text(
                "INSERT INTO novels (id, user_id, title, created_at, updated_at) "
                "VALUES (:id, :user_id, :title, now(), now())"
            ),
            {"id": novel_id, "user_id": OTHER_USER, "title": "Fremd"},
        )
        await session.execute(
            text(
                "INSERT INTO chapters "
                "(id, user_id, novel_id, title, position, created_at, updated_at) "
                "VALUES (:id, :user_id, :novel_id, :title, 0, now(), now())"
            ),
            {"id": chapter_id, "user_id": OTHER_USER, "novel_id": novel_id, "title": "Fremd"},
        )
        await session.commit()

    async with _client() as client:
        refused = await client.put(
            f"/api/writing/chapters/{chapter_id}", json={"target_words": 500}
        )
        assert refused.status_code == 404
