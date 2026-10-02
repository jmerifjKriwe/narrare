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
    ImportSplitCandidate,
)
from narrare.novels.ownership import verify_novel_owned
from narrare_core.importing.candidates import find_split_candidates
from narrare_core.importing.detector import detect_chapters
from narrare_core.importing.operations import apply_operations, build_operation_set
from narrare_core.shared.errors import ValidationError

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from fastapi import UploadFile
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.importing.contracts import ImportChapterRepositoryProtocol
    from narrare.importing.schemas import ImportCommitAdjustments, ImportSplitOperation
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
                split_candidates=self._split_candidates_for(c),
            )
            for i, c in enumerate(detected)
        ]
        return ImportPreviewResponse(
            items=items,
            file_count=len(files),
            chapter_count=len(detected),
            total_word_count=sum(c.word_count for c in detected),
        )

    @staticmethod
    def _is_md_source(chapter: DetectedChapter) -> bool:
        """D2a (shared predicate): split affordances are .md-only.

        Case-insensitive source-file extension check — the ONE place the
        .md-only rule lives; preview and commit both consume it.
        """
        return chapter.source_file.lower().endswith(".md")

    @staticmethod
    def _split_candidates_for(chapter: DetectedChapter) -> list[ImportSplitCandidate]:
        """Split candidates offered for one detected chapter (D2a ruling).

        .txt chapters are merge-only: their preview carries
        ``split_candidates: []`` even when the content contains ``###``
        lines — split points are a .md-only affordance. Candidates stay
        capped in Core.
        """
        if not ImportService._is_md_source(chapter):
            return []
        return [
            ImportSplitCandidate(
                ordinal=candidate.ordinal,
                heading=candidate.heading,
                words_before=candidate.words_before,
            )
            for candidate in find_split_candidates(chapter.content)
        ]

    @staticmethod
    def _reject_non_md_splits(
        splits: Sequence[ImportSplitOperation], detected: list[DetectedChapter]
    ) -> None:
        """D2a on BOTH phases: commit must reject what preview cannot offer.

        Core's op validation is content-pure (``find_split_candidates``
        sees the `###` lines inside .txt content too), so the source-file
        policy is enforced here — same rule, same helper as preview.
        Out-of-range indices fall through to Core's per-op drift errors,
        which name them precisely. Merges stay allowed (merge-only).
        """
        for op in splits:
            if 0 <= op.index < len(detected) and not ImportService._is_md_source(
                detected[op.index]
            ):
                raise ValidationError(
                    f"Split for chapter {op.index} is not allowed: source file "
                    f"'{detected[op.index].source_file}' is not Markdown (.md) — "
                    f"plain-text chapters are merge-only."
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
        """Ownership gate → re-parse → .md split gate → apply ops → selection → append.

        Splits/merges address ORIGINAL indices and are validated + applied
        by Core (``apply_operations``); the D2a .md-only split gate runs in
        this service first (commit rejects what preview cannot offer).
        Exclusions/rename address FINAL (post-ops) indices. Empty ops ⇒
        final ≡ original (v1 identity).
        """
        await verify_novel_owned(self._novel_repo, novel_id, user_id)

        texts = await self._read_and_validate(files)
        detected = self._detect_all(files, texts)
        if not detected:
            raise ValidationError("No chapters detected in the uploaded files.")
        self._reject_non_md_splits(adjustments.splits, detected)
        op_set = build_operation_set(
            splits=[(op.index, op.at) for op in adjustments.splits],
            merges=[op.indices for op in adjustments.merges],
        )
        materialized = apply_operations(detected, op_set)
        self._validate_adjustments(adjustments, len(materialized))

        selected = [
            dataclasses.replace(
                chapter,
                title=adjustments.title_overrides.get(str(final_index), chapter.title),
            )
            for final_index, chapter in enumerate(materialized)
            if final_index not in adjustments.excluded_indices
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
            splits=len(op_set.splits),
            merges=len(op_set.merges),
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
    def _validate_adjustments(adjustments: ImportCommitAdjustments, final_count: int) -> None:
        """FINAL-space indices must reference the materialized (post-ops) list."""
        for index in adjustments.excluded_indices:
            if not 0 <= index < final_count:
                raise ValidationError(
                    f"Excluded index {index} is out of range (0..{final_count - 1})."
                )
        for key, title in adjustments.title_overrides.items():
            # isdecimal() (not isdigit()): int() accepts exactly the isdecimal
            # set — digit-like Unicode ("①".isdigit() is True) would crash
            # int() with an unhandled ValueError on user input.
            if not key.isdecimal() or not 0 <= int(key) < final_count:
                raise ValidationError(
                    f"Title override key '{key}' is not a valid final chapter index."
                )
            # Stored RAW into Chapter.title String(500): the RAW length must
            # fit the column (stripped-only checks would pass whitespace
            # padding that overflows it); stripped minimum 1 rejects
            # whitespace-only titles.
            if len(title) > 500 or not title.strip():
                raise ValidationError(
                    f"Title override for final chapter {key} must be 1-500 characters."
                )
