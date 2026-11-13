"""Chapter management: deleting a chapter closes its gap in one transaction,
and the order is written as one whole. A delete moves a number, never a
"last written" — the book lost a chapter, no words were written (the novel's
row is what advances, D8) — and a reorder whose body is not exactly the
book's current ids is refused with those ids, never silently reshaped."""

import asyncio
from collections.abc import Sequence  # noqa: TC003
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.capabilities.writing.repository import ChapterRepository
from app.capabilities.writing.schemas import ChapterUpdate
from app.capabilities.writing.service import WritingService
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Chapter, ConsistencyFinding, EntitySuggestion
from app.kernel.contracts.positions import next_chapter_position
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


async def test_a_delete_holds_the_books_lock_against_an_append(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An append must not allocate beside an uncommitted delete.

    The race the lock forbids: A deletes a chapter and renumbers while
    uncommitted; B, on its own connection, reads the committed max — 2 —
    and takes 3; A commits its renumber to [0, 1] and the rail shows
    [0, 1, 3], a hole no constraint catches, because nothing collided.
    The book's row lock — the one every append already takes — is what
    serialises the two: the delete holds it from its scoped load to its
    commit, so B either waits for the renumber and reads the closed-up
    max, or commits first and is renumbered with the survivors.

    The delete is the service's own method, gated open at its survivor
    read — the read whose uncommitted result a racing append stales, the
    one statement between the lock and the renumber — by a patched
    repository call that signals and waits: the scoped load, the lock and
    the delete have all really run when B tries, so removing the lock
    from the flow itself, or taking it a statement late, is what turns
    this test red.
    """
    async with _client() as client:
        novel_id, chapters = await _three_chapters(client)
    novel, doomed = UUID(novel_id), UUID(chapters[1]["id"])

    reached = asyncio.Event()
    release = asyncio.Event()
    original_survivors = ChapterRepository.list_for_novel

    async def survivors_gated_open(
        repository: ChapterRepository, novel_id: UUID
    ) -> Sequence[Chapter]:
        # The service is mid-transaction here — the lock taken, the row
        # gone, the commit ahead — holding the numbers B is about to read.
        reached.set()
        await release.wait()
        return await original_survivors(repository, novel_id)

    monkeypatch.setattr(ChapterRepository, "list_for_novel", survivors_gated_open)

    async with Session() as a:
        delete = asyncio.create_task(WritingService(a, LOCAL_USER_ID).delete_chapter(doomed))
        await asyncio.wait_for(reached.wait(), timeout=5)

        try:
            # B allocates while the delete sits uncommitted, lock held
            async with Session() as b:
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(
                        next_chapter_position(b, user_id=LOCAL_USER_ID, novel_id=novel),
                        timeout=0.5,
                    )
                # the refusal is a block, not a stalled loop: B's
                # statement reached the server and waits on the row lock,
                # proven by the TimeoutError above (the stronger proof
                # #668 asks for); `in_transaction()` alone would be true
                # for any wrapped read.
        finally:
            release.set()
            await delete

    # the rail the delete committed: the survivors closed the gap
    async with _client() as client:
        listed = (await client.get(f"/api/writing/novels/{novel_id}/chapters")).json()
    assert [chapter["position"] for chapter in listed] == [0, 1]

    async with Session() as b:
        position = await next_chapter_position(b, user_id=LOCAL_USER_ID, novel_id=novel)
    # the survivors committed at 0 and 1, so the next number is 2 — not 3,
    # the hole a racing append would have taken from the stale max
    assert position == 2


async def test_a_save_and_a_delete_cannot_deadlock_over_one_book(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A save and a delete of one book must take its rows in one order.

    The inversion the lock forbids: a save dirties its chapter, the touch's
    read autoflushes the UPDATE — the save holds the chapter row — and only
    then asks for the book's row; a delete holds the book's row and
    rewrites the chapter rows under it. Overlap and each waits for the
    other's row: Postgres answers 40P01 and the writing loop sees a raw
    500. The book's row first, always — the delete's and the reorder's
    order — and the two writers queue on the one lock instead.

    The save is the service's own method, gated open at its touch — after
    the flush that takes the chapter row, the moment the inverted order
    would be holding it without the book's — and the delete of ANOTHER
    chapter of the same book runs beside it on its own session. Both
    must finish, in either order the lock permits, and neither may die.
    """
    async with _client() as client:
        novel_id, chapters = await _three_chapters(client)
    saved_id, doomed = UUID(chapters[0]["id"]), UUID(chapters[2]["id"])

    reached = asyncio.Event()
    release = asyncio.Event()
    original_touch = ChapterRepository.touch_novel

    async def touch_novel_gated(repository: ChapterRepository, novel_id: UUID) -> None:
        await original_touch(repository, novel_id)
        # Mid-transaction: the save's UPDATE has autoflushed — the chapter
        # row is held — and (the fixed order) the book's row before it.
        reached.set()
        await release.wait()

    monkeypatch.setattr(ChapterRepository, "touch_novel", touch_novel_gated)

    async with Session() as a:
        save = asyncio.create_task(
            WritingService(a, LOCAL_USER_ID).update_chapter(
                saved_id, ChapterUpdate(body="Der Nebel hob sich.")
            )
        )
        await asyncio.wait_for(reached.wait(), timeout=5)

        try:
            async with Session() as b:
                delete = asyncio.create_task(
                    WritingService(b, LOCAL_USER_ID).delete_chapter(doomed)
                )
                # The delete waits — on the book's lock, the one order —
                # never on the save's chapter row while the save waits on
                # the book's (the cycle the inversion built).
                _, pending = await asyncio.wait({delete}, timeout=0.5)
                assert delete in pending
                release.set()
                # Once the save commits, the delete takes its turn and
                # finishes; a deadlock would die here or in the save.
                await asyncio.wait_for(delete, timeout=10)
        finally:
            release.set()
            await save

    # Both writes landed: the survivors closed the gap, and the gated
    # save's body is on the row it meant.
    async with _client() as client:
        listed = (await client.get(f"/api/writing/novels/{novel_id}/chapters")).json()
    assert [chapter["position"] for chapter in listed] == [0, 1]
    assert listed[0]["body"] == "Der Nebel hob sich."

    # The save still bumps the book's row — the lock must not cost the
    # touch: one more save, alone, advances the timestamp it reads.
    async with _client() as client:
        before = datetime.fromisoformat(
            (await client.get(f"/api/writing/novels/{novel_id}")).json()["updated_at"]
        )
        again = await client.put(
            f"/api/writing/chapters/{chapters[1]['id']}", json={"body": "Der Mond stieg."}
        )
        assert again.status_code == 200
        after = datetime.fromisoformat(
            (await client.get(f"/api/writing/novels/{novel_id}")).json()["updated_at"]
        )
    assert after > before


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


async def test_reorder_rewrites_contiguously() -> None:
    async with _client() as client:
        novel_id, chapters = await _three_chapters(client)

        reordered = await client.put(
            f"/api/writing/novels/{novel_id}/chapter-order",
            json={"chapter_ids": [chapters[2]["id"], chapters[0]["id"], chapters[1]["id"]]},
        )
        assert reordered.status_code == 204

        listed = (await client.get(f"/api/writing/novels/{novel_id}/chapters")).json()
    # the rail shows the arrangement the body asked for, numbered 0 to n-1
    assert [chapter["title"] for chapter in listed] == ["Abfahrt", "Ankunft", "Nacht"]
    assert [chapter["position"] for chapter in listed] == [0, 1, 2]


async def test_reorder_keeps_each_rows_updated_at() -> None:
    async with _client() as client:
        novel_id, chapters = await _three_chapters(client)

        reordered = await client.put(
            f"/api/writing/novels/{novel_id}/chapter-order",
            json={"chapter_ids": [chapter["id"] for chapter in reversed(chapters)]},
        )
        assert reordered.status_code == 204

        for chapter in chapters:
            reloaded = await client.get(f"/api/writing/chapters/{chapter['id']}")
            assert reloaded.status_code == 200
            # the number moved; the "last written" did not — an arrangement
            # is not a write (D8, the renumber's own pin)
            assert reloaded.json()["updated_at"] == chapter["updated_at"]


async def test_reorder_advances_the_novel_timestamp() -> None:
    async with _client() as client:
        novel_id, chapters = await _three_chapters(client)
        before = datetime.fromisoformat(
            (await client.get(f"/api/writing/novels/{novel_id}")).json()["updated_at"]
        )

        reordered = await client.put(
            f"/api/writing/novels/{novel_id}/chapter-order",
            json={"chapter_ids": [chapter["id"] for chapter in reversed(chapters)]},
        )
        assert reordered.status_code == 204

        after = datetime.fromisoformat(
            (await client.get(f"/api/writing/novels/{novel_id}")).json()["updated_at"]
        )
    # the arrangement changed the book (D8): the novel's row is what advances
    assert after > before


async def test_reorder_refuses_a_missing_id() -> None:
    async with _client() as client:
        novel_id, chapters = await _three_chapters(client)
        # reorder once so the stored order differs from creation order (#671)
        reordered = await client.put(
            f"/api/writing/novels/{novel_id}/chapter-order",
            json={"chapter_ids": [chapters[2]["id"], chapters[0]["id"], chapters[1]["id"]]},
        )
        assert reordered.status_code == 204
        stored = [chapters[2]["id"], chapters[0]["id"], chapters[1]["id"]]

        # a second tab created a chapter the body does not know: the body is
        # the old rail, one id short of the book
        refused = await client.put(
            f"/api/writing/novels/{novel_id}/chapter-order",
            json={"chapter_ids": [chapters[0]["id"], chapters[2]["id"]]},
        )
        assert refused.status_code == 409
        # the answer is the book's current whole, in its stored order — what
        # the client reverts to, not what it asked for
        assert refused.json() == {
            "detail": {
                "code": "order_mismatch",
                "chapter_ids": stored,
            }
        }


async def test_reorder_refuses_an_extra_id() -> None:
    async with _client() as client:
        novel_id, chapters = await _three_chapters(client)

        # a second tab deleted a chapter the body still carries: an id the
        # book no longer holds
        refused = await client.put(
            f"/api/writing/novels/{novel_id}/chapter-order",
            json={"chapter_ids": [chapters[0]["id"], chapters[1]["id"], str(uuid4())]},
        )
        assert refused.status_code == 409
        assert refused.json()["detail"]["code"] == "order_mismatch"


async def test_reorder_refuses_a_foreign_id() -> None:
    await seed_user(OTHER_USER)
    foreign_novel, foreign_chapter = uuid4(), uuid4()
    async with Session() as session:
        await session.execute(
            text(
                "INSERT INTO novels (id, user_id, title, created_at, updated_at) "
                "VALUES (:id, :user_id, :title, now(), now())"
            ),
            {"id": foreign_novel, "user_id": OTHER_USER, "title": "Fremd"},
        )
        await session.execute(
            text(
                "INSERT INTO chapters "
                "(id, user_id, novel_id, title, position, body, created_at, updated_at) "
                "VALUES (:id, :user_id, :novel_id, :title, 0, '', now(), now())"
            ),
            {
                "id": foreign_chapter,
                "user_id": OTHER_USER,
                "novel_id": foreign_novel,
                "title": "Fremd",
            },
        )
        await session.commit()

    async with _client() as client:
        novel_id, chapters = await _three_chapters(client)

        # the foreign chapter is a real row, another reader's: an id this
        # book does not hold, refused like any other — never adopted
        refused = await client.put(
            f"/api/writing/novels/{novel_id}/chapter-order",
            json={"chapter_ids": [chapters[0]["id"], chapters[1]["id"], str(foreign_chapter)]},
        )
        assert refused.status_code == 409
        assert refused.json()["detail"]["code"] == "order_mismatch"

    # the refusal reached nothing beyond this book: the foreign row kept its place
    async with Session() as session:
        position = await session.scalar(
            text("SELECT position FROM chapters WHERE id = :id"), {"id": foreign_chapter}
        )
        assert position == 0


async def test_reorder_refuses_a_duplicate_id() -> None:
    async with _client() as client:
        novel_id, chapters = await _three_chapters(client)

        # every id the book holds and one twice: the set matches, the length
        # does not — a repeated id is a stale arrangement like any other
        # (spec §2), not a field error
        refused = await client.put(
            f"/api/writing/novels/{novel_id}/chapter-order",
            json={
                "chapter_ids": [
                    chapters[0]["id"],
                    chapters[1]["id"],
                    chapters[2]["id"],
                    chapters[1]["id"],
                ]
            },
        )
        assert refused.status_code == 409
        assert refused.json()["detail"]["code"] == "order_mismatch"


async def test_reorder_leaves_the_order_untouched_on_refusal() -> None:
    async with _client() as client:
        novel_id, chapters = await _three_chapters(client)
        novel_before = (await client.get(f"/api/writing/novels/{novel_id}")).json()

        # a body that would have moved every row, were it the book's whole
        refused = await client.put(
            f"/api/writing/novels/{novel_id}/chapter-order",
            json={
                "chapter_ids": [chapter["id"] for chapter in reversed(chapters)] + [str(uuid4())]
            },
        )
        assert refused.status_code == 409

        listed = (await client.get(f"/api/writing/novels/{novel_id}/chapters")).json()
        for chapter in chapters:
            reloaded = await client.get(f"/api/writing/chapters/{chapter['id']}")
            # each row's number and "last written" are what they were
            assert reloaded.json()["position"] == chapter["position"]
            assert reloaded.json()["updated_at"] == chapter["updated_at"]
        novel_after = (await client.get(f"/api/writing/novels/{novel_id}")).json()
    # the refusal wrote nothing: the rail and the novel's own timestamp
    # are what they were
    assert [chapter["title"] for chapter in listed] == ["Ankunft", "Nacht", "Abfahrt"]
    assert [chapter["position"] for chapter in listed] == [0, 1, 2]
    assert novel_after["updated_at"] == novel_before["updated_at"]


async def test_reorder_answers_404_for_a_never_known_novel() -> None:
    async with _client() as client:
        refused = await client.put(
            f"/api/writing/novels/{uuid4()}/chapter-order",
            json={"chapter_ids": []},
        )
        assert refused.status_code == 404
        assert refused.json()["detail"] == "novel not found"


async def test_reorder_answers_404_for_a_foreign_novel() -> None:
    await seed_user(OTHER_USER)
    foreign_novel = uuid4()
    async with Session() as session:
        await session.execute(
            text(
                "INSERT INTO novels (id, user_id, title, created_at, updated_at) "
                "VALUES (:id, :user_id, :title, now(), now())"
            ),
            {"id": foreign_novel, "user_id": OTHER_USER, "title": "Fremd"},
        )
        await session.commit()

    async with _client() as client:
        _, chapters = await _three_chapters(client)
        refused = await client.put(
            f"/api/writing/novels/{foreign_novel}/chapter-order",
            json={"chapter_ids": [chapters[0]["id"]]},
        )
        assert refused.status_code == 404
        assert refused.json()["detail"] == "novel not found"
