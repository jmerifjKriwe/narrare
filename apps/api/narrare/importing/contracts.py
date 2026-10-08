"""Import module service contracts (RULE-03 — written before implementation)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from fastapi import UploadFile
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.analytics.writing_stats_recorder import WritingStatsRecorder
    from narrare.chapters.models import Chapter
    from narrare.importing.schemas import (
        ImportCommitAdjustments,
        ImportCommitResponse,
        ImportPreviewResponse,
    )
    from narrare_core.importing.models import DetectedChapter


class ImportPreviewerProtocol(Protocol):
    """Parse uploaded files into a preview — no DB writes, idempotent."""

    async def preview(self, files: Sequence[UploadFile]) -> ImportPreviewResponse: ...


class ImportCommitterProtocol(Protocol):
    """Re-parse uploaded files and append chapters atomically (ADR-091)."""

    async def commit(
        self,
        files: Sequence[UploadFile],
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        adjustments: ImportCommitAdjustments,
    ) -> ImportCommitResponse: ...


class ImportChapterRepositoryProtocol(Protocol):
    """Bulk chapter append seam (repository owns all SQLAlchemy)."""

    async def max_position(self, novel_id: uuid.UUID) -> int: ...

    async def append_chapters(
        self,
        novel_id: uuid.UUID,
        chapters: Sequence[DetectedChapter],
        start_position: int,
    ) -> list[Chapter]: ...


class ImportServiceProtocol(ImportPreviewerProtocol, ImportCommitterProtocol, Protocol):
    """Full import service surface (preview + commit)."""


def build_import_service(
    session: AsyncSession,
    writing_stats_recorder: WritingStatsRecorder | None = None,
) -> ImportServiceProtocol:
    """Default composition root (re-exported seam for tests).

    ``writing_stats_recorder`` is optional so tests can build the service
    without the STATS-001 seam; production passes the recorder resolved
    by ``get_import_service``.
    """
    from narrare.importing.repository import ImportChapterRepository
    from narrare.importing.service import ImportService
    from narrare.novels.repository import NovelRepository

    return ImportService(
        session=session,
        chapter_repo=ImportChapterRepository(session),
        novel_repo=NovelRepository(session),
        writing_stats_recorder=writing_stats_recorder,
    )
