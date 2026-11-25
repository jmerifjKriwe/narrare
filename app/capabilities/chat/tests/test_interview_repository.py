"""The interview's storage: sessions, turns, the roster and the novel's heading.

Two users prove the narrowing on every path — another user's session is absent,
not an error — and the database proves the two invariants the service above
leans on: one ``seq`` per session, and a deleted novel taking its sessions and
their turns with it.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, event, func, select
from sqlalchemy.exc import IntegrityError

from app.capabilities.chat.models import AssistantSession, AssistantTurn
from app.capabilities.chat.repository import (
    SESSION_LIST_LIMIT,
    AssistantSessionRepository,
    EntityRosterRepository,
    NovelRepository,
)
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Entity, Novel
from app.kernel.db.session import Session, engine
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
async def test_lock_returns_the_owned_row_for_update() -> None:
    """The lock hands back this user's row, and the write under it commits."""
    novel = await _seed_novel()
    async with Session() as session:
        created = await AssistantSessionRepository(session, LOCAL_USER_ID).create(
            novel.id, MODE, "character", None
        )
        await session.commit()
        session_id = created.id

    closed_at = datetime(2026, 2, 1, tzinfo=UTC)
    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        locked = await repo.lock(session_id)
        assert locked is not None
        assert locked.id == session_id
        # The row the lock returned is writable without a reload.
        locked.closed_at = closed_at
        await session.commit()

    async with Session() as session:
        reread = await AssistantSessionRepository(session, LOCAL_USER_ID).get(session_id)
        assert reread is not None
        assert reread.closed_at == closed_at


@pytest.mark.usefixtures("two_users")
async def test_set_suggestion_state_persists() -> None:
    """Settling a turn's suggestion writes the state the next read sees."""
    novel = await _seed_novel()
    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        created = await repo.create(novel.id, MODE, "character", None)
        await repo.append_turn(created.id, 1, "assistant", "A new character?", suggestion="Mira")
        await session.commit()
        session_id = created.id

    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        [pending] = await repo.last_turns(session_id, 10)
        assert pending.suggestion_state is None
        await repo.set_suggestion_state(pending, "accepted")
        await session.commit()

    async with Session() as session:
        [settled] = await AssistantSessionRepository(session, LOCAL_USER_ID).last_turns(
            session_id, 10
        )
        assert settled.suggestion_state == "accepted"


@pytest.mark.usefixtures("two_users")
async def test_list_is_newest_first_and_own_only() -> None:
    """The novel's list is this user's sessions; another user's row in the same novel is absent."""
    novel = await _seed_novel()
    other_novel = await _seed_novel(title="Another Book")

    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        older = await repo.create(novel.id, MODE, "character", None)
        older.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        newer = await repo.create(novel.id, MODE, "location", None)
        newer.created_at = datetime(2026, 1, 2, tzinfo=UTC)
        # The novel filter: this user's session in another novel.
        await repo.create(other_novel.id, MODE, "object", None)
        # The user predicate: a stranger's session in *this* novel, which the
        # novel filter alone would let through.
        await AssistantSessionRepository(session, OTHER_USER).create(
            novel.id, MODE, "faction", None
        )
        await session.commit()

    async with Session() as session:
        rows = await AssistantSessionRepository(session, LOCAL_USER_ID).list_for_novel(novel.id)
        assert [row.id for row in rows] == [newer.id, older.id]
        assert all(row.novel_id == novel.id for row in rows)
        assert all(row.name is None for row in rows)


@pytest.mark.usefixtures("two_users")
async def test_list_shows_the_open_sessions_before_the_closed_ones() -> None:
    """The list's order is the surface's: open first, closed after, newest first within each."""
    novel = await _seed_novel()
    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        oldest_open = await repo.create(novel.id, MODE, "character", None)
        oldest_open.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        newest_closed = await repo.create(novel.id, MODE, "location", None)
        newest_closed.created_at = datetime(2026, 1, 3, tzinfo=UTC)
        await repo.close(newest_closed)
        newer_open = await repo.create(novel.id, MODE, "object", None)
        newer_open.created_at = datetime(2026, 1, 2, tzinfo=UTC)
        await session.commit()
        open_ids = [newer_open.id, oldest_open.id]
        closed_id = newest_closed.id

    async with Session() as session:
        rows = await AssistantSessionRepository(session, LOCAL_USER_ID).list_for_novel(novel.id)

    # The door's «newest open» is the first row, though a closed session is newer.
    assert [row.id for row in rows] == [*open_ids, closed_id]
    assert [row.closed_at is None for row in rows] == [True, True, False]


@pytest.mark.usefixtures("two_users")
async def test_the_list_is_one_statement_so_a_close_cannot_duplicate_a_row() -> None:
    """The list is one ``UNION ALL`` statement: a close between two reads cannot duplicate a row.

    Under read-committed, two selects are two snapshots, so a session closed
    between them would match the open select and the closed one. The test reads
    the statement off the wire — one ``SELECT ... UNION ALL SELECT ...`` with a
    ``LIMIT`` on each side — rather than racing a closer against the query.
    """
    novel = await _seed_novel()
    async with Session() as session:
        session.add_all(
            AssistantSession(
                user_id=LOCAL_USER_ID,
                novel_id=novel.id,
                mode=MODE,
                entity_type="character",
            )
            for _ in range(2)
        )
        await session.commit()

    statements: list[str] = []

    def record(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        async with Session() as session:
            rows = await AssistantSessionRepository(session, LOCAL_USER_ID).list_for_novel(novel.id)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)

    assert len(rows) == 2
    assert len(statements) == 1
    assert statements[0].count("UNION ALL") == 1
    assert statements[0].count("LIMIT") == 2


