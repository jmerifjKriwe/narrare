"""Unit tests for the notes DI wiring (NOTES-001 Task 8).

Covers the module-private ``OwnedLinkLookupProtocol`` adapters and the
``get_note_service`` production factory. In particular it pins the T7-review
invariant: BOTH link lookups are always wired (never ``None``) —
``NoteService._validate_link`` fails open on a missing lookup, so a forgotten
lookup would silently skip ownership validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from narrare.embeddings.service import EmbeddingService
from narrare.notes.dependencies import (
    _NovelOwnedLookup,  # pyright: ignore[reportPrivateUsage] — wiring is the unit under test
    _SeriesOwnedLookup,  # pyright: ignore[reportPrivateUsage] — wiring is the unit under test
    get_note_service,
)
from narrare.notes.embedding_dispatch import InProcessNoteEmbeddingDispatch
from narrare.notes.service import NoteService
from narrare_core.series.schemas import Series
from tests.fakes.fake_db_session import FakeDbSession

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.novels.repository import NovelRepository
    from narrare.series.repository import SeriesRepository


def _make_series(owner: UUID) -> Series:
    """A core Series row owned by ``owner`` (what SeriesRepository.get returns)."""
    return Series(id=uuid4(), user_id=owner, title="A series")


class _StubNovelRepo:
    """Structurally matches ``NovelRepository.get_by_id`` (ownership-filtered)."""

    def __init__(self, row: object | None) -> None:
        self.row = row
        self.calls: list[tuple[UUID, UUID]] = []

    async def get_by_id(self, novel_id: UUID, user_id: UUID) -> object | None:
        self.calls.append((novel_id, user_id))
        return self.row


class _StubSeriesRepo:
    """Structurally matches ``SeriesRepository.get`` — NO ownership check."""

    def __init__(self, row: Series | None) -> None:
        self.row = row

    async def get(self, series_id: UUID) -> Series | None:
        return self.row


class TestNovelOwnedLookup:
    async def test_delegates_to_repository_with_user_scope(self) -> None:
        """The novel adapter is pure delegation — get_by_id already filters by user."""
        novel = object()
        stub = _StubNovelRepo(novel)
        lookup = _NovelOwnedLookup(cast("NovelRepository", stub))
        novel_id, user_id = uuid4(), uuid4()

        assert await lookup.get_owned(novel_id, user_id) is novel
        assert stub.calls == [(novel_id, user_id)]

    async def test_returns_none_when_repository_finds_nothing(self) -> None:
        stub = _StubNovelRepo(None)
        lookup = _NovelOwnedLookup(cast("NovelRepository", stub))

        assert await lookup.get_owned(uuid4(), uuid4()) is None


class TestSeriesOwnedLookup:
    async def test_returns_series_when_user_owns_it(self) -> None:
        owner = uuid4()
        series = _make_series(owner)
        lookup = _SeriesOwnedLookup(cast("SeriesRepository", _StubSeriesRepo(series)))

        assert await lookup.get_owned(series.id, owner) is series

    async def test_returns_none_when_series_belongs_to_other_user(self) -> None:
        """``SeriesRepository.get`` has no user check — the adapter must enforce it."""
        series = _make_series(uuid4())
        lookup = _SeriesOwnedLookup(cast("SeriesRepository", _StubSeriesRepo(series)))

        assert await lookup.get_owned(series.id, uuid4()) is None

    async def test_returns_none_when_series_missing(self) -> None:
        lookup = _SeriesOwnedLookup(cast("SeriesRepository", _StubSeriesRepo(None)))

        assert await lookup.get_owned(uuid4(), uuid4()) is None


class TestGetNoteService:
    def test_wires_all_collaborators_including_both_lookups(self) -> None:
        """T7 review invariant: BOTH lookups always wired — never ``None``.

        ``NoteService`` exposes no public accessors for its collaborators, so
        the wiring test asserts on the construction attributes directly (the
        fail-open-on-None service semantics make a missing lookup a silent
        ownership gap — this is the regression pin).
        """
        service = get_note_service(cast("AsyncSession", FakeDbSession()))

        assert isinstance(service, NoteService)
        assert isinstance(
            service._novel_lookup,  # pyright: ignore[reportPrivateUsage] — see docstring
            _NovelOwnedLookup,
        )
        assert isinstance(
            service._series_lookup,  # pyright: ignore[reportPrivateUsage] — see docstring
            _SeriesOwnedLookup,
        )
        assert isinstance(
            service._embedding_dispatch,  # pyright: ignore[reportPrivateUsage] — see docstring
            InProcessNoteEmbeddingDispatch,
        )
        assert isinstance(
            service._embedding_cleanup,  # pyright: ignore[reportPrivateUsage] — see docstring
            EmbeddingService,
        )
