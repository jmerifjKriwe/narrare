"""The review contract: accept and discard are exactly-once, one transaction.

Accept creates the entity and consumes the suggestion together; discard
consumes without creating. A second review of any kind is a 409, and the
exclusivity holds under two concurrent accepts, not just two sequential ones.
"""

import asyncio
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response

from app.api.main import app
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Entity
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = uuid4()

CHAPTER_BODY = (
    "Mira betrat das alte Haus am See. Der Leuchtturm schwieg, und Nebel zog über das Dorf."
)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _pending_suggestion(client: AsyncClient) -> dict[str, object]:
    """A novel whose chapter went through extraction: its first pending suggestion."""
    novel = await client.post("/api/writing/novels", json={"title": "Der Nebel"})
    novel_id = novel.json()["id"]
    chapter = await client.post(
        f"/api/writing/novels/{novel_id}/chapters", json={"title": "Ankunft"}
    )
    await client.put(f"/api/writing/chapters/{chapter.json()['id']}", json={"body": CHAPTER_BODY})
    await client.post(
        f"/api/knowledge/extraction/{novel_id}", json={"chapter_id": chapter.json()["id"]}
    )

    from app.capabilities.knowledge.jobs import handlers
    from app.kernel.jobs.worker import Worker

    assert await Worker(Session, handlers).run_once() is True

    listed = await client.get(f"/api/knowledge/novels/{novel_id}/suggestions")
    suggestions = listed.json()
    assert len(suggestions) == 3
    return suggestions[0]


async def test_accept_creates_exactly_one_entity_and_consumes_the_suggestion() -> None:
    async with _client() as client:
        suggestion = await _pending_suggestion(client)
        novel_id = suggestion["novel_id"]

        accepted = await client.post(f"/api/knowledge/suggestions/{suggestion['id']}/accept")
        assert accepted.status_code == 200
        entity = accepted.json()
        assert entity["name"] == suggestion["name"]
        assert entity["type"] == suggestion["type"]
        assert entity["novel_id"] == novel_id

        entities = (await client.get(f"/api/knowledge/novels/{novel_id}/entities")).json()
        assert len(entities) == 1  # exactly one entity, not one per attempt

        still_pending = (
            await client.get(f"/api/knowledge/novels/{novel_id}/suggestions?status=pending")
        ).json()
        assert len(still_pending) == 2  # the unreviewed two remain, the accepted one is gone
        assert suggestion["id"] not in [row["id"] for row in still_pending]
        consumed = (
            await client.get(f"/api/knowledge/novels/{novel_id}/suggestions?status=accepted")
        ).json()
        assert [row["id"] for row in consumed] == [suggestion["id"]]

        second = await client.post(f"/api/knowledge/suggestions/{suggestion['id']}/accept")
        assert second.status_code == 409

        entities_after = (await client.get(f"/api/knowledge/novels/{novel_id}/entities")).json()
        assert len(entities_after) == 1  # the refusal created nothing


async def test_an_accept_births_the_entity_with_empty_labels_and_a_vector() -> None:
    """Birth per D5: the description becomes the body, the labels start empty,
    and the search text and the vector are computed in the same transaction."""
    async with _client() as client:
        suggestion = await _pending_suggestion(client)
        novel_id = suggestion["novel_id"]

        accepted = await client.post(f"/api/knowledge/suggestions/{suggestion['id']}/accept")
        assert accepted.status_code == 200
        entity = accepted.json()
        assert entity["type"] == suggestion["type"]
        assert entity["content"] == (suggestion["description"] or "")
        assert entity["aliases"] == []
        assert entity["tags"] == []

        # the entity is findable by its own name through the trigram search:
        # search_text rode the birth
        found = await client.get(
            f"/api/knowledge/novels/{novel_id}/entities",
            params={"q": str(suggestion["name"])},
        )
        assert [row["id"] for row in found.json()] == [entity["id"]]

    async with Session() as session:
        row = await session.get(Entity, UUID(str(entity["id"])))
    assert row is not None
    assert row.embedding is not None  # the vector rode the birth
    assert row.search_text == row.name


