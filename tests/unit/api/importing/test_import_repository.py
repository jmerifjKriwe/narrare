"""Unit tests for ImportChapterRepository — query wiring (FakeDbSession, no DB).

Covers the RULE-10 test-existence gate for ``importing/repository.py``:
``max_position`` aggregate handling (including the ``value or -1`` bug guard)
and the ``append_chapters`` bulk build (field mapping, sequential positions,
add_all + single flush).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast

from narrare.importing.repository import ImportChapterRepository
from narrare_core.importing.models import DetectedChapter
from tests.fakes.fake_db_session import FakeDbSession, FakeResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _repo(session: FakeDbSession) -> ImportChapterRepository:
    return ImportChapterRepository(cast("AsyncSession", session))


def _detected(title: str, content: str) -> DetectedChapter:
    return DetectedChapter(
        title=title,
        content=content,
        word_count=len(content.split()),
        status="draft",
        source_file="a.md",
    )


class TestMaxPosition:
    async def test_max_position_when_no_chapters_returns_minus_one(self) -> None:
        # scalar_one_or_none() over an empty aggregate → None → -1 sentinel.
        session = FakeDbSession(results=[FakeResult(value=None)])
        novel_id = uuid.uuid4()
        assert await _repo(session).max_position(novel_id) == -1
        # One aggregate SELECT scoped to the novel — no ORM entity loads.
        assert len(session.statements) == 1
        compiled = str(session.statements[0])
        assert "max(chapters.position)" in compiled
        assert "chapters.novel_id" in compiled

    async def test_max_position_when_max_is_zero_returns_zero(self) -> None:
        # Regression guard for the `value or -1` trap: a legitimate max of 0
        # (a chapter positioned at 0 exists) must NOT be conflated with the
        # "no chapters" sentinel — appending must start at 1, not 0.
        session = FakeDbSession(results=[FakeResult(value=0)])
        assert await _repo(session).max_position(uuid.uuid4()) == 0

    async def test_max_position_when_max_positive_returns_value(self) -> None:
        session = FakeDbSession(results=[FakeResult(value=4)])
        assert await _repo(session).max_position(uuid.uuid4()) == 4


class TestAppendChapters:
    async def test_append_chapters_maps_fields_and_assigns_sequential_positions(
        self,
    ) -> None:
        session = FakeDbSession()
        novel_id = uuid.uuid4()
        detected = [
            _detected("One", "first body"),
            _detected("Two", "second body"),
            _detected("Three", "third body"),
        ]

        rows = await _repo(session).append_chapters(novel_id, detected, start_position=5)

        # Sequential positions from start_position, in input order.
        assert [r.position for r in rows] == [5, 6, 7]
        # DetectedChapter fields mapped onto the Chapter columns.
        assert [r.title for r in rows] == ["One", "Two", "Three"]
        assert [r.content for r in rows] == ["first body", "second body", "third body"]
        assert [r.word_count for r in rows] == [2, 2, 2]
        assert [r.status for r in rows] == ["draft", "draft", "draft"]
        assert all(r.novel_id == novel_id for r in rows)
        # All rows handed to the session in ONE add_all, ONE flush — the
        # atomicity contract; and pure append: no SELECT executed.
        assert session.added == rows
        assert session.flush_count == 1
        assert session.statements == []

    async def test_append_chapters_when_no_chapters_adds_nothing(self) -> None:
        session = FakeDbSession()
        rows = await _repo(session).append_chapters(uuid.uuid4(), [], start_position=5)
        assert rows == []
        assert session.added == []
        assert session.flush_count == 1
