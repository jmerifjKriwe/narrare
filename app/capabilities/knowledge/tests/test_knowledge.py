"""Knowledge base against the real database: ingest, chunk, embed, search."""

from collections.abc import Sequence  # noqa: TC003
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text as sql

from app.api.main import app
from app.capabilities.knowledge.chunking import chunk_text
from app.capabilities.knowledge.repository import EntityRepository
from app.capabilities.knowledge.service import KnowledgeService
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Chapter, Entity, EntitySuggestion, Novel
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.embeddings import FakeEmbeddingProvider, get_embedding_provider
from app.kernel.retrieval import EmbeddingMismatchError

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")

TEXT = "\n\n".join(["Wort " * 100, "Leuchtturm " * 41, "Nebel " * 100])


def _upload(title: str | None, text: str) -> dict[str, str] | None:
    return {"title": title} if title else None


async def _post_document(
    client: AsyncClient, text: str, title: str | None = None
) -> tuple[int, dict[str, object]]:
    response = await client.post(
        "/api/knowledge/documents",
        files={"file": ("notizen.txt", text.encode("utf-8"), "text/plain")},
        data=_upload(title, text),
    )
    return response.status_code, response.json()


async def test_upload_chunks_a_document() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        status, body = await _post_document(client, TEXT, "Notizen")
        assert status == 201
        assert body["title"] == "Notizen"

        listed = await client.get("/api/knowledge/documents")
        assert [document["title"] for document in listed.json()] == ["Notizen"]

    async with Session() as session:
        count = await session.scalar(sql("SELECT count(*) FROM chunks"))
    assert count == 3


async def test_search_returns_the_passage_with_the_term() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _post_document(client, TEXT, "Notizen")

        response = await client.post("/api/knowledge/search", json={"query": "Leuchtturm"})
        assert response.status_code == 200
        hits = response.json()
        assert hits, "search returned nothing"
        assert "Leuchtturm" in hits[0]["text"]
        assert hits[0]["document_title"] == "Notizen"


async def test_another_users_document_is_not_searchable() -> None:
    await seed_user(OTHER_USER)
    async with Session() as session:
        await KnowledgeService(session, OTHER_USER, FakeEmbeddingProvider()).ingest(
            "Fremd", "Leuchtturm am Horizont, ganz allein."
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/knowledge/search", json={"query": "Leuchtturm"})
        assert response.status_code == 200
        assert response.json() == []


async def test_empty_document_is_rejected() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        status, body = await _post_document(client, "   \n\n  ")
        assert status == 422
        assert body["detail"] == "document is empty"


async def test_title_falls_back_to_the_filename() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        status, body = await _post_document(client, "Ein einzelner Absatz.")
        assert status == 201
        assert body["title"] == "notizen.txt"


def test_chunking_keeps_paragraphs_whole() -> None:
    assert chunk_text("eins\n\nzwei", size=8) == ["eins", "zwei"]
    assert chunk_text("eins zwei drei", size=800) == ["eins zwei drei"]
    assert chunk_text("   \n\n ") == []


class _OtherModel:
    """A second model at another width: same contract, other answer."""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.25] * 768 for _ in texts]

    def describe(self) -> str:
        return "test-other-width"

    def configuration_problems(self) -> list[str]:
        return []


async def _ingest(text: str, title: str = "Notizen") -> None:
    async with Session() as session:
        await KnowledgeService(session, LOCAL_USER_ID, FakeEmbeddingProvider()).ingest(title, text)


async def test_a_document_records_its_embedding_width() -> None:
    await _ingest("Ein einzelner Absatz.")
    async with Session() as session:
        widths = await session.scalars(sql("SELECT DISTINCT embedding_width FROM documents"))
    assert list(widths) == [384]


async def test_ingest_refuses_when_the_corpus_was_embedded_at_another_width() -> None:
    # One knowledge base, one model: vectors from two models are not comparable,
    # and a silent mix would corrupt every search result from then on.
    await _ingest("Leuchtturm am Horizont.")

    async with Session() as session:
        service = KnowledgeService(session, LOCAL_USER_ID, _OtherModel())
        with pytest.raises(EmbeddingMismatchError):
            await service.ingest("Neu", "Nebel über dem See.")


