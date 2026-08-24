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

from narrare.notes.contracts import NoteRepositoryProtocol
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


def _filter_binds(session: FakeDbSession) -> dict[str, object]:
    """Filter-related bound params of the first executed statement.

    Excludes non-filter binds (user_id scope, limit/offset paging) so each
    per-filter test asserts exactly its own bind(s) — a dropped or mis-wired
    condition changes the dict and fails the test.
    """
    prefixes = ("note_type", "tags", "novel_id", "series_id", "title", "content")
    params = session.statements[0].compile().params
    return {key: value for key, value in params.items() if key.startswith(prefixes)}


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

    async def test_list_notes_escapes_like_wildcards_in_q(self) -> None:
        """User input in q must match literally: % and _ are escaped (T6 review)."""
        session = FakeDbSession()
        repo = _make_repo(session)

        await repo.list_notes(uuid4(), q="100%_done")

        params = session.statements[0].compile().params
        assert any("100\\%\\_done" in str(value) for value in params.values())


class TestNoteRepositoryListNotesFilters:
    """Per-filter bind-param assertions (test-depth batch, final review).

    Filter SQL semantics (ILIKE, tag containment) are proven at integration
    level; these tests pin the WIRING — each filter binds its value under
    its column's param, so a dropped or mis-wired condition fails here
    instead of surfacing at e2e time.
    """

    async def test_note_type_filter_binds_value(self) -> None:
        session = FakeDbSession()
        repo = _make_repo(session)

        await repo.list_notes(uuid4(), note_type="idea")

        assert _filter_binds(session) == {"note_type_1": "idea"}

    async def test_tag_filter_binds_containment_array(self) -> None:
        """The tag filter binds an ARRAY containment param, not a scalar."""
        session = FakeDbSession()
        repo = _make_repo(session)

        await repo.list_notes(uuid4(), tag="plot")

        assert _filter_binds(session) == {"tags_1": ["plot"]}

    async def test_novel_id_filter_binds_value(self) -> None:
        session = FakeDbSession()
        repo = _make_repo(session)
        novel_id = uuid4()

        await repo.list_notes(uuid4(), novel_id=novel_id)

        assert _filter_binds(session) == {"novel_id_1": novel_id}

    async def test_series_id_filter_binds_value(self) -> None:
        session = FakeDbSession()
        repo = _make_repo(session)
        series_id = uuid4()

        await repo.list_notes(uuid4(), series_id=series_id)

        assert _filter_binds(session) == {"series_id_1": series_id}

    async def test_q_filter_binds_ilike_pattern_on_title_and_content(self) -> None:
        """q wraps the input in %...% and binds it for BOTH title and content."""
        session = FakeDbSession()
        repo = _make_repo(session)

        await repo.list_notes(uuid4(), q="needle")

        assert _filter_binds(session) == {"title_1": "%needle%", "content_1": "%needle%"}


class TestNoteRepositoryProtocolConformance:
    def test_repository_satisfies_protocol(self) -> None:
        """Structural guard: NoteRepository carries the Protocol's surface.

        ``runtime_checkable`` ``issubclass`` checks method presence only —
        cheap rename protection (mirrors test_series_drift_repository.py).
        """
        assert issubclass(NoteRepository, NoteRepositoryProtocol)


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

    async def test_distinct_tags_escapes_like_wildcards_in_q(self) -> None:
        """Prefix filter input must match literally: % and _ are escaped (T6 review)."""
        session = FakeDbSession([FakeResult(scalars=[])])
        repo = _make_repo(session)

        await repo.distinct_tags(uuid4(), q="a%b_c")

        params = session.statements[0].compile().params
        assert any("a\\%b\\_c" in str(value) for value in params.values())


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
