"""The canon rule (D8): working on the canon counts as touching the book.

Every knowledge write that changes what the export archive carries — an
entity corrected or deleted, an edge added, retyped or deleted, a
suggestion accepted into an entity, a merge — advances the parent novel's
updated_at, the same bump a chapter write makes, so the shelf and the
export staleness warning read the canon as part of the book. The writes
that do not change the archive do not touch it: a document feeds the
search base, and a review verdict on a finding never entered the archive
at all. Every read here goes through a fresh session, so the answer is
the database's, not a session's identity map.
"""

from datetime import datetime  # noqa: TC003
from uuid import UUID  # noqa: TC003

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.main import app
from app.capabilities.knowledge.repository import RelationRepository
from app.capabilities.knowledge.service import KnowledgeService
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import (
    Chapter,
    ConsistencyFinding,
    Entity,
    EntitySuggestion,
    Novel,
)
from app.kernel.db.session import Session
from app.kernel.embeddings import FakeEmbeddingProvider

pytestmark = pytest.mark.timeout(60)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_novel(*names: str) -> tuple[Novel, list[Entity]]:
    """A novel with bare entities, seeded straight through the session:
    the canon rule is about rows that exist, not about how they were born."""
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title="Der Kanon")
        session.add(novel)
        await session.flush()
        created = [
            Entity(user_id=LOCAL_USER_ID, novel_id=novel.id, name=name, type="character")
            for name in names
        ]
        session.add_all(created)
        await session.commit()
        return novel, created


async def _pending_suggestion() -> tuple[Novel, EntitySuggestion]:
    """A novel with one pending suggestion — the state extraction leaves
    behind, seeded the way review's own tests arrange their rows."""
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title="Der Kanon")
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
            status="pending",
        )
        session.add(suggestion)
        await session.commit()
        return novel, suggestion


async def _pending_finding() -> tuple[Novel, ConsistencyFinding]:
    """A novel with one pending finding, seeded straight through the session."""
    async with Session() as session:
        novel = Novel(user_id=LOCAL_USER_ID, title="Der Kanon")
        session.add(novel)
        await session.flush()
        finding = ConsistencyFinding(
            user_id=LOCAL_USER_ID,
            novel_id=novel.id,
            summary="Mira: 34 vs. 37",
            status="pending",
        )
        session.add(finding)
        await session.commit()
        return novel, finding


async def _written_at(novel_id: UUID) -> datetime:
    """The novel's updated_at through a fresh session — the database's
    answer, never a session's identity map."""
    async with Session() as session:
        written_at = await session.scalar(select(Novel.updated_at).where(Novel.id == novel_id))
    assert written_at is not None
    return written_at


async def test_adding_an_relation_advances_the_novel() -> None:
    novel, [mira, haus] = await _seed_novel("Mira", "Haus")
    before = await _written_at(novel.id)
    async with _client() as client:
        created = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={"to_entity_id": str(haus.id), "relation_type": "lebt_in"},
        )
        assert created.status_code == 201
    assert await _written_at(novel.id) > before


async def test_retyping_a_relation_advances_the_novel() -> None:
    novel, [mira, haus] = await _seed_novel("Mira", "Haus")
    async with _client() as client:
        created = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={"to_entity_id": str(haus.id), "relation_type": "lebt_in"},
        )
        assert created.status_code == 201
        # read after the create: the retype alone must move the column
        before = await _written_at(novel.id)
        retyped = await client.patch(
            f"/api/knowledge/relations/{created.json()['id']}",
            json={"relation_type": "besucht"},
        )
        assert retyped.status_code == 200
    assert await _written_at(novel.id) > before


async def test_deleting_a_relation_advances_the_novel() -> None:
    novel, [mira, haus] = await _seed_novel("Mira", "Haus")
    async with _client() as client:
        created = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={"to_entity_id": str(haus.id), "relation_type": "lebt_in"},
        )
        assert created.status_code == 201
        before = await _written_at(novel.id)
        deleted = await client.delete(f"/api/knowledge/relations/{created.json()['id']}")
        assert deleted.status_code == 204
    assert await _written_at(novel.id) > before


async def test_editing_an_entity_advances_the_novel() -> None:
    novel, [mira] = await _seed_novel("Mira")
    before = await _written_at(novel.id)
    async with _client() as client:
        edited = await client.patch(
            f"/api/knowledge/entities/{mira.id}",
            json={"content": "Mira trägt immer den roten Schal."},
        )
        assert edited.status_code == 200
    assert await _written_at(novel.id) > before


async def test_deleting_an_entity_advances_the_novel() -> None:
    novel, [mira, _haus] = await _seed_novel("Mira", "Haus")
    before = await _written_at(novel.id)
    async with _client() as client:
        deleted = await client.delete(f"/api/knowledge/entities/{mira.id}")
        assert deleted.status_code == 204
    assert await _written_at(novel.id) > before


async def test_accepting_a_suggestion_advances_the_novel() -> None:
    novel, suggestion = await _pending_suggestion()
    before = await _written_at(novel.id)
    async with _client() as client:
        accepted = await client.post(f"/api/knowledge/suggestions/{suggestion.id}/accept")
        assert accepted.status_code == 200
    assert await _written_at(novel.id) > before


async def test_merging_entities_advances_the_novel() -> None:
    novel, [mira, haus] = await _seed_novel("Mira", "Haus")
    async with Session() as session:
        await RelationRepository(session, LOCAL_USER_ID).create(mira.id, haus.id, "lebt_in", None)
        await session.commit()
    before = await _written_at(novel.id)
    async with Session() as session:
        await KnowledgeService(session, LOCAL_USER_ID, FakeEmbeddingProvider()).merge_entities(
            mira.id, haus.id
        )
    assert await _written_at(novel.id) > before


async def test_ingesting_a_document_does_not_advance_the_novel() -> None:
    """A document feeds the search base, not the archive: the ingest
    changes nothing the export carries, so no novel's column moves."""
    novel, _entities = await _seed_novel("Mira")
    before = await _written_at(novel.id)
    async with Session() as session:
        await KnowledgeService(session, LOCAL_USER_ID, FakeEmbeddingProvider()).ingest(
            "Notizen", "Nebel über dem See."
        )
    assert await _written_at(novel.id) == before


async def test_dismissing_a_finding_does_not_advance_the_novel() -> None:
    """A finding never entered the archive: the verdict consumes the
    queue's row and moves nothing the export carries."""
    novel, finding = await _pending_finding()
    before = await _written_at(novel.id)
    async with _client() as client:
        dismissed = await client.post(f"/api/knowledge/findings/{finding.id}/dismiss")
        assert dismissed.status_code == 200
    assert await _written_at(novel.id) == before


async def test_a_refused_canon_write_leaves_the_novel_timestamp_alone() -> None:
    novel, [mira, haus] = await _seed_novel("Mira", "Haus")
    async with _client() as client:
        first = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={"to_entity_id": str(haus.id), "relation_type": "lebt_in"},
        )
        assert first.status_code == 201
    before = await _written_at(novel.id)
    async with _client() as client:
        refused = await client.post(
            f"/api/knowledge/entities/{mira.id}/relations",
            json={"to_entity_id": str(haus.id), "relation_type": "lebt_in"},
        )
        assert refused.status_code == 409
    assert await _written_at(novel.id) == before