async def test_search_refuses_when_the_corpus_was_embedded_at_another_width() -> None:
    await _ingest("Leuchtturm am Horizont.")

    async with Session() as session:
        service = KnowledgeService(session, LOCAL_USER_ID, _OtherModel())
        with pytest.raises(EmbeddingMismatchError):
            await service.search("Leuchtturm", 5)


async def test_the_refusal_is_machine_readable_through_the_api() -> None:
    await _ingest("Leuchtturm am Horizont.")
    app.dependency_overrides[get_embedding_provider] = lambda: _OtherModel()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/knowledge/search", json={"query": "Leuchtturm"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 409
    # The UI localizes this error, so it needs a code, not the English sentence.
    assert response.json()["detail"] == {
        "code": "embedding-mismatch",
        "stored": 384,
        "found": 768,
    }


async def test_reembed_rebuilds_the_corpus_at_the_new_width() -> None:
    """The switch's fix, both halves of the corpus: the documents' chunks
    and the entities' vectors (D5). An entity left at the stale width would
    refuse every accept, update and merge with 409 embedding-mismatch — so
    the re-embed walks the entities too, and the refused birth goes through
    afterwards."""
    await _ingest("Leuchtturm am Horizont.", "Erstes")
    await _ingest("Nebel über dem See.", "Zweites")

    # One entity carrying the old model's vector, plus a pending suggestion
    # whose accept must stay refused until the re-embed has run. Both are
    # written through the session: the switch happens under live rows.
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title="Die Weite")
        session.add(novel)
        await session.flush()
        chapter = Chapter(user_id=LOCAL_USER_ID, novel_id=novel.id, title="Ankunft", position=0)
        session.add(chapter)
        await session.flush()
        repository = EntityRepository(session, LOCAL_USER_ID)
        await repository.create(
            novel.id,
            "Mira",
            "character",
            "",
            [],
            [],
            [0.5] * 384,  # the old model's width
        )
        suggestion = EntitySuggestion(
            user_id=LOCAL_USER_ID,
            novel_id=novel.id,
            chapter_id=chapter.id,
            name="Haus",
            type="location",
            description="Ein Haus am See.",
            relations=[],
            status="pending",
        )
        session.add(suggestion)
        await session.commit()
        novel_id = novel.id
        suggestion_id = suggestion.id

    app.dependency_overrides[get_embedding_provider] = lambda: _OtherModel()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # The stale entity width refuses the birth before anything lands.
            refused = await client.post(f"/api/knowledge/suggestions/{suggestion_id}/accept")
            assert refused.status_code == 409
            assert refused.json()["detail"]["code"] == "embedding-mismatch"

            # And the update: the same corpus guard, the same code.
            listed = await client.get(f"/api/knowledge/novels/{novel_id}/entities")
            mira = listed.json()[0]
            patched = await client.patch(
                f"/api/knowledge/entities/{mira['id']}", json={"content": "Neuer Körper"}
            )
            assert patched.status_code == 409
            assert patched.json()["detail"]["code"] == "embedding-mismatch"

            response = await client.post("/api/knowledge/reembed")
            assert response.status_code == 200
            assert response.json() == {"documents": 2, "chunks": 2, "entities": 1}

            # The corpus answers in the new model's width: search works again.
            searched = await client.post("/api/knowledge/search", json={"query": "Leuchtturm"})

            # The re-embed lifted the refusal: the birth goes through, with
            # a vector at the new width.
            accepted = await client.post(f"/api/knowledge/suggestions/{suggestion_id}/accept")
            assert accepted.status_code == 200
            born_id = accepted.json()["entity"]["id"]
    finally:
        app.dependency_overrides.clear()
    assert searched.status_code == 200
    assert searched.json() != []
    async with Session() as session:
        widths = await session.scalars(sql("SELECT DISTINCT embedding_width FROM documents"))
    assert list(widths) == [768]
    async with Session() as session:
        born = await session.get(Entity, UUID(str(born_id)))
    assert born is not None
    assert born.embedding is not None and len(born.embedding) == 768  # the fresh width


async def test_reembed_on_an_empty_corpus_is_a_no_op() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/knowledge/reembed")
    assert response.status_code == 200
    assert response.json() == {"documents": 0, "chunks": 0, "entities": 0}
