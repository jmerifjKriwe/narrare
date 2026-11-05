"""Managing a novel: PATCH changes only the fields the body carries; DELETE
takes the whole book — its chapters, entities, relations, suggestions and
findings — while the library's documents survive. The read carries the
export's trace, set by an export and by nothing else."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import (
    ConsistencyFinding,
    Document,
    Entity,
    EntityRelation,
    EntitySuggestion,
)
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


async def _novel_id(client: AsyncClient, **metadata: str) -> str:
    """A created novel's id — titled "Der Nebel", plus the metadata passed."""
    created = await client.post("/api/writing/novels", json={"title": "Der Nebel", **metadata})
    assert created.status_code == 201
    return created.json()["id"]


async def test_patch_changes_only_the_fields_sent() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client, genre="Mystery", blurb="A fog rolls in.")
        patched = await client.patch(
            f"/api/writing/novels/{novel_id}", json={"author": "J. Autorin"}
        )
        assert patched.status_code == 200
        body = patched.json()
        assert body["author"] == "J. Autorin"
        # the fields the body does not carry are untouched
        assert body["title"] == "Der Nebel"
        assert body["genre"] == "Mystery"
        assert body["blurb"] == "A fog rolls in."
        assert body["language"] is None


async def test_patch_answers_the_real_chapter_and_word_counts() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/writing/novels", json={"title": "Der Nebel"})
        novel_id = created.json()["id"]
        chapter = await client.post(
            f"/api/writing/novels/{novel_id}/chapters", json={"title": "Ankunft"}
        )
        assert chapter.status_code == 201
        written = await client.put(
            f"/api/writing/chapters/{chapter.json()['id']}",
            json={"body": "Der Nebel legt sich über die Bucht."},
        )
        assert written.status_code == 200
        patched = await client.patch(
            f"/api/writing/novels/{novel_id}", json={"author": "J. Autorin"}
        )
        assert patched.status_code == 200
        # the patch answers the novel's real length, not the schema's zeros
        assert patched.json()["chapter_count"] == 1
        assert patched.json()["word_count"] == 7


async def test_patch_trims_the_title() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        patched = await client.patch(
            f"/api/writing/novels/{novel_id}", json={"title": "  Die Stadt  "}
        )
        assert patched.status_code == 200
        assert patched.json()["title"] == "Die Stadt"


async def test_patch_refuses_an_empty_title() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        for title in ("", "   "):
            refused = await client.patch(f"/api/writing/novels/{novel_id}", json={"title": title})
            assert refused.status_code == 422, title
            assert refused.json()["detail"] == "invalid title"
        # the refusals wrote nothing
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.json()["title"] == "Der Nebel"


async def test_patch_refuses_a_bad_language_code() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        for code in ("deutsch", "d", "de-", "en_GB"):
            refused = await client.patch(f"/api/writing/novels/{novel_id}", json={"language": code})
            assert refused.status_code == 422, code
            assert refused.json()["detail"] == "invalid language"
        # the refusals wrote nothing
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.json()["language"] is None


async def test_patch_refuses_an_over_long_language() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        # "de-" + 14 letters matches the pattern and is wider than the column
        refused = await client.patch(
            f"/api/writing/novels/{novel_id}", json={"language": f"de-{'x' * 14}"}
        )
        assert refused.status_code == 422
        assert refused.json()["detail"] == "invalid language"


async def test_patch_clears_the_language_with_null_and_with_empty_string() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        chose = await client.patch(f"/api/writing/novels/{novel_id}", json={"language": "de"})
        assert chose.status_code == 200
        assert chose.json()["language"] == "de"

        # null is a value, not an absence: the language clears
        nulled = await client.patch(f"/api/writing/novels/{novel_id}", json={"language": None})
        assert nulled.status_code == 200
        assert nulled.json()["language"] is None

        chose_again = await client.patch(f"/api/writing/novels/{novel_id}", json={"language": "en"})
        assert chose_again.status_code == 200
        assert chose_again.json()["language"] == "en"

        # the empty string clears too — same honest no-answer
        emptied = await client.patch(f"/api/writing/novels/{novel_id}", json={"language": ""})
        assert emptied.status_code == 200
        assert emptied.json()["language"] is None


