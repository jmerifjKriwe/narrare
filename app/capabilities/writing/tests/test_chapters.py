"""Chapters: creation, ordering, saving the body, and the user boundary."""

from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.kernel.db.session import Session

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_novel(client: AsyncClient, title: str = "Der Nebel") -> str:
    response = await client.post("/api/writing/novels", json={"title": title})
    return response.json()["id"]


async def test_chapters_are_listed_in_creation_order() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client)
        for title in ("Ankunft", "Nacht", "Abfahrt"):
            created = await client.post(
                f"/api/writing/novels/{novel_id}/chapters", json={"title": title}
            )
            assert created.status_code == 201

        listed = await client.get(f"/api/writing/novels/{novel_id}/chapters")
        assert [chapter["title"] for chapter in listed.json()] == [
            "Ankunft",
            "Nacht",
            "Abfahrt",
        ]
        assert [chapter["position"] for chapter in listed.json()] == [0, 1, 2]


async def test_saving_the_body_persists_it() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client)
        chapter = (
            await client.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": "Ankunft"})
        ).json()

        saved = await client.put(
            f"/api/writing/chapters/{chapter['id']}",
            json={"body": "Der Nebel kam von See."},
        )
        assert saved.status_code == 200

        reloaded = await client.get(f"/api/writing/chapters/{chapter['id']}")
        assert reloaded.json()["body"] == "Der Nebel kam von See."


async def test_a_chapter_cannot_be_added_to_another_users_novel() -> None:
    async with Session() as session:
        novel_id = uuid4()
        await session.execute(
            text(
                "INSERT INTO novels (id, user_id, title, created_at) "
                "VALUES (:id, :user_id, :title, now())"
            ),
            {"id": novel_id, "user_id": OTHER_USER, "title": "Fremd"},
        )
        await session.commit()

    async with _client() as client:
        created = await client.post(
            f"/api/writing/novels/{novel_id}/chapters", json={"title": "Eindringen"}
        )
        assert created.status_code == 404


async def test_another_users_chapter_cannot_be_saved() -> None:
    async with Session() as session:
        novel_id, chapter_id = uuid4(), uuid4()
        await session.execute(
            text(
                "INSERT INTO novels (id, user_id, title, created_at) "
                "VALUES (:id, :user_id, :title, now())"
            ),
            {"id": novel_id, "user_id": OTHER_USER, "title": "Fremd"},
        )
        await session.execute(
            text(
                "INSERT INTO chapters "
                "(id, user_id, novel_id, title, position, body, created_at) "
                "VALUES (:id, :user_id, :novel_id, :title, 0, '', now())"
            ),
            {
                "id": chapter_id,
                "user_id": OTHER_USER,
                "novel_id": novel_id,
                "title": "Fremd",
            },
        )
        await session.commit()

    async with _client() as client:
        saved = await client.put(
            f"/api/writing/chapters/{chapter_id}", json={"body": "Überschrieben"}
        )
        assert saved.status_code == 404
