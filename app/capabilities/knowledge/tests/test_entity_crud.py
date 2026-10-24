"""Manual entity CRUD: rename, delete, merge — the correction contract.

Entities are born through review, but a typo must not live forever. The
three corrections are endpoint contracts first: a PATCH changes only the
fields its body carries, a delete removes exactly the row, a merge keeps
the target and deletes the source. Entity rows have no referents — an
accepted suggestion is a self-contained copy, never a reference — so a
delete needs no cascade and the review history outlives the entity. The
scoping answer is the product's one answer everywhere: another user's row
is a 404, indistinguishable from no row at all.
"""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Chapter, Entity, EntitySuggestion, Novel
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = uuid4()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _entities(*rows: tuple[str, str, str | None]) -> list[Entity]:
    """Entities in one novel, seeded straight through the session.

    The CRUD contract is about rows that exist, not about how they were
    born — review's own tests pin the birth. A None description stays None:
    clearing is a value this contract must carry, so the seeded rows cover
    both of its states.
    """
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title="Die Korrektur")
        session.add(novel)
        await session.flush()
        created = [
            Entity(
                user_id=LOCAL_USER_ID,
                novel_id=novel.id,
                name=name,
                kind=kind,
                description=description,
            )
            for name, kind, description in rows
        ]
        session.add_all(created)
        await session.commit()
        return created


async def _accepted_pair() -> tuple[Entity, EntitySuggestion]:
    """An entity beside the accepted suggestion that filed it: the row pair
    the no-referents contract is about."""
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title="Die Korrektur")
        session.add(novel)
        await session.flush()
        chapter = Chapter(user_id=LOCAL_USER_ID, novel_id=novel.id, title="Ankunft", position=0)
        session.add(chapter)
        await session.flush()
        suggestion = EntitySuggestion(
            user_id=LOCAL_USER_ID,
            novel_id=novel.id,
            chapter_id=chapter.id,
            name="Mira",
            kind="character",
            description="Mira appears in the chapter.",
            status="accepted",
        )
        session.add(suggestion)
        entity = Entity(
            user_id=LOCAL_USER_ID,
            novel_id=novel.id,
            name="Mira",
            kind="character",
            description="Mira appears in the chapter.",
        )
        session.add(entity)
        await session.commit()
        return entity, suggestion


async def test_a_patch_changes_only_the_fields_the_body_carries() -> None:
    [mira] = await _entities(("Mira", "character", "Mira appears in the chapter."))
    async with _client() as client:
        renamed = await client.patch(f"/api/knowledge/entities/{mira.id}", json={"name": "Miralam"})
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Miralam"
        # the fields the body does not carry are untouched
        assert renamed.json()["kind"] == "character"
        assert renamed.json()["description"] == "Mira appears in the chapter."

        rekinded = await client.patch(f"/api/knowledge/entities/{mira.id}", json={"kind": "place"})
        assert rekinded.status_code == 200
        assert rekinded.json()["kind"] == "place"
        assert rekinded.json()["name"] == "Miralam"

        # null is a value, not an absence: the description clears
        cleared = await client.patch(
            f"/api/knowledge/entities/{mira.id}", json={"description": None}
        )
        assert cleared.status_code == 200
        assert cleared.json()["description"] is None

        # the empty patch is a round trip, not an error
        untouched = await client.patch(f"/api/knowledge/entities/{mira.id}", json={})
        assert untouched.status_code == 200
        assert untouched.json()["name"] == "Miralam"


async def test_a_patch_is_validated_like_the_parse_contract() -> None:
    [mira] = await _entities(("Mira", "character", None))
    async with _client() as client:
        for name in ("", "   ", "x" * 201):
            refused = await client.patch(f"/api/knowledge/entities/{mira.id}", json={"name": name})
            assert refused.status_code == 422, name
        unknown_kind = await client.patch(
            f"/api/knowledge/entities/{mira.id}", json={"kind": "idea"}
        )
        assert unknown_kind.status_code == 422
        not_a_string = await client.patch(
            f"/api/knowledge/entities/{mira.id}", json={"description": 5}
        )
        assert not_a_string.status_code == 422
        # no refusal wrote anything
        listed = await client.get(f"/api/knowledge/novels/{mira.novel_id}/entities")
        assert [(row["name"], row["kind"], row["description"]) for row in listed.json()] == [
            ("Mira", "character", None)
        ]


