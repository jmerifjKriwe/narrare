"""Deleting a chapter: the row goes, the survivors close the gap in one
transaction, and no survivor's "last written" moves — the book lost a
chapter, no words were written (the novel's row is what advances, D8)."""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.capabilities.writing.repository import ChapterRepository
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import ConsistencyFinding, EntitySuggestion
from app.kernel.contracts.positions import lock_novel, next_chapter_position
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

pytestmark = pytest.mark.timeout(60)

OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _three_chapters(client: AsyncClient) -> tuple[str, list[Any]]:
    """A novel holding three chapters at positions 0, 1, 2 — the rail before
    any delete; the middle one is the gap the tests open."""
    novel = await client.post("/api/writing/novels", json={"title": "Der Nebel"})
    assert novel.status_code == 201
    chapters: list[Any] = []
    for title in ("Ankunft", "Nacht", "Abfahrt"):
        created = await client.post(
            f"/api/writing/novels/{novel.json()['id']}/chapters", json={"title": title}
        )
        assert created.status_code == 201
        chapters.append(created.json())
    return novel.json()["id"], chapters


async def test_delete_chapter_renumbers_contiguously() -> None:
    async with _client() as client:
        novel_id, chapters = await _three_chapters(client)

        deleted = await client.delete(f"/api/writing/chapters/{chapters[1]['id']}")
        assert deleted.status_code == 204

        listed = (await client.get(f"/api/writing/novels/{novel_id}/chapters")).json()
    # the rail shows the two survivors with no missing number between them
    assert [chapter["title"] for chapter in listed] == ["Ankunft", "Abfahrt"]
    assert [chapter["position"] for chapter in listed] == [0, 1]


async def test_delete_chapter_keeps_the_survivors_updated_at() -> None:
    async with _client() as client:
        _, chapters = await _three_chapters(client)

        deleted = await client.delete(f"/api/writing/chapters/{chapters[1]['id']}")
        assert deleted.status_code == 204

        survivors = [chapters[0], chapters[2]]
        for chapter in survivors:
            reloaded = await client.get(f"/api/writing/chapters/{chapter['id']}")
            assert reloaded.status_code == 200
            # the number moved; the "last written" did not — a renumber is
            # not a write (the column's onupdate is pinned off, D8)
            assert reloaded.json()["updated_at"] == chapter["updated_at"]


async def test_delete_chapter_advances_the_novel_timestamp() -> None:
    async with _client() as client:
        novel_id, chapters = await _three_chapters(client)
        before = datetime.fromisoformat(
            (await client.get(f"/api/writing/novels/{novel_id}")).json()["updated_at"]
        )

        deleted = await client.delete(f"/api/writing/chapters/{chapters[1]['id']}")
        assert deleted.status_code == 204

        after = datetime.fromisoformat(
            (await client.get(f"/api/writing/novels/{novel_id}")).json()["updated_at"]
        )
    # the archive lost a chapter, so the book was written in (D8)
    assert after > before


async def test_delete_chapter_cascades_its_pending_suggestions() -> None:
    async with _client() as client:
        novel_id, chapters = await _three_chapters(client)
    doomed, kept = UUID(chapters[1]["id"]), UUID(chapters[2]["id"])

    # one pending suggestion per chapter, the way extraction files them
    async with Session() as session:
        for chapter_id in (doomed, kept):
            session.add(
                EntitySuggestion(
                    user_id=LOCAL_USER_ID,
                    novel_id=UUID(novel_id),
                    chapter_id=chapter_id,
                    name="Robbe",
                    type="object",
                    status="pending",
                )
            )
        await session.commit()

    async with _client() as client:
        deleted = await client.delete(f"/api/writing/chapters/{doomed}")
        assert deleted.status_code == 204

    async with Session() as session:
        # the database's cascade, not the route's promise: the deleted
        # chapter's suggestion went with it; the survivor's stayed
        remaining = (
            await session.scalars(
                text("SELECT chapter_id FROM entity_suggestions WHERE novel_id = :novel_id"),
                {"novel_id": UUID(novel_id)},
            )
        ).all()
    assert remaining == [kept]


