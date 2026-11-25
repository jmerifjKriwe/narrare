"""Creating an entity by hand, with its relations, in one transaction.

The extraction review can already file an entity; this contract is the
writer's own door: a name, a type, its labels and a body, plus the relation
lines to place. Every line is resolved against the novel before anything is
written, so a refused line leaves no half-made canon behind. Duplicate names
stay allowed — the graph can merge them, and the dialog warns without
blocking.
"""

from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response

from app.api.main import app
from app.capabilities.knowledge.repository import EntityRepository
from app.capabilities.knowledge.service import KnowledgeService
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Chapter, Entity, EntitySuggestion, Novel
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = uuid4()

STATION_NAME = "Forschungsstation 7"
CHEN_NAME = "Dr. Lin Chen"


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_novel(title: str = "Die Nevada-Anlage") -> tuple[Novel, Entity, Entity]:
    """One novel with two canon rows: the create's natural relation targets."""
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title=title)
        session.add(novel)
        await session.flush()
        repository = EntityRepository(session, LOCAL_USER_ID)
        station = await repository.create(novel.id, STATION_NAME, "location", "", [], [])
        chen = await repository.create(novel.id, CHEN_NAME, "character", "", [], [])
        await session.commit()
        return novel, station, chen


async def _entity_count(client: AsyncClient, novel_id: UUID) -> int:
    response = await client.get(f"/api/knowledge/novels/{novel_id}/entities")
    assert response.status_code == 200
    return len(response.json())


def _body(
    novel_id: UUID,
    *,
    name: str = "Nevada-Trümmerfeld",
    type_: str = "location",
    relations: list[dict[str, Any]] | None = None,
) -> dict[str, object]:
    return {
        "novel_id": str(novel_id),
        "name": name,
        "type": type_,
        "aliases": ["Nevada"],
        "tags": ["Ruine"],
        "content": "Ein Feld aus alten Trümmern.",
        "relations": relations or [],
    }


def _coded(response: Response) -> dict[str, object]:
    """The whole coded detail: the code and sentence the surface localizes,
    plus the structure it marks instead of printing."""
    detail = cast("dict[str, object]", response.json()["detail"])
    code = detail["code"]
    text = detail["detail"]
    assert isinstance(code, str)
    assert isinstance(text, str)
    return detail


async def test_create_writes_entity_and_relations_in_one_transaction() -> None:
    novel, station, _chen = await _seed_novel()
    payload = _body(
        novel.id,
        relations=[
            {
                "to_entity_id": str(station.id),
                "relation_type": "located_in",
                "note": "nördlich der Station",
            }
        ],
    )
    async with _client() as client:
        response = await client.post("/api/knowledge/entities", json=payload)
        assert response.status_code == 201, response.text
        entity = response.json()
        assert entity["novel_id"] == str(novel.id)
        assert entity["name"] == "Nevada-Trümmerfeld"
        assert entity["type"] == "location"
        assert entity["aliases"] == ["Nevada"]
        assert entity["tags"] == ["Ruine"]
        assert entity["content"] == "Ein Feld aus alten Trümmern."

        listed = await client.get(f"/api/knowledge/novels/{novel.id}/entities")
        assert "Nevada-Trümmerfeld" in [row["name"] for row in listed.json()]

        edges = await client.get(f"/api/knowledge/entities/{entity['id']}/relations")
        assert edges.status_code == 200
        assert [
            (edge["from_entity_id"], edge["to_entity_id"], edge["relation_type"], edge["note"])
            for edge in edges.json()
        ] == [(entity["id"], str(station.id), "located_in", "nördlich der Station")]


async def test_foreign_novel_is_404() -> None:
    await seed_user(OTHER_USER)
    async with Session() as session:
        foreign = Novel(user_id=OTHER_USER, title="Fremdes Buch")
        session.add(foreign)
        await session.commit()

    async with _client() as client:
        foreign_response = await client.post("/api/knowledge/entities", json=_body(foreign.id))
        assert foreign_response.status_code == 404
        assert _coded(foreign_response)["code"] == "not-found"
        absent = await client.post(
            "/api/knowledge/entities", json=_body(UUID("00000000-0000-0000-0000-0000000000ff"))
        )
        assert absent.status_code == 404
        assert _coded(absent)["code"] == "not-found"


async def test_invalid_name_and_type_are_422_naming_the_field() -> None:
    novel, _station, _chen = await _seed_novel()
    async with _client() as client:
        before = await _entity_count(client, novel.id)
        for name in ("", "   ", "x" * 201):
            refused = await client.post("/api/knowledge/entities", json=_body(novel.id, name=name))
            assert refused.status_code == 422, name
            detail = _coded(refused)
            assert detail["code"] == "entity-invalid"
            assert detail["field"] == "name"
            assert "name" in str(detail["detail"])

        unknown_type = await client.post(
            "/api/knowledge/entities", json=_body(novel.id, type_="idea")
        )
        assert unknown_type.status_code == 422
        detail = _coded(unknown_type)
        assert detail["code"] == "entity-invalid"
        assert detail["field"] == "type"
        assert "type" in str(detail["detail"])

        # no refusal wrote anything
        assert await _entity_count(client, novel.id) == before


