"""Chapter positions: creations that overlap must not share a number — and
one transaction may rearrange the numbers, because the unique constraint
defers its check to commit.

A second click on "Neues Kapitel" before the first one lands is a legal
gesture, and the rail orders by ``position`` alone — with no tie-break, two
rows at one position are both a duplicated number in the list and an order the
planner picks. #521. The deferrable form (WP6 §1) is what lets a reorder's
writes pass through states the plain constraint refuses; deferral is not
amnesty, and the duplicate still dies at commit.
"""

import asyncio
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.api.main import app
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Chapter
from app.kernel.db.session import Session

pytestmark = pytest.mark.timeout(60)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _novel(client: AsyncClient, title: str = "Der Nebel") -> str:
    response = await client.post("/api/writing/novels", json={"title": title})
    return response.json()["id"]


async def _create_chapter(novel_id: str) -> int:
    """One request of its own, the way two clicks arrive: separate connections."""
    async with _client() as client:
        response = await client.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": ""})
        return response.status_code


async def test_chapters_created_at_once_get_distinct_positions() -> None:
    async with _client() as client:
        novel_id = await _novel(client)

    codes = await asyncio.gather(*(_create_chapter(novel_id) for _ in range(8)))
    assert codes == [201] * 8

    async with _client() as client:
        listed = (await client.get(f"/api/writing/novels/{novel_id}/chapters")).json()

    assert [chapter["position"] for chapter in listed] == list(range(8))


async def test_the_schema_refuses_two_chapters_at_one_position() -> None:
    """The allocation is guarded in code; the table refuses the collision too."""
    async with _client() as client:
        novel_id = await _novel(client)

    async with Session() as session:
        session.add(
            Chapter(user_id=LOCAL_USER_ID, novel_id=UUID(novel_id), title="", position=0, body="")
        )
        await session.commit()

        session.add(
            Chapter(user_id=LOCAL_USER_ID, novel_id=UUID(novel_id), title="", position=0, body="")
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_two_chapters_swap_positions_in_one_transaction() -> None:
    """A swap is two writes and one commit — no refused state in between.

    A renumber passes through shapes a plain unique constraint refuses
    (a sits at 1 while b still holds 1), so the check defers to the commit,
    where the pair is consistent again (WP6 §1).
    """
    async with _client() as client:
        novel_id = await _novel(client)
        for _ in range(2):
            assert await _create_chapter(novel_id) == 201
        listed = (await client.get(f"/api/writing/novels/{novel_id}/chapters")).json()

    a_id, b_id = UUID(listed[0]["id"]), UUID(listed[1]["id"])

    # two chapters at 0 and 1; inside one session, set a→1 and b→0, commit
    # (no flush between the two writes)
    async with Session() as session:
        rows = (
            (
                await session.execute(
                    select(Chapter)
                    .where(Chapter.novel_id == UUID(novel_id))
                    .order_by(Chapter.position)
                )
            )
            .scalars()
            .all()
        )
        a, b = rows
        a.position, b.position = 1, 0
        await session.commit()

    async with Session() as session:
        rows = (
            (
                await session.execute(
                    select(Chapter)
                    .where(Chapter.novel_id == UUID(novel_id))
                    .order_by(Chapter.position)
                )
            )
            .scalars()
            .all()
        )
        assert [(chapter.position, chapter.id) for chapter in rows] == [(0, b_id), (1, a_id)]


async def test_positions_constraint_is_deferred() -> None:
    """The catalog carries the deferral: ``DEFERRABLE INITIALLY DEFERRED``.

    ``condeferrable`` alone would accept the ``INITIALLY IMMEDIATE`` form,
    which checks at statement time and refuses the swap all the same;
    ``condeferred`` pins the initial mode the renumber relies on.
    """
    async with Session() as session:
        deferrable, initially_deferred = (
            await session.execute(
                text(
                    "SELECT condeferrable, condeferred FROM pg_constraint "
                    "WHERE contype = 'u' AND conrelid = 'chapters'::regclass "
                    "AND conname = 'uq_chapters_novel_id_position'"
                )
            )
        ).one()
    assert deferrable is True
    assert initially_deferred is True


async def test_a_direct_duplicate_position_is_refused_at_commit() -> None:
    """Deferral is not amnesty: a real duplicate still dies — at commit.

    The raw INSERT walks past the statement (that is what deferral bought)
    and meets the check when the transaction ends, the same boundary every
    renumber is consistent at.
    """
    async with _client() as client:
        novel_id = await _novel(client)
    assert await _create_chapter(novel_id) == 201

    async with Session() as session:
        await session.execute(
            text(
                "INSERT INTO chapters (id, user_id, novel_id, title, position, body, "
                "created_at, updated_at) "
                "VALUES (:id, :user_id, :novel_id, '', 0, '', now(), now())"
            ),
            {"id": uuid4(), "user_id": LOCAL_USER_ID, "novel_id": UUID(novel_id)},
        )
        with pytest.raises(IntegrityError):
            await session.commit()
