"""Import service — guard pipeline, parse orchestration, atomic append.

Preview is stateless (no DB writes). Commit re-parses deterministically and
appends chapters in the caller's request transaction (ADR-091).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from narrare.importing.constants import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
)
from narrare.importing.schemas import (
    ImportCommitChapterInfo,
    ImportCommitResponse,
    ImportPreviewItem,
    ImportPreviewResponse,
)
from narrare.novels.ownership import verify_novel_owned
from narrare_core.importing.detector import detect_chapters
from narrare_core.shared.errors import ValidationError

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from fastapi import UploadFile
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.importing.contracts import ImportChapterRepositoryProtocol
    from narrare.importing.schemas import ImportCommitAdjustments
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare_core.importing.models import DetectedChapter

logger = structlog.get_logger(__name__)


class ImportService:
    """Implements ImportServiceProtocol (contracts.py) implicitly."""

    def __init__(
        self,
        session: AsyncSession,
        chapter_repo: ImportChapterRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
    ) -> None:
        self._session = session
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo

    async def preview(self, files: Sequence[UploadFile]) -> ImportPreviewResponse:
        """Guard + parse uploads; NO DB writes (safe to repeat)."""
        texts = await self._read_and_validate(files)
        detected = self._detect_all(files, texts)
        if not detected:
            raise ValidationError("No chapters detected in the uploaded files.")
        items = [
            ImportPreviewItem(
                index=i,
                suggested_title=c.title,
                word_count=c.word_count,
                source_file=c.source_file,
            )
            for i, c in enumerate(detected)
        ]
        return ImportPreviewResponse(
            items=items,
            file_count=len(files),
            chapter_count=len(detected),
            total_word_count=sum(c.word_count for c in detected),
        )

    async def _read_and_validate(self, files: Sequence[UploadFile]) -> list[str]:
        """Guards 1-5 of spec §4.1, then decode utf-8-sig strict."""
        if not files:
            raise ValidationError("No files uploaded.")
        if len(files) > MAX_FILES:
            raise ValidationError(f"Too many files: {len(files)} (max {MAX_FILES}).")
        total = 0
        for upload in files:
            size = upload.size or 0
            if size > MAX_FILE_BYTES:
                raise ValidationError(f"File '{upload.filename}' exceeds the 5 MB per-file limit.")
            total += size
            if total > MAX_TOTAL_BYTES:
                raise ValidationError("Upload exceeds the 25 MB total size limit.")
            extension = Path(upload.filename or "").suffix.lower()
            if extension not in ALLOWED_EXTENSIONS:
                raise ValidationError(
                    f"File '{upload.filename}': unsupported type (allowed: .md, .txt)."
                )
        texts: list[str] = []
        for upload in files:
            raw = await upload.read()
            try:
                texts.append(raw.decode("utf-8-sig"))
            except UnicodeDecodeError as exc:
                raise ValidationError(f"File '{upload.filename}' is not valid UTF-8.") from exc
        return texts

    @staticmethod
    def _detect_all(files: Sequence[UploadFile], texts: list[str]) -> list[DetectedChapter]:
        """Deterministic parse — multipart part order is the chapter order."""
        detected: list[DetectedChapter] = []
        for upload, text in zip(files, texts, strict=True):
            detected.extend(detect_chapters(upload.filename or "", text))
        return detected

    async def commit(
        self,
        files: Sequence[UploadFile],
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        adjustments: ImportCommitAdjustments,
    ) -> ImportCommitResponse:
        """Ownership gate → deterministic re-parse → validate → atomic append."""
        await verify_novel_owned(self._novel_repo, novel_id, user_id)

        texts = await self._read_and_validate(files)
        detected = self._detect_all(files, texts)
        if not detected:
            raise ValidationError("No chapters detected in the uploaded files.")
        self._validate_adjustments(adjustments, len(detected))

        selected = [
            dataclasses.replace(
                chapter,
                title=adjustments.title_overrides.get(str(index), chapter.title),
            )
            for index, chapter in enumerate(detected)
            if index not in adjustments.excluded_indices
        ]
        if not selected:
            raise ValidationError("All detected chapters are excluded — nothing to import.")

        start_position = (await self._chapter_repo.max_position(novel_id)) + 1
        rows = await self._chapter_repo.append_chapters(novel_id, selected, start_position)

        logger.info(
            "import_committed",
            novel_id=str(novel_id),
            created=len(rows),
            first_position=start_position,
        )
        return ImportCommitResponse(
            novel_id=str(novel_id),
            created_count=len(rows),
            first_position=start_position,
            last_position=start_position + len(rows) - 1,
            chapters=[
                ImportCommitChapterInfo(
                    id=str(row.id),
                    title=row.title,
                    position=row.position,
                    word_count=row.word_count,
                )
                for row in rows
            ],
        )

    @staticmethod
    def _validate_adjustments(adjustments: ImportCommitAdjustments, chapter_count: int) -> None:
        """Indices must reference the freshly re-parsed chapter list (0-based)."""
        for index in adjustments.excluded_indices:
            if not 0 <= index < chapter_count:
                raise ValidationError(
                    f"Excluded index {index} is out of range (0..{chapter_count - 1})."
                )
        for key, title in adjustments.title_overrides.items():
            # isdecimal() (not isdigit()): int() accepts exactly the isdecimal
            # set — digit-like Unicode ("①".isdigit() is True) would crash
            # int() with an unhandled ValueError on user input.
            if not key.isdecimal() or not 0 <= int(key) < chapter_count:
                raise ValidationError(f"Title override key '{key}' is not a valid chapter index.")
            if not 1 <= len(title.strip()) <= 500:
                raise ValidationError(f"Title override for chapter {key} must be 1-500 characters.")