async def test_patch_accepts_bcp47_like_codes() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        for code in ("de", "en-GB"):
            patched = await client.patch(f"/api/writing/novels/{novel_id}", json={"language": code})
            assert patched.status_code == 200, code
            assert patched.json()["language"] == code


async def test_patch_folds_a_shouted_language_code() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        patched = await client.patch(f"/api/writing/novels/{novel_id}", json={"language": "DE"})
        assert patched.status_code == 200
        assert patched.json()["language"] == "de"


async def test_patch_refuses_a_genre_over_80() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        refused = await client.patch(f"/api/writing/novels/{novel_id}", json={"genre": "x" * 81})
        assert refused.status_code == 422
        assert refused.json()["detail"] == "invalid genre"
        # the refusal wrote nothing
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.json()["genre"] is None


async def test_patch_refuses_an_over_long_author() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        refused = await client.patch(f"/api/writing/novels/{novel_id}", json={"author": "x" * 201})
        assert refused.status_code == 422
        assert refused.json()["detail"] == "invalid author"
        # the refusal wrote nothing
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.json()["author"] is None


async def test_patch_clears_an_empty_genre() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client, genre="Mystery")

        # an empty genre is no genre, not an empty string stored
        emptied = await client.patch(f"/api/writing/novels/{novel_id}", json={"genre": "  "})
        assert emptied.status_code == 200
        assert emptied.json()["genre"] is None

        # a carried null keeps clearing too
        chose = await client.patch(f"/api/writing/novels/{novel_id}", json={"genre": "Mystery"})
        assert chose.status_code == 200
        assert chose.json()["genre"] == "Mystery"
        nulled = await client.patch(f"/api/writing/novels/{novel_id}", json={"genre": None})
        assert nulled.status_code == 200
        assert nulled.json()["genre"] is None


async def test_patch_bumps_updated_at() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        before = datetime.fromisoformat(fetched.json()["updated_at"])
        patched = await client.patch(
            f"/api/writing/novels/{novel_id}", json={"author": "J. Autorin"}
        )
        assert patched.status_code == 200
        after = datetime.fromisoformat(patched.json()["updated_at"])
        assert after > before


async def test_patch_answers_404_for_a_foreign_novel() -> None:
    await seed_user(OTHER_USER)
    foreign_id = uuid4()
    async with Session() as session:
        await session.execute(
            text(
                "INSERT INTO novels (id, user_id, title, created_at, updated_at) "
                "VALUES (:id, :user_id, :title, now(), now())"
            ),
            {"id": foreign_id, "user_id": OTHER_USER, "title": "Fremd"},
        )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        patched = await client.patch(
            f"/api/writing/novels/{foreign_id}", json={"title": "Umgetauft"}
        )
        assert patched.status_code == 404
        assert patched.json()["detail"] == "novel not found"


