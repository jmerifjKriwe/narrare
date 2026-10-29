"""Manual entity CRUD: edit, delete, merge, filter — the correction contract.

Entities are born through review, but a typo must not live forever. The
corrections are endpoint contracts first: a PATCH changes only the fields
its body carries, a delete removes exactly the row, a merge re-points the
source's edges and folds its fields into the survivor instead of dropping
them (D3), and the list filters by type and tag or fuzzy-finds a misspelt
name over the maintained search_text. Every write that moves identity
words recomputes search_text; nothing here reaches the embedding boundary.
The scoping answer is the product's one answer everywhere: another user's
row is a 404, indistinguishable from no row at all.
"""

import asyncio
from collections.abc import Sequence  # noqa: TC003  the exploding provider names it
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.capabilities.knowledge.repository import EntityRepository, RelationRepository
from app.capabilities.knowledge.schemas import EntityUpdate
from app.capabilities.knowledge.service import KnowledgeService
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Chapter, Entity, EntitySuggestion, Novel
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.embeddings import FakeEmbeddingProvider

pytestmark = pytest.mark.timeout(60)

OTHER_USER = uuid4()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _entities(*rows: tuple[str, str, str]) -> list[Entity]:
    """Entities in one novel, seeded through the repository.

    The CRUD contract is about rows that exist, not about how they were
    born — review's own tests pin the birth. Seeding rides the repository
    so the derived column (search_text) is written by the code under
    test, never by hand.
    """
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title="Die Korrektur")
        session.add(novel)
        await session.flush()
        repository = EntityRepository(session, LOCAL_USER_ID)
        created = [
            await repository.create(novel.id, name, type_, content, [], [])
            for name, type_, content in rows
        ]
        await session.commit()
        return created


