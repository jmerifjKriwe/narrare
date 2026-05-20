"""Outline mapping helpers — converts between ORM models and schemas.

Extracted from service.py to respect the 300-line file size limit (RULE-04).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from narrare.planning.schemas import BeatSchema, OutlineResponse
from narrare_core.planning.adapters.base import BeatDef
from narrare_core.planning.models import ChapterOutlineData, SyncStatus
from narrare_core.planning.sync import StructuralSyncChecker

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.models import Chapter

_checker = StructuralSyncChecker()


def to_outline_response(outline: object) -> OutlineResponse:
    """Convert a ChapterOutline ORM object to OutlineResponse."""
    raw_beats = cast("list[dict[str, str | bool]]", outline.planned_beats or [])  # type: ignore[union-attr]
    beats = [
        BeatSchema(
            title=str(b.get("title", "")),
            description=str(b.get("description", "")),
            completed=bool(b.get("completed", False)),
        )
        for b in raw_beats
    ]
    return OutlineResponse(
        id=outline.id,  # type: ignore[union-attr]
        chapter_id=outline.chapter_id,  # type: ignore[union-attr]
        stage_assignment=outline.stage_assignment,  # type: ignore[union-attr]
        planned_beats=beats,
        outline_notes=outline.outline_notes,  # type: ignore[union-attr]
        created_at=outline.created_at,  # type: ignore[union-attr]
        updated_at=outline.updated_at,  # type: ignore[union-attr]
    )


def build_outline_data(chapter: Chapter, outline: object | None) -> ChapterOutlineData:
    """Build ChapterOutlineData for sync status computation."""
    if outline is None:
        return ChapterOutlineData(
            chapter_id=chapter.id,
            stage_assignment="",
            planned_beats=[],
            outline_notes="",
            has_content=bool(chapter.content),
            word_count=chapter.word_count,
        )
    raw_beats = cast("list[dict[str, str | bool]]", outline.planned_beats or [])  # type: ignore[union-attr]
    beats = [
        BeatDef(
            title=str(b.get("title", "")),
            description=str(b.get("description", "")),
            required=bool(b.get("required", True)),
        )
        for b in raw_beats
    ]
    return ChapterOutlineData(
        chapter_id=chapter.id,
        stage_assignment=outline.stage_assignment,  # type: ignore[union-attr]
        planned_beats=beats,
        outline_notes=outline.outline_notes,  # type: ignore[union-attr]
        has_content=bool(chapter.content),
        word_count=chapter.word_count,
    )


def compute_sync(chapter: Chapter, outline: object | None, suggested_stage: str) -> SyncStatus:
    """Calculate sync status for a single chapter."""
    data = build_outline_data(chapter, outline)
    return _checker.calculate_sync_status(data, suggested_stage)


def find_position(chapters: list[Chapter], chapter_id: uuid.UUID) -> int:
    """Return 1-based position of a chapter in the list."""
    for idx, ch in enumerate(chapters, start=1):
        if ch.id == chapter_id:
            return idx
    return 1