async def test_blank_or_over_long_relation_type_is_the_coded_422() -> None:
    """The relation label's bounds are the service's coded refusal, not the
    framework's field list: the route's own branch answers both."""
    novel, station, _chen = await _seed_novel()
    async with _client() as client:
        before = await _entity_count(client, novel.id)
        for relation_type in ("   ", "x" * 81):
            refused = await client.post(
                "/api/knowledge/entities",
                json=_body(
                    novel.id,
                    relations=[
                        {
                            "to_entity_id": str(station.id),
                            "relation_type": relation_type,
                            "note": None,
                        }
                    ],
                ),
            )
            assert refused.status_code == 422, relation_type
            detail = _coded(refused)
            assert detail["code"] == "entity-invalid"
            assert detail["field"] == "relation type"
            assert "relation type" in str(detail["detail"])
        assert await _entity_count(client, novel.id) == before


async def test_more_than_twelve_relation_lines_is_the_coded_relation_limit() -> None:
    """The proposal's own bound holds on the request side too: a create asks
    for at most twelve relations, and the thirteenth line refuses the whole
    request before anything is written."""
    novel, station, chen = await _seed_novel()
    async with _client() as client:
        before = await _entity_count(client, novel.id)
        relations = [
            {
                "to_entity_id": str(station.id if index % 2 == 0 else chen.id),
                "relation_type": f"verweist_{index}",
                "note": None,
            }
            for index in range(13)
        ]
        refused = await client.post(
            "/api/knowledge/entities", json=_body(novel.id, relations=relations)
        )
        assert refused.status_code == 422, refused.text
        detail = _coded(refused)
        assert detail["code"] == "relation-limit"
        assert detail["row"] == 12
        assert "12" in str(detail["detail"])
        assert await _entity_count(client, novel.id) == before


async def test_novel_deleted_before_the_flush_is_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ownership check passed, then the novel vanished before the entity
    row flushed: the foreign key is the scoped absence's 404, never a 500."""
    novel, _station, _chen = await _seed_novel()
    original = getattr(KnowledgeService, "_own_novel")  # noqa: B009

    async def vanish(self: KnowledgeService, novel_id: UUID) -> Novel:
        row = await original(self, novel_id)
        await self.session.delete(row)
        await self.session.commit()
        return row

    monkeypatch.setattr(KnowledgeService, "_own_novel", vanish)
    async with _client() as client:
        refused = await client.post("/api/knowledge/entities", json=_body(novel.id))
    assert refused.status_code == 404, refused.text
    assert _coded(refused)["code"] == "not-found"


async def test_relation_outside_the_novel_refuses_and_leaves_no_row() -> None:
    novel, station, _chen = await _seed_novel()
    # A second novel of the caller's own: the row exists and is owned, but an
    # edge joins one story, so it is outside this novel.
    other_novel, other_entity, _ = await _seed_novel("Der andere Roman")
    async with _client() as client:
        before = await _entity_count(client, novel.id)
        before_edges = (await client.get(f"/api/knowledge/novels/{novel.id}/relations")).json()
        payload = _body(
            novel.id,
            relations=[
                {"to_entity_id": str(station.id), "relation_type": "located_in", "note": None},
                {"to_entity_id": str(other_entity.id), "relation_type": "knows", "note": None},
            ],
        )
        refused = await client.post("/api/knowledge/entities", json=payload)
        assert refused.status_code == 422, refused.text
        detail = _coded(refused)
        assert detail["code"] == "relation-target-invalid"
        assert detail["row"] == 1  # the refused row's sent-list index
        assert "1" in str(detail["detail"])

        # the valid first line was written to the same transaction and rolled
        # back with it: no entity, no edge
        assert await _entity_count(client, novel.id) == before
        assert (
            await client.get(f"/api/knowledge/novels/{novel.id}/relations")
        ).json() == before_edges
        assert other_novel.id != novel.id


async def test_duplicate_relation_line_is_422() -> None:
    novel, station, _chen = await _seed_novel()
    async with _client() as client:
        before = await _entity_count(client, novel.id)
        line = {"to_entity_id": str(station.id), "relation_type": "located_in", "note": None}
        refused = await client.post(
            "/api/knowledge/entities", json=_body(novel.id, relations=[line, dict(line)])
        )
        assert refused.status_code == 422, refused.text
        detail = _coded(refused)
        assert detail["code"] == "relation-duplicate"
        assert detail["row"] == 1
        assert "row 1" in str(detail["detail"])
        assert await _entity_count(client, novel.id) == before


async def test_accept_suggestion_still_creates_through_the_shared_core(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The review path keeps its birth: accept still files the entity through
    the create-by-hand core, so the name/type validation has one copy."""
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title="Die Auflösung")
        session.add(novel)
        await session.flush()
        chapter = Chapter(user_id=LOCAL_USER_ID, novel_id=novel.id, title="Ankunft", position=0)
        session.add(chapter)
        await session.flush()
        suggestion = EntitySuggestion(
            user_id=LOCAL_USER_ID,
            novel_id=novel.id,
            chapter_id=chapter.id,
            name="Leuchtturm",
            type="location",
            description="Der Leuchtturm erscheint.",
            status="pending",
        )
        session.add(suggestion)
        await session.commit()

    calls: list[tuple[object, ...]] = []
    original = getattr(KnowledgeService, "_create_entity_row")  # noqa: B009

    async def spy(self: KnowledgeService, *args: object, **kwargs: object) -> Entity:
        calls.append(args)
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(KnowledgeService, "_create_entity_row", spy)
    async with _client() as client:
        accepted = await client.post(f"/api/knowledge/suggestions/{suggestion.id}/accept")
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["entity"]["name"] == "Leuchtturm"
    assert calls, "accept did not go through the shared create core"
