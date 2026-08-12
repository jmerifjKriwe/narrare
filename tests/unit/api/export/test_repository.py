"""Unit tests for ``ExportRepository`` — read-only manuscript loading (RULE-22).

Uses an in-process fake session (the ``FakeResult`` / ``FakeSession`` pattern
from ``tests/unit/api/memory/test_repository.py``) so no real database is
needed. The fake returns canned ORM rows; the tests assert the repository
assembles them into a :class:`ManuscriptSource` correctly and never issues a
write (RULE-22: export never modifies the source).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select

from narrare.chapters.models import Chapter
from narrare.export.repository import ExportRepository
from narrare.novels.models import Novel


class _FakeResult:
    """Fake SQLAlchemy Result: ``scalar_one_or_none`` + iterable ``scalars()``.

    The repository calls ``list(result.scalars())`` for chapters, so
    ``scalars()`` returns the row list directly (lists are iterable, matching
    SQLAlchemy's ``Scalars`` iteration).
    """

    def __init__(self, *, one: Any | None = None, rows: list[Any] | None = None) -> None:
        self._one = one
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any | None:
        return self._one

    def scalars(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """Returns canned results in call order (novel query, then chapters query)."""

    def __init__(self, results: list[_FakeResult]) -> None:
        self._results = list(results)
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> _FakeResult:
        self.statements.append(stmt)
        return self._results.pop(0)


def _novel(
    novel_id: Any, *, title: str = "My Novel", author: str = "Author", language: str = "en"
) -> Novel:
    return Novel(id=novel_id, title=title, author=author, writing_language=language)


def _chapter(
    novel_id: Any,
    *,
    title: str,
    position: int,
    content: str,
    volume_id: Any | None = None,
) -> Chapter:
    return Chapter(
        id=uuid4(),
        novel_id=novel_id,
        title=title,
        content=content,
        position=position,
        volume_id=volume_id,
    )


class TestGetManuscriptSource:
    async def test_assembles_novel_and_chapters_in_position_order(self) -> None:
        novel_id = uuid4()
        ch1 = _chapter(novel_id, title="C1", position=0, content="<p>a</p>")
        ch2 = _chapter(novel_id, title="C2", position=1, content="<p>b</p>")
        session = _FakeSession(
            [
                _FakeResult(one=_novel(novel_id, title="My Novel", author="A", language="fr")),
                _FakeResult(rows=[ch1, ch2]),
            ]
        )
        repo = ExportRepository(session)  # type: ignore[arg-type]

        source = await repo.get_manuscript_source(novel_id)

        assert source is not None
        assert source.novel_id == novel_id
        assert source.title == "My Novel"
        assert source.author == "A"
        assert source.language == "fr"
        assert [c.title for c in source.chapters] == ["C1", "C2"]
        assert [c.content for c in source.chapters] == ["<p>a</p>", "<p>b</p>"]

    async def test_missing_novel_returns_none(self) -> None:
        session = _FakeSession([_FakeResult(one=None)])
        repo = ExportRepository(session)  # type: ignore[arg-type]

        assert await repo.get_manuscript_source(uuid4()) is None
        # Only the novel query ran (chapters query short-circuited).
        assert len(session.statements) == 1

    async def test_volume_filter_added_to_chapter_query(self) -> None:
        novel_id = uuid4()
        volume_id = uuid4()
        session = _FakeSession(
            [
                _FakeResult(one=_novel(novel_id)),
                _FakeResult(rows=[]),
            ]
        )
        repo = ExportRepository(session)  # type: ignore[arg-type]

        await repo.get_manuscript_source(novel_id, volume_id=volume_id)

        # The second statement (chapters) filters by volume_id.
        chapter_stmt = session.statements[1]
        compiled = str(chapter_stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "volume_id" in compiled

    async def test_chapters_ordered_by_position_in_query(self) -> None:
        novel_id = uuid4()
        session = _FakeSession([_FakeResult(one=_novel(novel_id)), _FakeResult(rows=[])])
        repo = ExportRepository(session)  # type: ignore[arg-type]

        await repo.get_manuscript_source(novel_id)

        chapter_stmt = session.statements[1]
        compiled = str(chapter_stmt.compile())
        assert "ORDER BY" in compiled
        assert "position" in compiled

    async def test_no_write_operations_issued(self) -> None:
        # RULE-22: export is read-only. Assert only SELECT statements ran.
        novel_id = uuid4()
        session = _FakeSession([_FakeResult(one=_novel(novel_id)), _FakeResult(rows=[])])
        repo = ExportRepository(session)  # type: ignore[arg-type]

        await repo.get_manuscript_source(novel_id)

        for stmt in session.statements:
            assert isinstance(stmt, select.__class__) or "Select" in type(stmt).__name__
