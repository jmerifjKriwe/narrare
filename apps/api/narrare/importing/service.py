"""Import service — guard pipeline, parse orchestration, atomic append.

Preview is stateless (no DB writes). Commit re-parses deterministically and
appends chapters in the caller's request transaction (ADR-091).

Task 2 (SETUP-003) ships the preview surface; ``commit`` follows in Task 3
(together with the Task-3-only imports: ``uuid``, ``Chapter``,
``ImportCommitAdjustments``, ``ImportCommitChapterInfo``,
``ImportCommitResponse``).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from narrare.importing.constants import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
)
from narrare.importing.schemas import ImportPreviewItem, ImportPreviewResponse
from narrare_core.importing.detector import detect_chapters
from narrare_core.shared.errors import ValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fastapi import UploadFile
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.importing.contracts import ImportChapterRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare_core.importing.models import DetectedChapter

logger = structlog.get_logger(__name__)


class ImportService:
    """Implements ImportServiceProtocol (contracts.py) implicitly."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        chapter_repo: ImportChapterRepositoryProtocol | None = None,
        novel_repo: NovelRepositoryProtocol | None = None,
    ) -> None:
        # Interim Task-2 shape: preview touches no collaborators, so they are
        # optional until Task 3 wires them for `commit` (then tightened).
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
