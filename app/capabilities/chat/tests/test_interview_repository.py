"""The interview's storage: sessions, turns, the roster and the novel's heading.

Two users prove the narrowing on every path — another user's session is absent,
not an error — and the database proves the two invariants the service above
leans on: one ``seq`` per session, and a deleted novel taking its sessions and
their turns with it.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.capabilities.chat.models import AssistantSession, AssistantTurn
from app.capabilities.chat.repository import (
    AssistantSessionRepository,
    EntityRosterRepository,
    NovelRepository,
)
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Entity, Novel
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user

MODE = "knowledge.entity"
OTHER_USER = UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture
async def two_users(empty_tables: None, schema: None) -> None:
    """The local writer and one stranger: ownership is what the scope reads.

    ``empty_tables`` seeds the local user; ``schema`` so a single-file run on a
    fresh test database rebuilds the tables before anything truncates them.
    """
    await seed_user(OTHER_USER)


async def _seed_novel(
    user_id: UUID = LOCAL_USER_ID, title: str = "The Lighthouse", genre: str | None = None
) -> Novel:
    """A novels row straight through the session — the rows' shape, not a flow."""
    async with Session() as session:
        novel = Novel(user_id=user_id, title=title, genre=genre)
        session.add(novel)
        await session.commit()
        return novel


async def _seed_entities(novel: Novel, names: tuple[str, ...]) -> None:
    async with Session() as session:
        session.add_all(
            Entity(
                user_id=novel.user_id,
                novel_id=novel.id,
                name=name,
                type="character",
                aliases=[name[:1]],
                content="unread by the roster",
            )
            for name in names
        )
        await session.commit()


@pytest.mark.usefixtures("two_users")
async def test_create_and_get() -> None:
    """A new session carries its scope, mode, type and target; get reads it back."""
    novel = await _seed_novel(genre="gothic")
    target_id = uuid4()
    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        created = await repo.create(novel.id, MODE, "character", target_id)
        await session.commit()

    assert created.novel_id == novel.id
    assert created.mode == MODE
    assert created.entity_type == "character"
    assert created.target_id == target_id
    assert created.proposal is None
    assert created.closed_at is None
    assert created.user_id == LOCAL_USER_ID
    assert created.created_at is not None
    assert created.updated_at is not None

    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        fetched = await repo.get(created.id)
        assert fetched is not None
        assert fetched.id == created.id

        await repo.set_proposal(fetched, {"name": "Mira", "aliases": []})
        await repo.close(fetched)
        await session.commit()

    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        closed = await repo.get(created.id)
        assert closed is not None
        assert closed.proposal == {"name": "Mira", "aliases": []}
        assert closed.closed_at is not None

        novel_repo = NovelRepository(session, LOCAL_USER_ID)
        assert await novel_repo.exists(novel.id) is True
        assert await novel_repo.heading(novel.id) == ("The Lighthouse", "gothic")


@pytest.mark.usefixtures("two_users")
async def test_a_foreign_session_is_none() -> None:
    """Another user's session answers as absent to both read and lock."""
    novel = await _seed_novel()
    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        created = await repo.create(novel.id, MODE, "character", None)
        await session.commit()
        session_id = created.id

    async with Session() as session:
        foreign = AssistantSessionRepository(session, OTHER_USER)
        assert await foreign.get(session_id) is None
        assert await foreign.lock(session_id) is None


@pytest.mark.usefixtures("two_users")
async def test_list_is_newest_first_and_own_only() -> None:
    """The novel's list is this user's sessions, newest first, and no others."""
    novel = await _seed_novel()
    other_novel = await _seed_novel(title="Another Book")
    foreign_novel = await _seed_novel(OTHER_USER, "The Stranger's Book")

    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        older = await repo.create(novel.id, MODE, "character", None)
        older.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        newer = await repo.create(novel.id, MODE, "location", None)
        newer.created_at = datetime(2026, 1, 2, tzinfo=UTC)
        await repo.create(other_novel.id, MODE, "object", None)
        await AssistantSessionRepository(session, OTHER_USER).create(
            foreign_novel.id, MODE, "faction", None
        )
        await session.commit()

    async with Session() as session:
        rows = await AssistantSessionRepository(session, LOCAL_USER_ID).list_for_novel(novel.id)
        assert [row.id for row in rows] == [newer.id, older.id]
        assert all(row.user_id == LOCAL_USER_ID for row in rows)
        assert all(row.novel_id == novel.id for row in rows)


