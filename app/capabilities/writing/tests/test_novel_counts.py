"""Derived counts: the shelf says how long a novel is, without opening it.

The rule is the wave's single one: a word is a whitespace-separated
token of the body after trimming, and a body that trims empty counts 0.
Whitespace is PostgreSQL's ``[[:space:]]`` plus the three near spaces a
browser counts too (R31): NBSP, figure space, narrow no-break space.
"""

from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_novel(client: AsyncClient, title: str) -> str:
    response = await client.post("/api/writing/novels", json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


async def _add_chapter(client: AsyncClient, novel_id: str, body: str) -> None:
    created = await client.post(
        f"/api/writing/novels/{novel_id}/chapters", json={"title": "Kapitel"}
    )
    assert created.status_code == 201
    saved = await client.put(
        f"/api/writing/chapters/{created.json()['id']}",
        json={"body": body},
    )
    assert saved.status_code == 200


async def _novel_row(client: AsyncClient, novel_id: str) -> dict[str, object]:
    listed = (await client.get("/api/writing/novels")).json()
    return next(novel for novel in listed if novel["id"] == novel_id)


async def test_counts_count_chapters_and_words() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Der Nebel")
        await _add_chapter(client, novel_id, "eins zwei drei")
        await _add_chapter(client, novel_id, "vier")

        row = await _novel_row(client, novel_id)
        assert row["chapter_count"] == 2
        assert row["word_count"] == 4

        # The single-novel payload carries the same counts, not zeros.
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.json()["chapter_count"] == 2
        assert fetched.json()["word_count"] == 4


async def test_a_novel_without_chapters_reports_zeros() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Leer")

        row = await _novel_row(client, novel_id)
        assert row["chapter_count"] == 0
        assert row["word_count"] == 0


async def test_empty_and_whitespace_bodies_contribute_no_words() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Stumm")
        await _add_chapter(client, novel_id, "")
        await _add_chapter(client, novel_id, "   \t\n  ")

        row = await _novel_row(client, novel_id)
        # Both chapters exist — they just say nothing.
        assert row["chapter_count"] == 2
        assert row["word_count"] == 0


async def test_near_spaces_are_whitespace() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Abstand")
        # NBSP between words: two words, not one glued token (R31).
        await _add_chapter(client, novel_id, "a" + chr(160) + "b")
        # A body of only near spaces says nothing at all.
        await _add_chapter(client, novel_id, chr(160))
        await _add_chapter(client, novel_id, chr(0x2007) + chr(0x202F))

        row = await _novel_row(client, novel_id)
        assert row["chapter_count"] == 3
        assert row["word_count"] == 2


async def test_another_users_chapter_does_not_count() -> None:
    async with _client() as client:
        novel_id = await _create_novel(client, "Mein")
        await _add_chapter(client, novel_id, "eins")

        # A foreign user's chapter row, attached to my novel — the user
        # boundary, not the novel's, decides what the count sees.
        await seed_user(OTHER_USER)
        async with Session() as session:
            await session.execute(
                text(
                    "INSERT INTO chapters (id, user_id, novel_id, title, position, body, "
                    "created_at, updated_at) "
                    "VALUES (:id, :user_id, :novel_id, 'Fremd', 0, 'fremd worte', now(), now())"
                ),
                {"id": uuid4(), "user_id": OTHER_USER, "novel_id": UUID(novel_id)},
            )
            await session.commit()

        row = await _novel_row(client, novel_id)
        assert row["chapter_count"] == 1
        assert row["word_count"] == 1
