"""Relations: directed edges between an entity and the rest of the canon.

An edge is free-text typed (the vocabulary is a UI suggestion, not an API
constraint), unique per (owner, from, to, type), listed for both of its
ends, and patchable in type and note only — the ends are immutable, moving
an edge is delete plus create. Self-relations are allowed; flagging them
is the UI's business, not the API's. When an entity goes, its foreign keys
cascade: the delete contract takes the edges along. The scoping answer is
the product's one answer everywhere: another user's row is a 404,
indistinguishable from no row at all.
"""

from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.main import app
from app.capabilities.knowledge.repository import RelationRepository
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Entity, EntityRelation, Novel
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = uuid4()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed(*names: str) -> tuple[Novel, list[Entity]]:
    """A novel with bare entities, seeded straight through the session.

    The relation contract is about rows that exist, not about how they
    were born — review's own tests pin the birth.
    """
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title="Die Verbindungen")
        session.add(novel)
        await session.flush()
        created = [
            Entity(user_id=LOCAL_USER_ID, novel_id=novel.id, name=name, type="character")
            for name in names
        ]
        session.add_all(created)
        await session.commit()
        return novel, created


async def test_a_relation_is_created_and_listed_for_both_ends() -> None:
    _novel, [mira, haus] = await _seed("Mira", "Haus")
    async with _client() as client:
        created = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={"to_entity_id": str(haus.id), "relation_type": "lebt_in", "note": "Sommer 1893"},
        )
        assert created.status_code == 201
        edge = created.json()
        assert edge["from_entity_id"] == str(mira.id)
        assert edge["to_entity_id"] == str(haus.id)
        assert edge["relation_type"] == "lebt_in"
        assert edge["note"] == "Sommer 1893"

        from_mira = (await client.get(f"/api/knowledge/entities/{mira.id}/relations")).json()
        from_haus = (await client.get(f"/api/knowledge/entities/{haus.id}/relations")).json()
        # both directions: the target's list carries the same edge
        assert [row["id"] for row in from_mira] == [edge["id"]]
        assert [row["id"] for row in from_haus] == [edge["id"]]


async def test_the_list_is_created_at_order_with_both_directions() -> None:
    _novel, [mira, haus, see] = await _seed("Mira", "Haus", "See")
    async with _client() as client:
        outgoing = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={"to_entity_id": str(see.id), "relation_type": "lebt_am"},
        )
        incoming = await client.post(
            f"/api/knowledge/entities/{haus.id}/relations",
            json={"to_entity_id": str(mira.id), "relation_type": "erwähnt"},
        )
        assert outgoing.status_code == incoming.status_code == 201

        from_mira = (await client.get(f"/api/knowledge/entities/{mira.id}/relations")).json()
        assert [row["relation_type"] for row in from_mira] == ["lebt_am", "erwähnt"]
        from_see = (await client.get(f"/api/knowledge/entities/{see.id}/relations")).json()
        assert [row["relation_type"] for row in from_see] == ["lebt_am"]
        from_haus = (await client.get(f"/api/knowledge/entities/{haus.id}/relations")).json()
        assert [row["relation_type"] for row in from_haus] == ["erwähnt"]


async def test_a_self_relation_is_allowed() -> None:
    _novel, [mira] = await _seed("Mira")
    async with _client() as client:
        created = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={"to_entity_id": str(mira.id), "relation_type": "kennt_sich_selbst"},
        )
        assert created.status_code == 201
        edge = created.json()
        assert edge["from_entity_id"] == edge["to_entity_id"] == str(mira.id)