async def test_novel_read_carries_the_timestamp() -> None:
    """The read carries the export's trace: None until a first export sets it."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        fresh = await client.get(f"/api/writing/novels/{novel_id}")
        assert fresh.json()["last_exported_at"] is None

        exported = await client.post(f"/api/writing/novels/{novel_id}/export", json={"mode": "zip"})
        assert exported.status_code == 200

        traced = await client.get(f"/api/writing/novels/{novel_id}")
        stamp = datetime.fromisoformat(traced.json()["last_exported_at"])
        assert stamp.tzinfo is not None


async def test_delete_novel_answers_204_and_is_gone() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)
        deleted = await client.delete(f"/api/writing/novels/{novel_id}")
        assert deleted.status_code == 204
        # gone means gone: the shelf no longer knows the book
        fetched = await client.get(f"/api/writing/novels/{novel_id}")
        assert fetched.status_code == 404


async def test_delete_novel_cascades_chapters_entities_relations_suggestions_findings() -> None:
    """The database's cascades, not the route's promises: after the delete,
    every novel-scoped row for the id is gone — chapters, entities and their
    relations, pending suggestions, findings."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = UUID(await _novel_id(client))
        chapter = await client.post(
            f"/api/writing/novels/{novel_id}/chapters", json={"title": "Ankunft"}
        )
        assert chapter.status_code == 201

    # The novel's canon through the kernel models (never another capability):
    # two entities, their edge, one pending suggestion and one finding.
    async with Session() as session:
        mira = Entity(user_id=LOCAL_USER_ID, novel_id=novel_id, name="Mira Vale", type="character")
        tower = Entity(user_id=LOCAL_USER_ID, novel_id=novel_id, name="Leuchtturm", type="location")
        session.add_all([mira, tower])
        await session.flush()
        session.add(
            EntityRelation(
                user_id=LOCAL_USER_ID,
                from_entity_id=mira.id,
                to_entity_id=tower.id,
                relation_type="bewacht",
            )
        )
        session.add(
            EntitySuggestion(
                user_id=LOCAL_USER_ID,
                novel_id=novel_id,
                chapter_id=UUID(chapter.json()["id"]),
                name="Robbe",
                type="object",
                status="pending",
            )
        )
        session.add(
            ConsistencyFinding(
                user_id=LOCAL_USER_ID,
                novel_id=novel_id,
                summary="Miras Augen sind blau und grün",
                status="pending",
            )
        )
        await session.commit()
        ends = (mira.id, tower.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        deleted = await client.delete(f"/api/writing/novels/{novel_id}")
        assert deleted.status_code == 204

    async with Session() as session:
        # one row of scalar subqueries: the answer for every table at once
        (chapters, entities, suggestions, findings, edges) = (
            await session.execute(
                text(
                    "SELECT"
                    " (SELECT count(*) FROM chapters WHERE novel_id = :novel_id),"
                    " (SELECT count(*) FROM entities WHERE novel_id = :novel_id),"
                    " (SELECT count(*) FROM entity_suggestions WHERE novel_id = :novel_id),"
                    " (SELECT count(*) FROM consistency_findings WHERE novel_id = :novel_id),"
                    " (SELECT count(*) FROM entity_relations"
                    "   WHERE from_entity_id IN (:first, :second)"
                    "      OR to_entity_id IN (:first, :second))"
                ),
                {"novel_id": novel_id, "first": ends[0], "second": ends[1]},
            )
        ).one()
        assert chapters == 0, "chapters"
        assert entities == 0, "entities"
        assert suggestions == 0, "entity_suggestions"
        assert findings == 0, "consistency_findings"
        # relations carry no novel column; their ends were this novel's entities
        assert edges == 0, "entity_relations"


async def test_delete_novel_leaves_documents_alone() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        novel_id = await _novel_id(client)

    # a document is the library's, not the novel's — it has no novel column
    async with Session() as session:
        session.add(Document(user_id=LOCAL_USER_ID, title="Recherche", embedding_width=8))
        await session.commit()
        before = await session.scalar(text("SELECT count(*) FROM documents"))
        assert before == 1

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        deleted = await client.delete(f"/api/writing/novels/{novel_id}")
        assert deleted.status_code == 204

    async with Session() as session:
        after = await session.scalar(text("SELECT count(*) FROM documents"))
        assert after == 1


async def test_delete_novel_answers_404_for_a_foreign_novel() -> None:
    await seed_user(OTHER_USER)
    foreign_id = uuid4()
    async with Session() as session:
        await session.execute(
            text(
                "INSERT INTO novels (id, user_id, title, created_at, updated_at) "
                "VALUES (:id, :user_id, :title, now(), now())"
            ),
            {"id": foreign_id, "user_id": OTHER_USER, "title": "Fremd"},
        )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        deleted = await client.delete(f"/api/writing/novels/{foreign_id}")
        assert deleted.status_code == 404
        assert deleted.json()["detail"] == "novel not found"
    # the refusal deleted nothing: the foreign book keeps its rows
    async with Session() as session:
        kept = await session.scalar(
            text("SELECT count(*) FROM novels WHERE id = :id"), {"id": foreign_id}
        )
        assert kept == 1
