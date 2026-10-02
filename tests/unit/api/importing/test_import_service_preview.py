"""Unit tests for ImportService.preview guard pipeline (no DB, no HTTP)."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, cast

from fastapi import UploadFile
from starlette.datastructures import Headers

from narrare.importing.constants import MAX_FILES
from narrare.importing.service import ImportService
from narrare_core.shared.errors import ValidationError
from tests.fakes.fake_db_session import FakeDbSession
from tests.fakes.fake_novel_repo import FakeNovelRepository

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.chapters.models import Chapter
    from narrare_core.importing.models import DetectedChapter


def _upload(name: str, data: bytes) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(data),
        size=len(data),
        filename=name,
        headers=Headers({"content-type": "application/octet-stream"}),
    )


class _UnusedChapterRepo:
    """Satisfies ImportChapterRepositoryProtocol — preview must never call it."""

    async def max_position(self, novel_id: uuid.UUID) -> int:
        raise AssertionError("preview must not query chapter positions")

    async def append_chapters(
        self,
        novel_id: uuid.UUID,
        chapters: Sequence[DetectedChapter],
        start_position: int,
    ) -> list[Chapter]:
        raise AssertionError("preview must not append chapters")


def _service() -> ImportService:
    # Preview touches no collaborators — canonical fakes satisfy the required
    # constructor types; the fake chapter repo fails the test if ever reached.
    return ImportService(
        session=cast("AsyncSession", FakeDbSession()),
        chapter_repo=_UnusedChapterRepo(),
        novel_repo=FakeNovelRepository(),
    )


class TestPreviewGuards:
    async def test_preview_with_empty_file_list_raises_422(self) -> None:
        try:
            await _service().preview([])
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "No files" in str(exc)

    async def test_preview_with_too_many_files_raises_422(self) -> None:
        files = [_upload(f"f{i}.md", b"# H\nbody") for i in range(MAX_FILES + 1)]
        try:
            await _service().preview(files)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "Too many files" in str(exc)

    async def test_preview_with_oversize_file_raises_422(self) -> None:
        big = _upload("big.md", b"x" * (5 * 1024 * 1024 + 1))
        try:
            await _service().preview([big])
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "big.md" in str(exc)

    async def test_preview_with_unsupported_extension_raises_422(self) -> None:
        try:
            await _service().preview([_upload("ch.docx", b"pk\x03\x04")])
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "ch.docx" in str(exc)

    async def test_preview_with_latin1_bytes_raises_422_naming_file(self) -> None:
        try:
            await _service().preview([_upload("bad.md", "café".encode("latin-1"))])
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "bad.md" in str(exc)
            assert "UTF-8" in str(exc)

    async def test_preview_with_zero_chapters_raises_422(self) -> None:
        try:
            await _service().preview([_upload("empty.md", b"   \n")])
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "No chapters" in str(exc)

    async def test_preview_over_total_limit_raises_422_naming_total(self) -> None:
        # 5 x 5 MiB fill the 25 MiB aggregate budget exactly; the 6th file tips
        # the SUM over the aggregate guard while each single file still passes
        # the per-file guard — proves the aggregate check, not the per-file one.
        five_mib = 5 * 1024 * 1024
        files = [_upload(f"{i}.md", b"# H\n" + b"x" * (five_mib - 4)) for i in range(5)]
        files.append(_upload("tip.md", b"# H\nx"))
        try:
            await _service().preview(files)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "total" in str(exc)

    async def test_preview_with_exactly_total_limit_bytes_passes_size_guard(self) -> None:
        # Boundary: 5 x 5 MiB = 25 MiB aggregate is allowed (guard is strict
        # `>`); content is valid markdown so nothing downstream rejects it.
        five_mib = 5 * 1024 * 1024
        files = [_upload(f"{i}.md", b"# Heading\n" + b"x" * (five_mib - 10)) for i in range(5)]
        result = await _service().preview(files)
        assert result.file_count == 5
        assert result.chapter_count == 5


class TestPreviewHappyPath:
    async def test_preview_returns_indexed_items_across_files(self) -> None:
        result = await _service().preview(
            [
                _upload("b.md", b"# Second\nbody two words here"),
                _upload("a.md", b"# First\none two"),
            ]
        )
        assert result.file_count == 2
        assert result.chapter_count == 2
        # Order = multipart part order (client sorts; server does not re-order)
        assert [i.suggested_title for i in result.items] == ["Second", "First"]
        assert result.items[0].index == 0
        assert result.items[0].source_file == "b.md"
        # 4 words ("body two words here") + 2 words ("one two") — the detector
        # counts body words only (heading line excluded).
        assert result.total_word_count == 6

    async def test_preview_is_idempotent(self) -> None:
        # Same bytes via fresh UploadFile streams: UploadFile is a one-shot
        # stream (read() consumes it), so idempotency = re-parsing identical
        # input yields an identical response; preview keeps no state.
        files = [_upload("a.md", b"# T\nbody")]
        assert await _service().preview(files) == await _service().preview(
            [_upload("a.md", b"# T\nbody")]
        )