async def test_a_duplicate_edge_conflicts_but_a_new_type_does_not() -> None:
    _novel, [mira, haus] = await _seed("Mira", "Haus")
    path = f"/api/knowledge/entities/{mira.id}/relations"
    async with _client() as client:
        first = await client.post(
            path, json={"to_entity_id": str(haus.id), "relation_type": "lebt_in"}
        )
        assert first.status_code == 201

        same = await client.post(
            path, json={"to_entity_id": str(haus.id), "relation_type": "lebt_in"}
        )
        assert same.status_code == 409

        # the type is part of the identity: another type is another edge,
        # and the reverse direction is its own edge too
        other_type = await client.post(
            path, json={"to_entity_id": str(haus.id), "relation_type": "besucht"}
        )
        assert other_type.status_code == 201
        reverse = await client.post(
            f"/api/knowledge/entities/{haus.id}/relations",
            json={"to_entity_id": str(mira.id), "relation_type": "lebt_in"},
        )
        assert reverse.status_code == 201


async def test_a_relation_needs_both_ends_present_owned_and_local() -> None:
    _novel, [mira] = await _seed("Mira")
    await seed_user(OTHER_USER)
    async with Session() as session:
        foreign_novel = Novel(user_id=OTHER_USER, title="Fremder Roman")
        session.add(foreign_novel)
        await session.flush()
        foreign = Entity(
            user_id=OTHER_USER, novel_id=foreign_novel.id, name="Fremde Mira", type="character"
        )
        session.add(foreign)
        # my own second novel: owned, but another story — an edge joins one story
        second_novel = Novel(user_id=LOCAL_USER_ID, title="Zweiter Roman")
        session.add(second_novel)
        await session.flush()
        elsewhere = Entity(
            user_id=LOCAL_USER_ID, novel_id=second_novel.id, name="Andere Mira", type="character"
        )
        session.add(elsewhere)
        await session.commit()

    async with _client() as client:
        unknown_target = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={
                "to_entity_id": "00000000-0000-0000-0000-0000000000ff",
                "relation_type": "kennt",
            },
        )
        assert unknown_target.status_code == 404

        # another user's entity is the same absence
        theirs = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={"to_entity_id": str(foreign.id), "relation_type": "kennt"},
        )
        assert theirs.status_code == 404

        # and so is an entity from another novel of mine
        other_story = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={"to_entity_id": str(elsewhere.id), "relation_type": "kennt"},
        )
        assert other_story.status_code == 404

        unknown_source = await client.post(
            f"/api/knowledge/entities/{uuid4()}/relations",
            json={"to_entity_id": str(mira.id), "relation_type": "kennt"},
        )
        assert unknown_source.status_code == 404


async def test_a_patch_changes_only_the_fields_the_body_carries() -> None:
    _novel, [mira, haus, see] = await _seed("Mira", "Haus", "See")
    async with _client() as client:
        created = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={"to_entity_id": str(haus.id), "relation_type": "lebt_in", "note": "Sommer 1893"},
        )
        edge_id = created.json()["id"]
        path = f"/api/knowledge/relations/{edge_id}"

        noted = await client.patch(path, json={"note": "Winter 1893"})
        assert noted.status_code == 200
        assert noted.json()["note"] == "Winter 1893"
        assert noted.json()["relation_type"] == "lebt_in"
        assert noted.json()["to_entity_id"] == str(haus.id)

        retyped = await client.patch(path, json={"relation_type": "besucht"})
        assert retyped.status_code == 200
        assert retyped.json()["relation_type"] == "besucht"
        assert retyped.json()["note"] == "Winter 1893"

        # null is a value, not an absence: the note clears
        cleared = await client.patch(path, json={"note": None})
        assert cleared.status_code == 200
        assert cleared.json()["note"] is None

        # the ends are immutable: the body cannot move the edge
        unmoved = await client.patch(path, json={"to_entity_id": str(see.id)})
        assert unmoved.status_code == 200
        assert unmoved.json()["from_entity_id"] == str(mira.id)
        assert unmoved.json()["to_entity_id"] == str(haus.id)

        for relation_type in ("   ", "x" * 81):
            refused = await client.patch(path, json={"relation_type": relation_type})
            assert refused.status_code == 422, relation_type