async def _labeled_entities(
    *rows: tuple[str, str, str, list[str], list[str]],
) -> tuple[Novel, list[Entity]]:
    """One novel whose entities carry aliases and tags, for the filters."""
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title="Die Korrektur")
        session.add(novel)
        await session.flush()
        repository = EntityRepository(session, LOCAL_USER_ID)
        created = [
            await repository.create(novel.id, name, type_, content, aliases, tags)
            for name, type_, content, aliases, tags in rows
        ]
        await session.commit()
        return novel, created


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
            type="character",
            description="Mira appears in the chapter.",
            status="accepted",
        )
        session.add(suggestion)
        entity = Entity(
            user_id=LOCAL_USER_ID,
            novel_id=novel.id,
            name="Mira",
            type="character",
            content="Mira appears in the chapter.",
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
        assert renamed.json()["type"] == "character"
        assert renamed.json()["content"] == "Mira appears in the chapter."

        retyped = await client.patch(
            f"/api/knowledge/entities/{mira.id}", json={"type": "location"}
        )
        assert retyped.status_code == 200
        assert retyped.json()["type"] == "location"
        assert retyped.json()["name"] == "Miralam"

        # null is a value, not an absence: the content clears to the empty body
        cleared = await client.patch(f"/api/knowledge/entities/{mira.id}", json={"content": None})
        assert cleared.status_code == 200
        assert cleared.json()["content"] == ""

        # the empty patch is a round trip, not an error
        untouched = await client.patch(f"/api/knowledge/entities/{mira.id}", json={})
        assert untouched.status_code == 200
        assert untouched.json()["name"] == "Miralam"


async def test_a_patch_is_validated_like_the_parse_contract() -> None:
    [mira] = await _entities(("Mira", "character", ""))
    async with _client() as client:
        for name in ("", "   ", "x" * 201):
            refused = await client.patch(f"/api/knowledge/entities/{mira.id}", json={"name": name})
            assert refused.status_code == 422, name
        unknown_type = await client.patch(
            f"/api/knowledge/entities/{mira.id}", json={"type": "idea"}
        )
        assert unknown_type.status_code == 422
        not_a_string = await client.patch(f"/api/knowledge/entities/{mira.id}", json={"content": 5})
        assert not_a_string.status_code == 422
        not_a_list = await client.patch(
            f"/api/knowledge/entities/{mira.id}", json={"aliases": "Rhea"}
        )
        assert not_a_list.status_code == 422
        # no refusal wrote anything
        listed = await client.get(f"/api/knowledge/novels/{mira.novel_id}/entities")
        assert [(row["name"], row["type"], row["content"]) for row in listed.json()] == [
            ("Mira", "character", "")
        ]


async def test_a_patch_validates_and_dedupes_aliases_and_tags() -> None:
    [mira] = await _entities(("Mira", "character", ""))
    async with _client() as client:
        # duplicates fold case-insensitively, first spelling wins
        dupes = await client.patch(
            f"/api/knowledge/entities/{mira.id}", json={"aliases": ["Rhea", "rhea", "RHEA"]}
        )
        assert dupes.status_code == 200
        assert dupes.json()["aliases"] == ["Rhea"]

        blank = await client.patch(f"/api/knowledge/entities/{mira.id}", json={"tags": ["  "]})
        assert blank.status_code == 422
        overlong = await client.patch(
            f"/api/knowledge/entities/{mira.id}", json={"aliases": ["x" * 201]}
        )
        assert overlong.status_code == 422
        # a refusal writes nothing
        listed = await client.get(f"/api/knowledge/novels/{mira.novel_id}/entities")
        assert listed.json()[0]["tags"] == []


async def test_an_update_recomputes_search_text() -> None:
    [mira] = await _entities(("Mira", "character", ""))
    async with _client() as client:
        patched = await client.patch(
            f"/api/knowledge/entities/{mira.id}",
            json={"aliases": ["Rhea"], "tags": ["protagonist"]},
        )
        assert patched.status_code == 200
        assert patched.json()["aliases"] == ["Rhea"]

        # the just-added alias is searchable: search_text rode the update
        found = await client.get(
            f"/api/knowledge/novels/{mira.novel_id}/entities", params={"q": "Rhea"}
        )
        assert [row["name"] for row in found.json()] == ["Mira"]

    async with Session() as session:
        row = await session.get(Entity, mira.id)
    assert row is not None
    assert row.search_text == "Mira Rhea protagonist"


async def test_the_list_filters_by_type_tag_and_finds_a_misspelt_name() -> None:
    novel, _rows = await _labeled_entities(
        ("Katharina", "character", "Die Erzählerin.", ["Käthe"], ["protagonist", "adlig"]),
        ("Mira", "character", "", [], ["protagonist"]),
        ("Haus", "location", "", [], ["adlig"]),
        ("See", "location", "", [], []),
    )
    async with _client() as client:
        base = f"/api/knowledge/novels/{novel.id}/entities"

        by_type = await client.get(base, params={"type": "character"})
        assert by_type.status_code == 200
        assert [row["name"] for row in by_type.json()] == ["Katharina", "Mira"]

        by_tag = await client.get(base, params={"tag": "adlig"})
        assert [row["name"] for row in by_tag.json()] == ["Katharina", "Haus"]

        # the trigram tier: a realistic misspelling still finds her
        misspelt = await client.get(base, params={"q": "Kathrina"})
        assert [row["name"] for row in misspelt.json()] == ["Katharina"]

        # an empty q is no filter: the list answers unfiltered
        everything = await client.get(base, params={"q": ""})
        assert [row["name"] for row in everything.json()] == ["Katharina", "Mira", "Haus", "See"]


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
        assert rows[0]["type"] == "character"
        assert rows[0]["description"] == "Mira appears in the chapter."

        # the row is gone gone: a second delete meets the same absence
        again = await client.delete(f"/api/knowledge/entities/{mira.id}")
        assert again.status_code == 404


async def test_a_merge_keeps_the_target_and_deletes_the_source() -> None:
    mira, haus = await _entities(("Mira", "character", ""), ("Haus", "location", "Das alte Haus."))
    async with _client() as client:
        merged = await client.post(
            f"/api/knowledge/entities/{mira.id}/merge", json={"target_id": str(haus.id)}
        )
        assert merged.status_code == 200
        assert merged.json()["id"] == str(haus.id)
        assert merged.json()["name"] == "Haus"

        listed = await client.get(f"/api/knowledge/novels/{mira.novel_id}/entities")
        assert [row["name"] for row in listed.json()] == ["Haus"]


async def test_a_merge_repoints_the_edges_and_folds_the_fields() -> None:
    """The D3 fold: nothing the source carried is dropped.

    Edges re-point in both directions and survive as the survivor's —
    including a self-edge — with only exact duplicates dropped; the
    source's name lives on as an alias, aliases and tags union, the body
    folds under a self-labeling heading, and the survivor's type wins.
    """
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title="Die Fusion")
        session.add(novel)
        await session.flush()
        entities = EntityRepository(session, LOCAL_USER_ID)
        relations = RelationRepository(session, LOCAL_USER_ID)
        mira = await entities.create(
            novel.id, "Mira", "character", "Miras Kapitel.", ["Miralam"], ["protagonist"]
        )
        haus = await entities.create(
            novel.id, "Haus", "location", "Das alte Haus.", ["The House"], ["building"]
        )
        see = await entities.create(novel.id, "See", "location", "", [], [])
        await relations.create(mira.id, see.id, "lebt_am", None)  # outgoing, moves
        await relations.create(see.id, mira.id, "erwähnt", "Kapitel 1")  # incoming, moves
        await relations.create(haus.id, haus.id, "kennt", None)  # the survivor's own edge
        await relations.create(mira.id, haus.id, "kennt", None)  # re-points onto it: dropped
        await relations.create(mira.id, mira.id, "spiegelt", None)  # self-edge, survives
        await session.commit()

    async with _client() as client:
        merged = await client.post(
            f"/api/knowledge/entities/{mira.id}/merge", json={"target_id": str(haus.id)}
        )
        assert merged.status_code == 200
        survivor = merged.json()
        assert survivor["id"] == str(haus.id)
        assert survivor["type"] == "location"  # the survivor's type wins
        assert survivor["aliases"] == ["The House", "Miralam", "Mira"]
        assert survivor["tags"] == ["building", "protagonist"]
        assert survivor["content"] == "Das alte Haus.\n\n## Mira\n\nMiras Kapitel."

        listed = await client.get(f"/api/knowledge/novels/{novel.id}/entities")
        # the source is gone; the third entity is nobody's source and stays
        assert [row["name"] for row in listed.json()] == ["Haus", "See"]

        # the edges moved with the fold: both directions, the self-edge
        # alive, only the exact duplicate gone
        edges = (await client.get(f"/api/knowledge/entities/{haus.id}/relations")).json()
        haus_id = str(haus.id)
        see_id = str(see.id)
        assert sorted(
            (row["from_entity_id"], row["to_entity_id"], row["relation_type"]) for row in edges
        ) == sorted(
            [
                (haus_id, haus_id, "kennt"),  # the survivor's own
                (haus_id, haus_id, "spiegelt"),  # the source's self-edge, re-pointed
                (haus_id, see_id, "lebt_am"),  # outgoing, re-pointed
                (see_id, haus_id, "erwähnt"),  # incoming, re-pointed
            ]
        )
        # the folded source is searchable by its own name
        found = await client.get(f"/api/knowledge/novels/{novel.id}/entities", params={"q": "Mira"})
        assert [row["name"] for row in found.json()] == ["Haus"]

    async with Session() as session:
        row = await session.get(Entity, haus.id)
    assert row is not None
    assert row.search_text == "Haus The House Miralam Mira building protagonist"