async def test_a_delete_is_a_row_delete_and_the_review_history_survives() -> None:
    mira, suggestion = await _accepted_pair()
    async with _client() as client:
        gone = await client.delete(f"/api/knowledge/entities/{mira.id}")
        assert gone.status_code == 204

        listed = await client.get(f"/api/knowledge/novels/{mira.novel_id}/entities")
        assert listed.json() == []

        # the suggestion is a self-contained copy: it outlives the entity
        # with its snapshot intact — the review history is not the entity's
        # shadow, so deleting the entity deletes exactly one row.
        accepted = await client.get(
            f"/api/knowledge/novels/{mira.novel_id}/suggestions", params={"status": "accepted"}
        )
        assert accepted.status_code == 200
        rows = accepted.json()
        assert [row["id"] for row in rows] == [str(suggestion.id)]
        assert rows[0]["name"] == "Mira"
        assert rows[0]["kind"] == "character"
        assert rows[0]["description"] == "Mira appears in the chapter."

        # the row is gone gone: a second delete meets the same absence
        again = await client.delete(f"/api/knowledge/entities/{mira.id}")
        assert again.status_code == 404


async def test_a_merge_keeps_the_target_and_deletes_the_source() -> None:
    mira, haus = await _entities(("Mira", "character", None), ("Haus", "place", "Das alte Haus."))
    async with _client() as client:
        merged = await client.post(
            f"/api/knowledge/entities/{mira.id}/merge", json={"target_id": str(haus.id)}
        )
        assert merged.status_code == 200
        assert merged.json()["id"] == str(haus.id)
        assert merged.json()["name"] == "Haus"

        listed = await client.get(f"/api/knowledge/novels/{mira.novel_id}/entities")
        assert [row["name"] for row in listed.json()] == ["Haus"]


async def test_an_entity_cannot_merge_into_itself() -> None:
    mira, _haus = await _entities(("Mira", "character", None), ("Haus", "place", None))
    async with _client() as client:
        refused = await client.post(
            f"/api/knowledge/entities/{mira.id}/merge", json={"target_id": str(mira.id)}
        )
        assert refused.status_code == 422
        # the refusal deleted nothing
        listed = await client.get(f"/api/knowledge/novels/{mira.novel_id}/entities")
        assert len(listed.json()) == 2


async def test_another_users_entity_cannot_be_corrected() -> None:
    [mira] = await _entities(("Mira", "character", None))
    await seed_user(OTHER_USER)
    async with Session() as session:
        novel = Novel(user_id=OTHER_USER, title="Fremder Roman")
        session.add(novel)
        await session.flush()
        theirs = Entity(user_id=OTHER_USER, novel_id=novel.id, name="Fremde Mira", kind="character")
        session.add(theirs)
        await session.commit()

    async with _client() as client:
        patched = await client.patch(
            f"/api/knowledge/entities/{theirs.id}", json={"name": "Übernommen"}
        )
        assert patched.status_code == 404
        deleted = await client.delete(f"/api/knowledge/entities/{theirs.id}")
        assert deleted.status_code == 404
        merged = await client.post(
            f"/api/knowledge/entities/{theirs.id}/merge", json={"target_id": str(mira.id)}
        )
        assert merged.status_code == 404
        # a merge onto another user's row is the same refusal, from the
        # other side: neither end of the pair may cross the scoping line
        cross = await client.post(
            f"/api/knowledge/entities/{mira.id}/merge", json={"target_id": str(theirs.id)}
        )
        assert cross.status_code == 404

        unknown = "00000000-0000-0000-0000-0000000000ff"
        assert (
            await client.patch(f"/api/knowledge/entities/{unknown}", json={"name": "Niemand"})
        ).status_code == 404
        assert (await client.delete(f"/api/knowledge/entities/{unknown}")).status_code == 404
        assert (
            await client.post(
                f"/api/knowledge/entities/{unknown}/merge", json={"target_id": str(mira.id)}
            )
        ).status_code == 404

    async with Session() as session:
        row = await session.get(Entity, theirs.id)
    assert row is not None
    assert row.name == "Fremde Mira"  # the refusals wrote nothing

    # and my own row survived every refusal untouched
    async with _client() as client:
        listed = await client.get(f"/api/knowledge/novels/{mira.novel_id}/entities")
        assert [row["name"] for row in listed.json()] == ["Mira"]