async def test_a_patched_type_cannot_collide_with_a_sibling_edge() -> None:
    _novel, [mira, haus] = await _seed("Mira", "Haus")
    async with _client() as client:
        path = f"/api/knowledge/entities/{mira.id}/relations"
        first = await client.post(
            path, json={"to_entity_id": str(haus.id), "relation_type": "lebt_in"}
        )
        second = await client.post(
            path, json={"to_entity_id": str(haus.id), "relation_type": "besucht"}
        )
        assert first.status_code == second.status_code == 201

        collided = await client.patch(
            f"/api/knowledge/relations/{second.json()['id']}",
            json={"relation_type": "lebt_in"},
        )
        assert collided.status_code == 409

        # a free type still goes through, and stays its own edge
        free = await client.patch(
            f"/api/knowledge/relations/{second.json()['id']}",
            json={"relation_type": "kennt"},
        )
        assert free.status_code == 200
        assert free.json()["relation_type"] == "kennt"


async def test_a_retype_colliding_with_a_concurrent_sibling_answers_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The race backstop: a sibling created between this request's duplicate
    look and its commit falls to the unique constraint, and the answer is the
    duplicate's 409 — a concurrent PATCH is a conflict, never a 500.
    """
    _novel, [mira, haus] = await _seed("Mira", "Haus")
    async with _client() as client:
        second = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={"to_entity_id": str(haus.id), "relation_type": "besucht"},
        )
        assert second.status_code == 201

        original_edge = RelationRepository.edge

        async def racing_edge(
            self: RelationRepository, from_id: UUID, to_id: UUID, relation_type: str
        ) -> EntityRelation | None:
            found = await original_edge(self, from_id, to_id, relation_type)
            if found is None:
                # The concurrent writer's insert lands in the window between
                # this request's look and its commit. The row enters the
                # session unflushed, so the constraint's verdict falls on the
                # commit — exactly where a committed concurrent insert puts it.
                self.session.add(
                    EntityRelation(
                        user_id=self.user_id,
                        from_entity_id=from_id,
                        to_entity_id=to_id,
                        relation_type=relation_type,
                    )
                )
            return found

        monkeypatch.setattr(RelationRepository, "edge", racing_edge)
        collided = await client.patch(
            f"/api/knowledge/relations/{second.json()['id']}",
            json={"relation_type": "kennt"},
        )
        assert collided.status_code == 409


async def test_a_duplicate_created_in_a_race_answers_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The unique-violation branch of the create backstop: a concurrent create
    of the same edge is the duplicate's 409 — the branch the FK race must not
    take (its own test pins the 404)."""
    _novel, [mira, haus] = await _seed("Mira", "Haus")
    original_edge = RelationRepository.edge

    async def racing_edge(
        self: RelationRepository, from_id: UUID, to_id: UUID, relation_type: str
    ) -> EntityRelation | None:
        found = await original_edge(self, from_id, to_id, relation_type)
        if found is None:
            self.session.add(
                EntityRelation(
                    user_id=self.user_id,
                    from_entity_id=from_id,
                    to_entity_id=to_id,
                    relation_type=relation_type,
                )
            )
        return found

    monkeypatch.setattr(RelationRepository, "edge", racing_edge)
    async with _client() as client:
        created = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={"to_entity_id": str(haus.id), "relation_type": "kennt"},
        )
        assert created.status_code == 409


