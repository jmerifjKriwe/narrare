"""Unit tests for ImportService.commit — adjustment validation (fakes, no DB)."""

from __future__ import annotations

import io
import uuid
from typing import TYPE_CHECKING, cast

from fastapi import UploadFile
from starlette.datastructures import Headers

from narrare.chapters.models import Chapter
from narrare.importing.schemas import ImportCommitAdjustments
from narrare.importing.service import ImportService
from narrare.novels.models import Novel
from narrare_core.shared.errors import ValidationError
from tests.fakes.fake_db_session import FakeDbSession
from tests.fakes.fake_novel_repo import FakeNovelRepository

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare_core.importing.models import DetectedChapter

NOVEL_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _upload(name: str, data: bytes) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(data),
        size=len(data),
        filename=name,
        headers=Headers({"content-type": "application/octet-stream"}),
    )


class _FakeChapterRepo:
    """Structurally satisfies ImportChapterRepositoryProtocol — records appends."""

    def __init__(self) -> None:
        self.appended: list[DetectedChapter] = []
        self.start_position = -1

    async def max_position(self, novel_id: uuid.UUID) -> int:
        return 4  # novel already has chapters at positions 0..4

    async def append_chapters(
        self,
        novel_id: uuid.UUID,
        chapters: Sequence[DetectedChapter],
        start_position: int,
    ) -> list[Chapter]:
        self.appended = list(chapters)
        self.start_position = start_position
        # Mirror the real repository contract: the caller reports these rows
        # back in the response (created_count/positions), so return real rows.
        return [
            Chapter(
                novel_id=novel_id,
                title=chapter.title,
                content=chapter.content,
                position=start_position + offset,
                word_count=chapter.word_count,
                status=chapter.status,
            )
            for offset, chapter in enumerate(chapters)
        ]


def _service() -> tuple[ImportService, _FakeChapterRepo]:
    repo = _FakeChapterRepo()
    novel_repo = FakeNovelRepository()
    novel_repo.seed(Novel(id=NOVEL_ID, user_id=USER_ID, title="Import Target"))
    return (
        ImportService(
            session=cast("AsyncSession", FakeDbSession()),  # commit never touches the session
            chapter_repo=repo,
            novel_repo=novel_repo,
        ),
        repo,
    )


def _files() -> list[UploadFile]:
    # Fresh streams per call — UploadFile.read() consumes its buffer, so a
    # shared module-level constant would leak empty files between tests.
    return [
        _upload("a.md", b"# One\nbody one"),
        _upload("b.md", b"# Two\nbody two"),
    ]


class TestCommitValidation:
    async def test_out_of_range_excluded_index_raises_422(self) -> None:
        service, _ = _service()
        try:
            await service.commit(
                _files(),
                NOVEL_ID,
                USER_ID,
                ImportCommitAdjustments(excluded_indices=[5]),
            )
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "5" in str(exc)

    async def test_out_of_range_title_override_key_raises_422(self) -> None:
        service, _ = _service()
        try:
            await service.commit(
                _files(),
                NOVEL_ID,
                USER_ID,
                ImportCommitAdjustments(title_overrides={"9": "X"}),
            )
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "9" in str(exc)

    async def test_non_decimal_unicode_override_key_raises_422(self) -> None:
        # "①".isdigit() is True but int("①") raises — the guard must use
        # isdecimal() so digit-like Unicode is rejected as a 422, not a 500.
        service, _ = _service()
        try:
            await service.commit(
                _files(),
                NOVEL_ID,
                USER_ID,
                ImportCommitAdjustments(title_overrides={"①": "X"}),
            )
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "①" in str(exc)

    async def test_overlong_title_override_raises_422(self) -> None:
        service, _ = _service()
        try:
            await service.commit(
                _files(),
                NOVEL_ID,
                USER_ID,
                ImportCommitAdjustments(title_overrides={"0": "x" * 501}),
            )
            raise AssertionError("expected ValidationError")
        except ValidationError:
            pass

    async def test_empty_title_override_raises_422(self) -> None:
        service, _ = _service()
        try:
            await service.commit(
                _files(),
                NOVEL_ID,
                USER_ID,
                ImportCommitAdjustments(title_overrides={"0": "  "}),
            )
            raise AssertionError("expected ValidationError")
        except ValidationError:
            pass


class TestCommitAppend:
    async def test_exclusion_rename_and_positions(self) -> None:
        service, repo = _service()
        result = await service.commit(
            _files(),
            NOVEL_ID,
            USER_ID,
            ImportCommitAdjustments(excluded_indices=[1], title_overrides={"0": "Renamed"}),
        )
        assert result.created_count == 1
        assert [c.title for c in repo.appended] == ["Renamed"]
        assert repo.start_position == 5  # max_position 4 + 1
        assert result.first_position == 5 and result.last_position == 5
