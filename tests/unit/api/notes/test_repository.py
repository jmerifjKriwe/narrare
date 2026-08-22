"""Unit tests for ``NoteRepository`` query wiring (fake session).

Mirrors ``tests/unit/api/novels/test_novel_repository.py``: the repository is
a thin SQLAlchemy wrapper — these tests exercise each method's query/return
path and the create/update/delete bookkeeping (flush+refresh, setattr loop,
session.delete) without a real database. Filter semantics (ILIKE, tag
containment, DISTINCT unnest) are proven at integration level; the fake
session only carries results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import uuid4

from narrare.notes.repository import NoteRepository
from tests.factories import make_note
from tests.fakes.fake_db_session import FakeDbSession, FakeResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _make_repo(session: FakeDbSession) -> NoteRepository:
    """Wrap a fake session in a repository.

    ``cast`` (not ``# type: ignore[arg-type]``) is the RULE-23-sanctioned
    seam for passing a fake where an ``AsyncSession`` is declared.
    """
    return NoteRepository(cast("AsyncSession", session))


class TestNoteRepositoryGetById:
    async def test_get_by_id_returns_note_when_found(self) -> None:
        """get_by_id() returns the note scoped to (note_id, user_id)."""
        note = make_note()
        repo = _make_repo(FakeDbSession([FakeResult(value=note)]))

        result = await repo.get_by_id(note.id, note.user_id)

        assert result is note

    async def test_get_by_id_returns_none_when_missing(self) -> None:
        """get_by_id() returns None when the query yields no row."""
        repo = _make_repo(FakeDbSession([FakeResult(value=None)]))

        result = await repo.get_by_id(uuid4(), uuid4())

        assert result is None


class TestNoteRepositoryGetManyByIds:
    async def test_get_many_by_ids_returns_scalar_list(self) -> None:
        """get_many_by_ids() returns the scalars() result as a list."""
        notes = [make_note(), make_note()]
        repo = _make_repo(FakeDbSession([FakeResult(scalars=notes)]))

        result = await repo.get_many_by_ids({note.id for note in notes}, notes[0].user_id)

        assert result == notes

    async def test_get_many_by_ids_with_empty_set_returns_empty(self) -> None:
        """An empty id set short-circuits to [] without a query."""
        repo = _make_repo(FakeDbSession())

        result = await repo.get_many_by_ids(set(), uuid4())

        assert result == []


class TestNoteRepositoryListNotes:
    async def test_list_notes_returns_scalar_list(self) -> None:
        """list_notes() returns the scalars() result as a list."""
        notes = [make_note(), make_note()]
        repo = _make_repo(FakeDbSession([FakeResult(scalars=notes)]))

        result = await repo.list_notes(notes[0].user_id)

        assert result == notes


class TestNoteRepositoryDistinctTags:
    async def test_distinct_tags_returns_string_list(self) -> None:
        """distinct_tags() returns the distinct tags as plain strings."""
        repo = _make_repo(FakeDbSession([FakeResult(scalars=["alpha", "beta"])]))

        result = await repo.distinct_tags(uuid4())

        assert result == ["alpha", "beta"]

    async def test_distinct_tags_with_prefix_filter(self) -> None:
        """distinct_tags(q=...) passes the prefix through and returns the rows."""
        repo = _make_repo(FakeDbSession([FakeResult(scalars=["plot"])]))

        result = await repo.distinct_tags(uuid4(), q="pl")

        assert result == ["plot"]


class TestNoteRepositoryCreate:
    async def test_create_builds_note_and_flushes(self) -> None:
        """create() constructs a Note from the arguments and flushes it."""
        session = FakeDbSession()
        repo = _make_repo(session)
        user_id = uuid4()

        note = await repo.create(
            user_id,
            title=None,
            content="body",
            note_type="idea",
            tags=["plot"],
            novel_id=None,
            series_id=None,
        )

        assert note.user_id == user_id
        assert note.content == "body"
        assert note.note_type == "idea"
        assert note.tags == ["plot"]
        assert session.added == [note]
        assert session.flush_count == 1
        assert note in session.refreshed


class TestNoteRepositoryUpdate:
    async def test_update_sets_patched_fields(self) -> None:
        """update() applies every patch field and flushes."""
        note = make_note()
        session = FakeDbSession()
        repo = _make_repo(session)

        updated = await repo.update(note, content="new body", tags=["x"])

        assert updated is note
        assert updated.content == "new body"
        assert updated.tags == ["x"]
        assert session.flush_count == 1


class TestNoteRepositoryDelete:
    async def test_delete_delegates_to_session_and_flushes(self) -> None:
        """delete() removes the note via the session and flushes once."""
        note = make_note()
        session = FakeDbSession()
        repo = _make_repo(session)

        await repo.delete(note)

        assert session.deleted == [note]
        assert session.flush_count == 1