async def test_a_merge_of_same_named_rows_keeps_the_name_once() -> None:
    """The survivor's own name seeds the alias dedupe: two rows named Mira
    fold without aliasing the name to itself — no alias is added, and the
    search text carries the name once."""
    source, target = await _entities(
        ("Mira", "character", "Die Quelle."), ("Mira", "character", "Die Erzählerin.")
    )
    async with _client() as client:
        merged = await client.post(
            f"/api/knowledge/entities/{source.id}/merge", json={"target_id": str(target.id)}
        )
        assert merged.status_code == 200
        assert merged.json()["aliases"] == []  # not ["Mira"]

    async with Session() as session:
        row = await session.get(Entity, target.id)
    assert row is not None
    assert row.search_text == "Mira"  # not "Mira Mira"


async def test_a_merge_folds_into_an_empty_body_without_leading_blank_lines() -> None:
    """The fold's heading opens the body when the survivor has none: the
    folded row starts at ``## <source name>``, not at blank lines."""
    target, source = await _entities(
        ("Haus", "location", ""), ("Mira", "character", "Miras Kapitel.")
    )
    async with _client() as client:
        merged = await client.post(
            f"/api/knowledge/entities/{source.id}/merge", json={"target_id": str(target.id)}
        )
        assert merged.status_code == 200
        assert merged.json()["content"] == "## Mira\n\nMiras Kapitel."