async def test_delete_chapter_leaves_findings() -> None:
    async with _client() as client:
        novel_id, chapters = await _three_chapters(client)

    # a finding belongs to the whole book, not to a chapter: it must
    # outlive one of them
    async with Session() as session:
        session.add(
            ConsistencyFinding(
                user_id=LOCAL_USER_ID,
                novel_id=UUID(novel_id),
                summary="Miras Augen sind blau und grün",
                status="pending",
            )
        )
        await session.commit()

    async with _client() as client:
        deleted = await client.delete(f"/api/writing/chapters/{chapters[1]['id']}")
        assert deleted.status_code == 204

    async with Session() as session:
        findings = await session.scalar(
            text("SELECT count(*) FROM consistency_findings WHERE novel_id = :novel_id"),
            {"novel_id": UUID(novel_id)},
        )
        assert findings == 1


async def test_a_delete_holds_the_books_lock_against_an_append() -> None:
    """An append must not allocate beside an uncommitted delete.

    The race the lock forbids: A deletes a chapter and renumbers while
    uncommitted; B, on its own connection, reads the committed max — 2 —
    and takes 3; A commits its renumber to [0, 1] and the rail shows
    [0, 1, 3], a hole no constraint catches, because nothing collided.
    The book's row lock — the one every append already takes — is what
    serialises the two: the delete holds it from its scoped load to its
    commit, so B either waits for the renumber and reads the closed-up
    max, or commits first and is renumbered with the survivors.

    Session A here is the delete held open at that window: the scoped
    load, the lock, the delete and the renumber through the flow's own
    repository calls, with the commit — the one boundary where the race
    happens — still ahead.
    """
    async with _client() as client:
        novel_id, chapters = await _three_chapters(client)
    novel, doomed = UUID(novel_id), UUID(chapters[1]["id"])

    async with Session() as a:
        repository = ChapterRepository(a, LOCAL_USER_ID)
        chapter = await repository.get(doomed)
        assert chapter is not None
        await lock_novel(a, user_id=LOCAL_USER_ID, novel_id=novel)
        await repository.delete(chapter)
        survivors = await repository.list_for_novel(novel)
        await repository.renumber(novel, [survivor.id for survivor in survivors])

        # B allocates while A's renumber sits uncommitted
        async with Session() as b:
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(
                    next_chapter_position(b, user_id=LOCAL_USER_ID, novel_id=novel),
                    timeout=0.5,
                )

        await a.commit()

    async with Session() as b:
        position = await next_chapter_position(b, user_id=LOCAL_USER_ID, novel_id=novel)
    # the survivors committed at 0 and 1, so the next number is 2 — not 3,
    # the hole a racing append would have taken from the stale max
    assert position == 2


async def test_delete_chapter_answers_404_for_a_foreign_chapter() -> None:
    await seed_user(OTHER_USER)
    novel_id, chapter_id = uuid4(), uuid4()
    async with Session() as session:
        await session.execute(
            text(
                "INSERT INTO novels (id, user_id, title, created_at, updated_at) "
                "VALUES (:id, :user_id, :title, now(), now())"
            ),
            {"id": novel_id, "user_id": OTHER_USER, "title": "Fremd"},
        )
        await session.execute(
            text(
                "INSERT INTO chapters "
                "(id, user_id, novel_id, title, position, body, created_at, updated_at) "
                "VALUES (:id, :user_id, :novel_id, :title, 0, '', now(), now())"
            ),
            {"id": chapter_id, "user_id": OTHER_USER, "novel_id": novel_id, "title": "Fremd"},
        )
        await session.commit()

    async with _client() as client:
        deleted = await client.delete(f"/api/writing/chapters/{chapter_id}")
        assert deleted.status_code == 404
        assert deleted.json()["detail"] == "chapter not found"
    # the refusal deleted nothing: the foreign chapter keeps its row
    async with Session() as session:
        kept = await session.scalar(
            text("SELECT count(*) FROM chapters WHERE id = :id"), {"id": chapter_id}
        )
        assert kept == 1
