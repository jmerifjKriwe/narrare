"""Continuation: the stream is SSE, the chunks add up, and the door stays shut."""

import json
from collections.abc import AsyncIterator  # noqa: TC003
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.capabilities.writing.prompts import continuity_prompt
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.llm import FakeProvider, get_provider
from app.kernel.llm.contract import CompletionEvent, CompletionRequest, Delta

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


async def test_the_continuation_records_its_audit_row() -> None:
    async with _client() as client:
        chapter_id = await _create_chapter(client)
        response = await client.post(f"/api/writing/chapters/{chapter_id}/continue")
        assert response.status_code == 200

    async with Session() as session:
        novel_id = await session.scalar(
            text("SELECT novel_id FROM chapters WHERE id = :id"), {"id": UUID(chapter_id)}
        )
        row = (
            await session.execute(
                text(
                    "SELECT task_key, novel_id, status, input_tokens, output_tokens,"
                    " response_text, cost_usd FROM llm_calls"
                )
            )
        ).one()
    assert row.task_key == "writing.continuation"
    assert str(row.novel_id) == str(novel_id)
    assert row.status == "ok"
    assert row.input_tokens > 0
    assert row.output_tokens > 0
    assert row.response_text == "".join(FakeProvider.CHUNKS)
    assert row.cost_usd is None


class _DyingProvider:
    """Streams half an answer, then dies: the mid-stream failure path.

    It sits exactly where the real one does — behind the provider boundary —
    so everything below the boundary runs the real code."""

    def describe(self) -> str:
        return "dying"

    def configuration_problems(self) -> list[str]:
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        yield Delta(text="Halb")
        raise RuntimeError("the provider died")


async def test_a_provider_that_dies_mid_stream_errors_and_audits_the_failure() -> None:
    app.dependency_overrides[get_provider] = lambda: _DyingProvider()
    try:
        async with _client() as client:
            chapter_id = await _create_chapter(client)
            response = await client.post(f"/api/writing/chapters/{chapter_id}/continue")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert _deltas(response.text) == ["Halb"]  # what arrived, arrived
    assert "event: error" in response.text
    assert "event: done" not in response.text

    async with Session() as session:
        row = (await session.execute(text("SELECT status, error, task_key FROM llm_calls"))).one()
    assert row.task_key == "writing.continuation"
    assert row.status == "error"
    assert "the provider died" in row.error


async def test_another_users_chapter_cannot_be_continued() -> None:
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
                "(id, user_id, novel_id, title, position, body, created_at, updated_at) "
                "VALUES (:id, :user_id, :novel_id, :title, 0, '', now(), now())"
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
