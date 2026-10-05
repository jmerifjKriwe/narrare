"""ChapterReader (start-path validation) unit tests (F2 T3, ADR-092 §4.6).

The reader is the real ``BulkChapterReader`` implementation backing
``service.start``: duplicates/cap/membership/non-empty-content all fail
as 422 (``narrare_core`` ``ValidationError``) naming the offending id,
and the returned refs are in chapter-position order.

DB-free by construction: the canonical ``FakeChapterRepository`` is
seeded with detached ``Chapter`` rows (no session, no server).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from narrare.chapters.models import Chapter
from narrare.kb.bulk_extraction.contracts import (
    BULK_EXTRACT_MAX_CHAPTERS,
    BulkChapterReader,
)
from narrare.kb.bulk_extraction.reader import ChapterReader
from narrare_core.shared.errors import ValidationError
from tests.fakes.fake_chapter_repo import FakeChapterRepository

NOVEL_ID = uuid4()
OTHER_NOVEL_ID = uuid4()


def _chapter(
    chapter_id: UUID | None = None,
    position: int = 0,
    *,
    content: str = "<p>body text</p>",
    title: str = "Storm",
    novel_id: UUID = NOVEL_ID,
) -> Chapter:
    return Chapter(
        id=chapter_id or uuid4(),
        novel_id=novel_id,
        title=title,
        content=content,
        position=position,
    )


def _reader(*chapters: Chapter) -> tuple[ChapterReader, FakeChapterRepository]:
    repo = FakeChapterRepository()
    repo.seed(*chapters)
    return ChapterReader(chapter_repo=repo), repo


class TestProtocolConformance:
    def test_reader_satisfies_the_bulk_chapter_reader_protocol(self) -> None:
        reader, _repo = _reader()
        assert isinstance(reader, BulkChapterReader)


class TestHappyPath:
    async def test_returns_refs_in_position_order_with_row_data(self) -> None:
        requested = [uuid4() for _ in range(3)]
        reader, _repo = _reader(
            _chapter(requested[0], 5, title="Coda"),
            _chapter(requested[1], 1, title="Aftermath"),
            _chapter(requested[2], 3, title="Storm"),
        )

        refs = await reader.load(NOVEL_ID, requested)

        assert [(ref.chapter_id, ref.title, ref.position) for ref in refs] == [
            (requested[1], "Aftermath", 1),
            (requested[2], "Storm", 3),
            (requested[0], "Coda", 5),
        ]

    async def test_request_order_does_not_matter(self) -> None:
        requested = [uuid4() for _ in range(2)]
        reader, _repo = _reader(_chapter(requested[0], 9), _chapter(requested[1], 2))

        refs = await reader.load(NOVEL_ID, list(reversed(requested)))

        assert [ref.position for ref in refs] == [2, 9]


class TestValidation:
    async def test_empty_request_rejected(self) -> None:
        reader, _repo = _reader()

        with pytest.raises(ValidationError, match="must not be empty"):
            await reader.load(NOVEL_ID, [])

    async def test_unknown_id_rejected_naming_it(self) -> None:
        stranger = uuid4()
        known = uuid4()
        reader, _repo = _reader(_chapter(known, 0))

        with pytest.raises(ValidationError, match=str(stranger)):
            await reader.load(NOVEL_ID, [known, stranger])

    async def test_chapter_of_another_novel_is_rejected_like_unknown(self) -> None:
        foreign = uuid4()
        reader, _repo = _reader(_chapter(foreign, 0, novel_id=OTHER_NOVEL_ID))

        with pytest.raises(ValidationError, match=str(foreign)):
            await reader.load(NOVEL_ID, [foreign])

    async def test_duplicate_request_ids_rejected_naming_the_id(self) -> None:
        duplicated = uuid4()
        reader, _repo = _reader(_chapter(duplicated, 0))

        with pytest.raises(ValidationError, match=str(duplicated)):
            await reader.load(NOVEL_ID, [duplicated, duplicated])

    async def test_over_cap_rejected_naming_the_cap(self) -> None:
        reader, _repo = _reader()

        with pytest.raises(ValidationError, match=str(BULK_EXTRACT_MAX_CHAPTERS)):
            await reader.load(NOVEL_ID, [uuid4() for _ in range(BULK_EXTRACT_MAX_CHAPTERS + 1)])

    @pytest.mark.parametrize("content", ["", "   "])
    async def test_empty_content_rejected_naming_the_id(self, content: str) -> None:
        empty = uuid4()
        full = uuid4()
        reader, _repo = _reader(_chapter(empty, 0, content=content), _chapter(full, 1))

        with pytest.raises(ValidationError, match=str(empty)):
            await reader.load(NOVEL_ID, [empty, full])


class TestCheckOrder:
    async def test_duplicate_check_reports_before_membership(self) -> None:
        duplicated = uuid4()
        reader, _repo = _reader()  # empty novel — membership would also fail

        with pytest.raises(ValidationError, match=r"[Dd]uplicate"):
            await reader.load(NOVEL_ID, [duplicated, duplicated])

    async def test_membership_reports_before_content(self) -> None:
        empty = uuid4()
        stranger = uuid4()
        reader, _repo = _reader(_chapter(empty, 0, content=""))

        with pytest.raises(ValidationError, match=str(stranger)):
            await reader.load(NOVEL_ID, [empty, stranger])