async def test_an_accept_at_another_embedding_width_is_refused_and_writes_nothing() -> None:
    """Birth embeds in the transaction (D5): a corpus embedded at another
    width refuses the accept like an upload, and the refusal writes nothing —
    no entity born, no suggestion consumed."""
    async with _client() as client:
        suggestion = await _pending_suggestion(client)
        novel_id = suggestion["novel_id"]

    async with Session() as session:
        # the corpus's first set vector fixes its width at 3; the configured
        # fake embeds at 384, so the birth's vector cannot join
        session.add(
            Entity(
                user_id=LOCAL_USER_ID,
                novel_id=UUID(str(novel_id)),
                name="Alt",
                type="generic",
                search_text="Alt",
                embedding=[0.1, 0.2, 0.3],
            )
        )
        await session.commit()

    async with _client() as client:
        refused = await client.post(f"/api/knowledge/suggestions/{suggestion['id']}/accept")
        assert refused.status_code == 409
        # a dict, not a sentence: the UI localizes this error and needs a code
        assert refused.json()["detail"]["code"] == "embedding-mismatch"

        entities = (await client.get(f"/api/knowledge/novels/{novel_id}/entities")).json()
        assert [row["name"] for row in entities] == ["Alt"]  # the birth never landed
        still_pending = (
            await client.get(f"/api/knowledge/novels/{novel_id}/suggestions?status=pending")
        ).json()
        # unconsumed: the reviewed row is still among the pending three
        assert suggestion["id"] in [row["id"] for row in still_pending]


async def test_discard_consumes_without_creating() -> None:
    async with _client() as client:
        suggestion = await _pending_suggestion(client)
        novel_id = suggestion["novel_id"]

        discarded = await client.post(f"/api/knowledge/suggestions/{suggestion['id']}/discard")
        assert discarded.status_code == 200
        assert discarded.json()["status"] == "discarded"

        entities = (await client.get(f"/api/knowledge/novels/{novel_id}/entities")).json()
        assert entities == []

        second = await client.post(f"/api/knowledge/suggestions/{suggestion['id']}/discard")
        assert second.status_code == 409
        late_accept = await client.post(f"/api/knowledge/suggestions/{suggestion['id']}/accept")
        assert late_accept.status_code == 409

        entities_after = (await client.get(f"/api/knowledge/novels/{novel_id}/entities")).json()
        assert entities_after == []  # a discarded suggestion creates nothing, ever


async def test_two_concurrent_accepts_leave_exactly_one_entity() -> None:
    async with _client() as client:
        suggestion = await _pending_suggestion(client)
        novel_id = suggestion["novel_id"]
        accept_path = f"/api/knowledge/suggestions/{suggestion['id']}/accept"

    async def _accept() -> Response:
        async with _client() as own:
            return await own.post(accept_path)

    # Two requests in flight at once: the row-level transition must serialize
    # them — one winner, one 409, one entity row.
    first, second = await asyncio.gather(_accept(), _accept())
    assert sorted([first.status_code, second.status_code]) == [200, 409]

    async with _client() as client:
        entities = (await client.get(f"/api/knowledge/novels/{novel_id}/entities")).json()
        accepted = (
            await client.get(f"/api/knowledge/novels/{novel_id}/suggestions?status=accepted")
        ).json()
    assert len(entities) == 1
    assert len(accepted) == 1


async def test_another_users_suggestion_cannot_be_reviewed() -> None:
    from app.kernel.contracts.models import Chapter, EntitySuggestion, Novel

    async with _client() as client:
        await _pending_suggestion(client)  # my rows exist too: scoping must not blur

    await seed_user(OTHER_USER)
    async with Session() as session:
        novel = Novel(user_id=OTHER_USER, title="Fremder Roman")
        session.add(novel)
        await session.flush()
        chapter = Chapter(user_id=OTHER_USER, novel_id=novel.id, title="Ankunft", position=0)
        session.add(chapter)
        await session.flush()
        theirs = EntitySuggestion(
            user_id=OTHER_USER,
            novel_id=novel.id,
            chapter_id=chapter.id,
            name="Mira",
            type="character",
            status="pending",
        )
        session.add(theirs)
        await session.commit()

    async with _client() as client:
        for path in (
            f"/api/knowledge/suggestions/{theirs.id}/accept",
            f"/api/knowledge/suggestions/{theirs.id}/discard",
        ):
            response = await client.post(path)
            assert response.status_code == 404

        unknown = await client.post(
            "/api/knowledge/suggestions/00000000-0000-0000-0000-0000000000ff/accept"
        )
        assert unknown.status_code == 404

    async with Session() as session:
        row = await session.get(EntitySuggestion, theirs.id)
    assert row is not None
    assert row.status == "pending"  # the refusals consumed nothing
