"""Derived counts: the shelf says how long a novel is, without opening it.

The rule is the wave's single one: a word is a whitespace-separated
token of the body after trimming, and a body that trims empty counts 0.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app

pytestmark = pytest.mark.timeout(60)


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