@pytest.mark.usefixtures("two_users")
async def test_last_turns_returns_the_newest_oldest_first() -> None:
    """The model sees the most recent turns, still in reading order."""
    novel = await _seed_novel()
    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        created = await repo.create(novel.id, MODE, "character", None)
        for seq in range(1, 6):
            await repo.append_turn(created.id, seq, "user", f"turn {seq}")
        await session.commit()
        session_id = created.id

    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        turns = await repo.last_turns(session_id, 3)
        assert [turn.seq for turn in turns] == [3, 4, 5]
        assert [turn.text for turn in turns] == ["turn 3", "turn 4", "turn 5"]
        assert await AssistantSessionRepository(session, OTHER_USER).last_turns(session_id, 3) == []


@pytest.mark.usefixtures("two_users")
async def test_seq_is_unique_per_session() -> None:
    """A seq can be used once per session, and the same seq may repeat across them."""
    novel = await _seed_novel()
    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        first = await repo.create(novel.id, MODE, "character", None)
        second = await repo.create(novel.id, MODE, "character", None)
        await session.commit()
        first_id, second_id = first.id, second.id

        await repo.append_turn(first_id, 1, "user", "one")
        await session.commit()
        assert await repo.next_seq(first_id) == 2
        assert await repo.next_seq(second_id) == 1

        with pytest.raises(IntegrityError):
            await repo.append_turn(first_id, 1, "assistant", "again")
        await session.rollback()

        await repo.append_turn(second_id, 1, "user", "first in its own session")
        await session.commit()

    async with Session() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(AssistantTurn)
            .where(AssistantTurn.session_id == first_id)
        )
        assert count == 1


@pytest.mark.usefixtures("two_users")
async def test_closing_a_novel_deletes_its_sessions() -> None:
    """The novel's cascade reaches the session and the turn below it."""
    novel = await _seed_novel()
    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        created = await repo.create(novel.id, MODE, "character", None)
        await repo.append_turn(created.id, 1, "user", "hello")
        await session.commit()

    async with Session() as session:
        await session.execute(delete(Novel).where(Novel.id == novel.id))
        await session.commit()

    async with Session() as session:
        sessions = await session.scalar(select(func.count()).select_from(AssistantSession))
        turns = await session.scalar(select(func.count()).select_from(AssistantTurn))
        assert sessions == 0
        assert turns == 0


@pytest.mark.usefixtures("two_users")
async def test_roster_lists_only_the_novel() -> None:
    """The roster is the novel's entities, name-ordered, with only the four fields."""
    novel = await _seed_novel()
    other_novel = await _seed_novel(title="Another Book")
    foreign_novel = await _seed_novel(OTHER_USER, "The Stranger's Book")
    await _seed_entities(novel, ("Zara", "Aya", "Mira"))
    await _seed_entities(other_novel, ("Bea",))
    await _seed_entities(foreign_novel, ("Cora",))

    async with Session() as session:
        rows = await EntityRosterRepository(session, LOCAL_USER_ID).names_for_novel(novel.id)
        assert [row.name for row in rows] == ["Aya", "Mira", "Zara"]
        for row in rows:
            assert row.id is not None
            assert row.type == "character"
            assert row.aliases == [row.name[:1]]
            # The roster query loads the four fields and nothing else.
            assert "content" not in row.__dict__

        limited = await EntityRosterRepository(session, LOCAL_USER_ID).names_for_novel(
            novel.id, limit=2
        )
        assert [row.name for row in limited] == ["Aya", "Mira"]

        novel_repo = NovelRepository(session, LOCAL_USER_ID)
        assert await novel_repo.exists(novel.id) is True
        assert await novel_repo.exists(foreign_novel.id) is False
        assert await novel_repo.heading(novel.id) == ("The Lighthouse", None)
