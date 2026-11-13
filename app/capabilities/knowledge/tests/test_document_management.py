"""Document management: the size, the passage count, the delete.

A document knows how large it is (the same UTF-8 byte count the upload
limit already computes), the list states how many passages it carries —
one grouped query, not one per row — and a wrong upload can be removed:
the row goes, the passages cascade, and search no longer finds its text.
"""

from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy import text as sql

from app.api.main import app
from app.capabilities.knowledge.service import KnowledgeService
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.db.session import Session, engine
from app.kernel.db.testsupport import seed_user
from app.kernel.embeddings import FakeEmbeddingProvider

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


async def _ingest(text: str, title: str = "Notizen") -> None:
    async with Session() as session:
        await KnowledgeService(session, LOCAL_USER_ID, FakeEmbeddingProvider()).ingest(title, text)


async def test_ingest_stores_the_utf8_byte_size() -> None:
    # Umlaute and a Gedankenstrich: the byte count must exceed the character
    # count, or the test could not tell an encoding from a len().
    text = "Leuchtturm über dem Nebel — drei Umlaute: äöü."
    await _ingest(text)

    async with Session() as session:
        sizes = await session.scalars(sql("SELECT byte_size FROM documents"))
    assert list(sizes) == [len(text.encode("utf-8"))]


async def test_document_list_counts_chunks_in_one_query() -> None:
    await _ingest(TEXT)  # three passages
    await _ingest("Ein einzelner Absatz.", "Kurz")  # one

    chunk_count_queries: list[str] = []

    def _record(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if "count(*)" in statement and "FROM chunks" in statement:
            chunk_count_queries.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _record)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            listed = await client.get("/api/knowledge/documents")
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _record)

    assert listed.status_code == 200
    by_title = {document["title"]: document for document in listed.json()}
    assert by_title["Notizen"]["chunk_count"] == 3
    assert by_title["Kurz"]["chunk_count"] == 1
    assert by_title["Notizen"]["byte_size"] == len(TEXT.encode("utf-8"))
    # two documents, one grouped count query — not one query per row
    assert len(chunk_count_queries) == 1
    assert "GROUP BY" in chunk_count_queries[0]


async def test_delete_document_cascades_chunks() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        status, body = await _post_document(client, TEXT, "Notizen")
        assert status == 201
        document_id = body["id"]

        deleted = await client.delete(f"/api/knowledge/documents/{document_id}")
        assert deleted.status_code == 204

        # the row is gone gone: a second delete meets the same absence
        again = await client.delete(f"/api/knowledge/documents/{document_id}")
        assert again.status_code == 404

    async with Session() as session:
        documents = await session.scalar(sql("SELECT count(*) FROM documents"))
        chunks = await session.scalar(sql("SELECT count(*) FROM chunks"))
    assert documents == 0
    assert chunks == 0


async def test_delete_document_removes_its_passages_from_search() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        status, body = await _post_document(client, TEXT, "Notizen")
        assert status == 201
        document_id = body["id"]

        # the passages answer search before the delete, or the test proves
        # nothing about the delete
        before = await client.post("/api/knowledge/search", json={"query": "Leuchtturm"})
        assert before.status_code == 200
        hits = before.json()
        assert hits, "the passages must answer search before the delete"
        assert {hit["document_id"] for hit in hits} == {document_id}

        deleted = await client.delete(f"/api/knowledge/documents/{document_id}")
        assert deleted.status_code == 204

        after = await client.post("/api/knowledge/search", json={"query": "Leuchtturm"})
        assert after.status_code == 200
        assert after.json() == []


async def test_delete_document_answers_404_for_a_foreign_document() -> None:
    await seed_user(OTHER_USER)
    async with Session() as session:
        theirs = await KnowledgeService(session, OTHER_USER, FakeEmbeddingProvider()).ingest(
            "Fremd", "Leuchtturm am Horizont, ganz allein."
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        deleted = await client.delete(f"/api/knowledge/documents/{theirs.id}")
        assert deleted.status_code == 404
        assert deleted.json()["detail"] == "document not found"

        # an unknown id is the same refusal — the scoped absence is one answer
        unknown = "00000000-0000-0000-0000-0000000000ff"
        assert (await client.delete(f"/api/knowledge/documents/{unknown}")).status_code == 404

    # the refusal deleted nothing: the foreign row and its passage survive
    async with Session() as session:
        documents = await session.scalar(sql("SELECT count(*) FROM documents"))
        chunks = await session.scalar(sql("SELECT count(*) FROM chunks"))
    assert documents == 1
    assert chunks == 1


async def test_upload_answer_carries_the_real_chunk_count() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        status, body = await _post_document(client, TEXT, "Notizen")
        assert status == 201
        assert body["chunk_count"] == 3
