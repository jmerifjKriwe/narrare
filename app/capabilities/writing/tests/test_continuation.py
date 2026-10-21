"""Continuation: the stream is SSE, the chunks add up, and the door stays shut."""

import json
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.capabilities.writing.prompts import continuity_prompt
from app.kernel.db.session import Session
from app.kernel.llm import FakeProvider

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _deltas(body: str) -> list[str]:
    deltas: list[str] = []
    for line in body.splitlines():
        if line.startswith("data: "):
            payload: dict[str, str] = json.loads(line[len("data: ") :])
            if "delta" in payload:
                deltas.append(payload["delta"])
    return deltas


async def _create_chapter(client: AsyncClient, body: str = "") -> str:
    novel = await client.post("/api/writing/novels", json={"title": "Der Nebel"})
    chapter = await client.post(
        f"/api/writing/novels/{novel.json()['id']}/chapters", json={"title": "Ankunft"}
    )
    chapter_id = chapter.json()["id"]
    if body:
        await client.put(f"/api/writing/chapters/{chapter_id}", json={"body": body})
    return chapter_id


async def test_the_continuation_streams_the_provider_chunks() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client)
        response = await client.post(f"/api/writing/chapters/{chapter_id}/continue")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    deltas = _deltas(response.text)
    # More than one event: the endpoint streams, it does not buffer one blob.
    assert len(deltas) > 1
    assert "".join(deltas) == "".join(FakeProvider.CHUNKS)
    assert "event: done" in response.text


async def test_another_users_chapter_cannot_be_continued() -> None:
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
        response = await client.post(f"/api/writing/chapters/{chapter_id}/continue")
        assert response.status_code == 404


def test_the_prompt_carries_the_chapter_tail() -> None:
    prompt = continuity_prompt(
        novel_title="Der Nebel", chapter_title="Ankunft", body="Der Nebel kam von See."
    )
    assert "Der Nebel" in prompt
    assert "Ankunft" in prompt
    assert "Der Nebel kam von See." in prompt