async def test_a_target_deleted_in_a_race_is_an_absence_not_a_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The FK branch of the create backstop: a target deleted between this
    request's reads and its insert fails the edge's foreign key — the scoped
    absence's 404, not the duplicate's 409."""
    _novel, [mira, haus] = await _seed("Mira", "Haus")
    original_create = RelationRepository.create

    async def racing_create(
        self: RelationRepository,
        from_id: UUID,
        to_id: UUID,
        relation_type: str,
        note: str | None,
    ) -> EntityRelation:
        async with Session() as other:
            target = await other.get(Entity, to_id)
            if target is not None:
                await other.delete(target)
                await other.commit()
        return await original_create(self, from_id, to_id, relation_type, note)

    monkeypatch.setattr(RelationRepository, "create", racing_create)
    async with _client() as client:
        created = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={"to_entity_id": str(haus.id), "relation_type": "kennt"},
        )
        assert created.status_code == 404


async def test_a_relation_type_is_stripped_before_the_duplicate_check() -> None:
    """A padded type is stored trimmed: the stored form is the edge's identity,
    so its trimmed twin is the duplicate the constraint would catch — not a
    second edge that dodges the check by its whitespace."""
    _novel, [mira, haus] = await _seed("Mira", "Haus")
    path = f"/api/knowledge/entities/{mira.id}/relations"
    async with _client() as client:
        padded = await client.post(
            path, json={"to_entity_id": str(haus.id), "relation_type": "lebt_in "}
        )
        assert padded.status_code == 201
        assert padded.json()["relation_type"] == "lebt_in"

        again = await client.post(
            path, json={"to_entity_id": str(haus.id), "relation_type": "lebt_in"}
        )
        assert again.status_code == 409


async def test_a_delete_removes_exactly_the_edge() -> None:
    _novel, [mira, haus] = await _seed("Mira", "Haus")
    async with _client() as client:
        created = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={"to_entity_id": str(haus.id), "relation_type": "lebt_in"},
        )
        edge_id = created.json()["id"]

        gone = await client.delete(f"/api/knowledge/relations/{edge_id}")
        assert gone.status_code == 204

        from_mira = (await client.get(f"/api/knowledge/entities/{mira.id}/relations")).json()
        assert from_mira == []

        again = await client.delete(f"/api/knowledge/relations/{edge_id}")
        assert again.status_code == 404


async def test_an_entity_delete_takes_its_edges_along() -> None:
    _novel, [mira, haus] = await _seed("Mira", "Haus")
    async with _client() as client:
        created = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={"to_entity_id": str(haus.id), "relation_type": "lebt_in"},
        )
        assert created.status_code == 201

        deleted = await client.delete(f"/api/knowledge/entities/{mira.id}")
        assert deleted.status_code == 204

        # the foreign keys cascade: no edge outlives its end
        from_haus = (await client.get(f"/api/knowledge/entities/{haus.id}/relations")).json()
        assert from_haus == []
        async with Session() as session:
            edges = (await session.scalars(select(EntityRelation))).all()
        assert edges == []


async def test_another_users_relation_is_absent() -> None:
    _novel, _mira = await _seed("Mira")
    await seed_user(OTHER_USER)
    async with Session() as session:
        foreign_novel = Novel(user_id=OTHER_USER, title="Fremder Roman")
        session.add(foreign_novel)
        await session.flush()
        theirs = Entity(
            user_id=OTHER_USER, novel_id=foreign_novel.id, name="Fremde Mira", type="character"
        )
        session.add(theirs)
        await session.flush()
        edge = EntityRelation(
            user_id=OTHER_USER,
            from_entity_id=theirs.id,
            to_entity_id=theirs.id,
            relation_type="kennt",
        )
        session.add(edge)
        await session.commit()

    async with _client() as client:
        patched = await client.patch(
            f"/api/knowledge/relations/{edge.id}", json={"note": "Übernommen"}
        )
        assert patched.status_code == 404
        deleted = await client.delete(f"/api/knowledge/relations/{edge.id}")
        assert deleted.status_code == 404
        listed = await client.get(f"/api/knowledge/entities/{theirs.id}/relations")
        assert listed.status_code == 404

    async with Session() as session:
        row = await session.get(EntityRelation, edge.id)
    assert row is not None
    assert row.note is None  # the refusals wrote nothing
