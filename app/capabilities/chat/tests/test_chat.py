"""Chat over the knowledge base: real database, catalog's fake provider."""

import json
from collections.abc import Sequence  # noqa: TC003
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.capabilities.chat.service import ChatService
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Chunk, Document
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.embeddings import FakeEmbeddingProvider, get_embedding_provider

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")
PASSAGE = "Der Leuchtturm am Horizont war seit Jahren dunkel."


def _frames(body: str) -> list[dict[str, Any]]:
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


async def _seed(user_id: UUID, title: str, passage: str) -> None:
    """One document, one chunk, through the kernel models — chat's own tests do
    not reach into the knowledge capability for their fixtures."""
    await seed_user(user_id)
    [vector] = await FakeEmbeddingProvider().embed([passage])
    async with Session() as session:
        document = Document(user_id=user_id, title=title, embedding_width=len(vector))
        session.add(document)
        await session.flush()
        session.add(
            Chunk(
                user_id=user_id,
                document_id=document.id,
                position=0,
                text=passage,
                embedding=vector,
            )
        )
        await session.commit()


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
    await _seed(LOCAL_USER_ID, "Notizen", PASSAGE)

    async with Session() as session:
        prompt, passages = await ChatService(
            session, LOCAL_USER_ID, FakeEmbeddingProvider()
        ).prepare("Wo war der Leuchtturm?", 5)

    assert "Wo war der Leuchtturm?" in prompt
    assert PASSAGE in prompt
    assert [passage.text for passage in passages] == [PASSAGE]


async def test_another_users_passage_is_not_a_source() -> None:
    await _seed(OTHER_USER, "Fremd", PASSAGE)

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


class _OtherModel:
    """A second model at another width: same contract, other answer."""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.25] * 768 for _ in texts]

    def describe(self) -> str:
        return "test-other-width"

    def configuration_problems(self) -> list[str]:
        return []


async def test_a_model_switch_after_ingest_answers_with_the_refusal() -> None:
    await _seed(LOCAL_USER_ID, "Notizen", PASSAGE)
    app.dependency_overrides[get_embedding_provider] = lambda: _OtherModel()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat/ask", json={"question": "Leuchtturm?"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 409
    assert "re-upload" in str(response.json()["detail"])
