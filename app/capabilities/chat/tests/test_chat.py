"""Chat over the knowledge base: real database, catalog's fake provider."""

import json
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.capabilities.chat.service import ChatService
from app.capabilities.knowledge.service import KnowledgeService
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.db.session import Session
from app.kernel.embeddings import FakeEmbeddingProvider

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")
PASSAGE = "Der Leuchtturm am Horizont war seit Jahren dunkel."


def _frames(body: str) -> list[dict[str, Any]]:
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


async def _upload(client: AsyncClient, text: str, title: str) -> None:
    response = await client.post(
        "/api/knowledge/documents",
        files={"file": ("notizen.txt", text.encode("utf-8"), "text/plain")},
        data={"title": title},
    )
    assert response.status_code == 201


async def test_answer_comes_back_with_the_passage_as_source() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _upload(client, PASSAGE, "Notizen")

        response = await client.post("/api/chat/ask", json={"question": "Wo war der Leuchtturm?"})
        assert response.status_code == 200

        frames = _frames(response.text)
        assert frames[0]["sources"][0]["document_title"] == "Notizen"
        assert PASSAGE in frames[0]["sources"][0]["text"]

        answer = "".join(str(frame["delta"]) for frame in frames if "delta" in frame)
        assert PASSAGE in answer


async def test_prompt_carries_the_question_and_the_passage() -> None:
    async with Session() as session:
        await KnowledgeService(session, LOCAL_USER_ID, FakeEmbeddingProvider()).ingest(
            "Notizen", PASSAGE
        )

    async with Session() as session:
        prompt, passages = await ChatService(
            session, LOCAL_USER_ID, FakeEmbeddingProvider()
        ).prepare("Wo war der Leuchtturm?", 5)

    assert "Wo war der Leuchtturm?" in prompt
    assert PASSAGE in prompt
    assert [passage.text for passage in passages] == [PASSAGE]


async def test_another_users_passage_is_not_a_source() -> None:
    async with Session() as session:
        await KnowledgeService(session, OTHER_USER, FakeEmbeddingProvider()).ingest(
            "Fremd", PASSAGE
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat/ask", json={"question": "Wo war der Leuchtturm?"})
        assert response.status_code == 200
        assert _frames(response.text)[0]["sources"] == []


async def test_answer_without_sources_does_not_invent_a_citation() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat/ask", json={"question": "Wo war der Leuchtturm?"})
        assert response.status_code == 200
        frames = _frames(response.text)
        assert frames[0]["sources"] == []
        assert any("delta" in frame for frame in frames)


async def test_an_empty_question_is_rejected() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat/ask", json={"question": ""})
        assert response.status_code == 422