@pytest.mark.usefixtures("two_users")
async def test_each_list_state_is_bounded_on_its_own() -> None:
    """A closed history beyond the bound cannot push an old open session off the list."""
    novel = await _seed_novel()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    async with Session() as session:
        session.add_all(
            AssistantSession(
                user_id=LOCAL_USER_ID,
                novel_id=novel.id,
                mode=MODE,
                entity_type="character",
                proposal={"name": f"Row {index}"},
                closed_at=base,
                created_at=base + timedelta(seconds=index + 1),
            )
            for index in range(SESSION_LIST_LIMIT + 1)
        )
        still_open = AssistantSession(
            user_id=LOCAL_USER_ID,
            novel_id=novel.id,
            mode=MODE,
            entity_type="location",
            proposal={"name": "Still open"},
            created_at=base,
        )
        session.add(still_open)
        await session.commit()
        open_id = still_open.id

    async with Session() as session:
        rows = await AssistantSessionRepository(session, LOCAL_USER_ID).list_for_novel(novel.id)

    assert len(rows) == SESSION_LIST_LIMIT + 1
    assert rows[0].id == open_id
    assert rows[0].name == "Still open"
    # The closed state is capped: its oldest row is dropped, its newest kept.
    assert rows[1].name == f"Row {SESSION_LIST_LIMIT}"
    assert all(row.name != "Row 0" for row in rows)


@pytest.mark.usefixtures("two_users")
async def test_list_reads_the_name_from_the_proposal_without_the_proposal() -> None:
    """A row carries the proposal's name; the draft itself is not in the row."""
    novel = await _seed_novel()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        named = await repo.create(novel.id, MODE, "character", None)
        named.created_at = base
        await repo.set_proposal(named, {"name": "Mira", "content": "Eine Wächterin am See."})
        unnamed = await repo.create(novel.id, MODE, "location", None)
        unnamed.created_at = base + timedelta(seconds=1)
        await session.commit()
        named_id, unnamed_id = named.id, unnamed.id

    async with Session() as session:
        rows = await AssistantSessionRepository(session, LOCAL_USER_ID).list_for_novel(novel.id)

    assert [(row.id, row.name) for row in rows] == [(unnamed_id, None), (named_id, "Mira")]
    assert not hasattr(rows[0], "proposal")


@pytest.mark.usefixtures("two_users")
async def test_list_returns_only_the_newest_bounded_rows() -> None:
    """More than the bound exists in one state: the list is the newest ``SESSION_LIST_LIMIT``."""
    novel = await _seed_novel()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    async with Session() as session:
        session.add_all(
            AssistantSession(
                user_id=LOCAL_USER_ID,
                novel_id=novel.id,
                mode=MODE,
                entity_type="character",
                proposal={"name": f"Row {index}"},
                created_at=base + timedelta(seconds=index),
            )
            for index in range(SESSION_LIST_LIMIT + 1)
        )
        await session.commit()

    async with Session() as session:
        rows = await AssistantSessionRepository(session, LOCAL_USER_ID).list_for_novel(novel.id)

    assert len(rows) == SESSION_LIST_LIMIT
    assert rows[0].name == f"Row {SESSION_LIST_LIMIT}"
    assert rows[-1].name == "Row 1"
    assert all(row.name != "Row 0" for row in rows)


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

        with pytest.raises(IntegrityError) as excinfo:
            await repo.append_turn(first_id, 1, "assistant", "again")
        assert "uq_assistant_turns_seq" in str(excinfo.value)
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
    other_novel = await _seed_novel(title="Another Book")
    async with Session() as session:
        repo = AssistantSessionRepository(session, LOCAL_USER_ID)
        created = await repo.create(novel.id, MODE, "character", None)
        await repo.append_turn(created.id, 1, "user", "hello")
        survivor = await repo.create(other_novel.id, MODE, "character", None)
        await repo.append_turn(survivor.id, 1, "user", "still here")
        await session.commit()
        session_id, survivor_id = created.id, survivor.id

    async with Session() as session:
        await session.execute(delete(Novel).where(Novel.id == novel.id))
        await session.commit()

    async with Session() as session:
        sessions = await session.scalar(
            select(func.count())
            .select_from(AssistantSession)
            .where(AssistantSession.novel_id == novel.id)
        )
        turns = await session.scalar(
            select(func.count())
            .select_from(AssistantTurn)
            .where(AssistantTurn.session_id == session_id)
        )
        assert sessions == 0
        assert turns == 0
        # The other novel's interview is untouched, so the zeros above mean
        # the cascade, not an empty table.
        assert await AssistantSessionRepository(session, LOCAL_USER_ID).get(survivor_id) is not None


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
        # Absent and foreign are one answer: the heading returns None.
        assert await novel_repo.heading(foreign_novel.id) is None
        assert await novel_repo.heading(uuid4()) is None