async def test_the_list_orders_by_similarity_not_creation() -> None:
    """The ``q`` tier's rank beats the row's age: the better match answers
    first even though it was created last — the two orders disagree here."""
    # The near match rides along unnamed: the assertion names it.
    _katharinka, katharina = await _entities(
        ("Katharinka", "character", ""), ("Katharina", "character", "")
    )
    async with _client() as client:
        found = await client.get(
            f"/api/knowledge/novels/{katharina.novel_id}/entities",
            params={"q": "Katharina"},
        )
        # the exact name ranks first (similarity 1.0), the near one second
        # (0.8) — creation order alone would answer the reverse
        assert [row["name"] for row in found.json()] == ["Katharina", "Katharinka"]


async def test_an_entity_cannot_merge_into_itself() -> None:
    mira, _haus = await _entities(("Mira", "character", ""), ("Haus", "location", ""))
    async with _client() as client:
        refused = await client.post(
            f"/api/knowledge/entities/{mira.id}/merge", json={"target_id": str(mira.id)}
        )
        assert refused.status_code == 422
        # the refusal deleted nothing
        listed = await client.get(f"/api/knowledge/novels/{mira.novel_id}/entities")
        assert len(listed.json()) == 2


async def test_a_merge_that_races_another_into_one_survivor_folds_from_the_fold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two concurrent merges into one survivor fold one after the other.

    The fold reads the survivor's fields before it writes them, so the
    reads must be row-locked reads: the second merge waits for the first
    one's commit and folds from the folded state. Two unlocked reads would
    both fold from the same pre-fold row, and the later commit would
    overwrite the earlier fold while both sources are deleted — one fold
    unrecoverable. The race is driven at the service seam, like the
    relation race tests: the first merge's two row locks are the window,
    and the second merge (a fresh session, a second service) runs inside
    it.
    """

    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title="Die Gleichzeitigkeit")
        session.add(novel)
        await session.flush()
        entities = EntityRepository(session, LOCAL_USER_ID)
        haus = await entities.create(
            novel.id, "Haus", "location", "Das alte Haus.", ["The House"], ["building"]
        )
        mira = await entities.create(
            novel.id, "Mira", "character", "Miras Kapitel.", ["Miralam"], ["protagonist"]
        )
        see = await entities.create(
            novel.id, "See", "location", "Der See liegt tief.", ["Der See"], ["Schauplatz"]
        )
        await session.commit()

    async with Session() as session_a, Session() as session_b:
        service_a = KnowledgeService(session_a, LOCAL_USER_ID, FakeEmbeddingProvider())
        service_b = KnowledgeService(session_b, LOCAL_USER_ID, FakeEmbeddingProvider())
        race: dict[str, asyncio.Task[Entity]] = {}
        original_locked = EntityRepository.locked
        locks = [0]

        async def racing_locked(self: EntityRepository, entity_id: UUID) -> Entity | None:
            row = await original_locked(self, entity_id)
            if self.session is not session_a:
                return row
            locks[0] += 1
            if locks[0] != 2:
                return row
            # The second merge runs while the first holds both locks: with
            # the locks it blocks on the survivor until the first commit;
            # without them it completes here and its fold is lost to the
            # first merge's stale overwrite. The final assertions tell the
            # two worlds apart.
            race["task"] = asyncio.create_task(service_b.merge_entities(see.id, haus.id))
            for _ in range(100):
                if race["task"].done():
                    break
                await asyncio.sleep(0.01)
            return row

        monkeypatch.setattr(EntityRepository, "locked", racing_locked)
        await service_a.merge_entities(mira.id, haus.id)
        await race["task"]

    async with Session() as session:
        survivor = await session.get(Entity, haus.id)
        assert survivor is not None
        # The survivor carries BOTH sources' contributions, in fold order.
        assert survivor.aliases == ["The House", "Miralam", "Mira", "Der See", "See"]
        assert survivor.tags == ["building", "protagonist", "Schauplatz"]
        assert survivor.content == (
            "Das alte Haus.\n\n## Mira\n\nMiras Kapitel.\n\n## See\n\nDer See liegt tief."
        )
        assert await session.get(Entity, mira.id) is None
        assert await session.get(Entity, see.id) is None


class _ExplodingEmbedding:
    """An embedding boundary that proves it was not asked."""

    def describe(self) -> str:
        return "exploding"

    def configuration_problems(self) -> list[str]:
        return []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise AssertionError(f"an entity write must not embed: {texts!r}")


async def test_entity_writes_never_reach_the_embedding_provider() -> None:
    """Accept, update and merge are entity writes, not corpus writes.

    No read path consumes an entity vector — the document vector is the corpus
    chat retrieves — so none of the three may wait for the provider or be
    refused by its width rule.
    """
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title="Der Stille Wald")
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
            type="character",
            description="Mira erscheint.",
            status="pending",
        )
        session.add(suggestion)
        repository = EntityRepository(session, LOCAL_USER_ID)
        haus = await repository.create(novel.id, "Haus", "location", "Das Haus.", [], [])
        see = await repository.create(novel.id, "See", "location", "Der See.", [], [])
        await session.commit()

        service = KnowledgeService(session, LOCAL_USER_ID, _ExplodingEmbedding())
        await service.accept_suggestion(suggestion.id)
        await service.update_entity(haus.id, EntityUpdate(name="Haus am See"))
        await service.merge_entities(see.id, haus.id)


async def test_a_merge_cannot_cross_novels() -> None:
    # Two novels, both the caller's own: the rows exist and are owned, but a
    # merge folds two entries of ONE story. Another novel's row is not a
    # target — the same invalid relation as merging a row into itself — and
    # the refusal must delete nothing on either side.
    [mira] = await _entities(("Mira", "character", ""))
    [haus] = await _entities(("Haus", "location", ""))
    async with _client() as client:
        refused = await client.post(
            f"/api/knowledge/entities/{mira.id}/merge", json={"target_id": str(haus.id)}
        )
        assert refused.status_code == 422

        # both rows survive, each in its own novel
        first = await client.get(f"/api/knowledge/novels/{mira.novel_id}/entities")
        second = await client.get(f"/api/knowledge/novels/{haus.novel_id}/entities")
        assert [row["name"] for row in first.json()] == ["Mira"]
        assert [row["name"] for row in second.json()] == ["Haus"]


async def test_another_users_entity_cannot_be_corrected() -> None:
    [mira] = await _entities(("Mira", "character", ""))
    await seed_user(OTHER_USER)
    async with Session() as session:
        novel = Novel(user_id=OTHER_USER, title="Fremder Roman")
        session.add(novel)
        await session.flush()
        theirs = Entity(user_id=OTHER_USER, novel_id=novel.id, name="Fremde Mira", type="character")
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
        # and neither are their relations reachable
        their_relations = await client.get(f"/api/knowledge/entities/{theirs.id}/relations")
        assert their_relations.status_code == 404

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
