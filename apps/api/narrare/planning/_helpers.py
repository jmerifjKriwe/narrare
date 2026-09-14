"""Outline mapping helpers — converts between ORM models and schemas.

Extracted from service.py to respect the 300-line file size limit (RULE-04).
AI remap helpers (WRITE-012) live in _remap_helpers.py (RULE-04 split).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from narrare.planning.schemas import BeatSchema, OutlineResponse
from narrare_core.planning.adapters.base import BeatDef
from narrare_core.planning.models import ChapterOutlineData, SyncStatus
from narrare_core.planning.sync import StructuralSyncChecker

if TYPE_CHECKING:
    import uuid
    from collections.abc import Mapping
    from typing import Protocol

    from narrare.chapters.models import Chapter
    from narrare.planning.models import ChapterOutline
    from narrare.planning.schemas import ChapterInStoryboard

    class _OutlineRepoProtocol(Protocol):
        """Minimal outline repository interface — duck-typing for ensure_outlines."""

        async def get_all_for_novel(self, novel_id: uuid.UUID) -> list[ChapterOutline]: ...
        async def create(self, chapter_id: uuid.UUID, stage_assignment: str) -> ChapterOutline: ...


_logger = logging.getLogger(__name__)

_checker = StructuralSyncChecker()


def to_outline_response(outline: ChapterOutline) -> OutlineResponse:
    """Convert a ChapterOutline ORM object to OutlineResponse."""
    raw_beats = cast("list[dict[str, str | bool]]", outline.planned_beats or [])
    beats = [
        BeatSchema(
            title=str(b.get("title", "")),
            description=str(b.get("description", "")),
            completed=bool(b.get("completed", False)),
        )
        for b in raw_beats
    ]
    return OutlineResponse(
        id=outline.id,
        chapter_id=outline.chapter_id,
        stage_assignment=outline.stage_assignment,
        planned_beats=beats,
        outline_notes=outline.outline_notes,
        created_at=outline.created_at,
        updated_at=outline.updated_at,
    )


def build_outline_data(chapter: Chapter, outline: ChapterOutline | None) -> ChapterOutlineData:
    """Build ChapterOutlineData for sync status computation."""
    if outline is None:
        return ChapterOutlineData(
            chapter_id=chapter.id,
            stage_assignment="",
            planned_beats=[],
            outline_notes="",
            has_content=bool(chapter.content),
            word_count=chapter.word_count,
            has_summary=bool(chapter.summary),
        )
    raw_beats = cast("list[dict[str, str | bool]]", outline.planned_beats or [])
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
        stage_assignment=outline.stage_assignment,
        planned_beats=beats,
        outline_notes=outline.outline_notes,
        has_content=bool(chapter.content),
        word_count=chapter.word_count,
        has_summary=bool(chapter.summary),
    )


def compute_sync(
    chapter: Chapter, outline: ChapterOutline | None, suggested_stage: str
) -> SyncStatus:
    """Calculate sync status for a single chapter."""
    data = build_outline_data(chapter, outline)
    return _checker.calculate_sync_status(data, suggested_stage)


def find_position(chapters: list[Chapter], chapter_id: uuid.UUID) -> int:
    """Return 1-based position of a chapter in the list."""
    for idx, ch in enumerate(chapters, start=1):
        if ch.id == chapter_id:
            return idx
    return 1


async def ensure_outlines(
    outline_repo: _OutlineRepoProtocol,
    novel_id: uuid.UUID,
    chapters: list[Chapter],
    adapter: object,
) -> dict[uuid.UUID, ChapterOutline]:
    """Ensure every chapter has an outline, auto-creating missing ones."""
    from narrare_core.planning.adapters.base import StructureAdapter

    raw = await outline_repo.get_all_for_novel(novel_id)
    outlines = raw or []
    outline_map: dict[uuid.UUID, ChapterOutline] = {o.chapter_id: o for o in outlines}
    total = max(len(chapters), 1)

    for idx, ch in enumerate(chapters, start=1):
        if ch.id not in outline_map:
            if isinstance(adapter, StructureAdapter):
                suggested = adapter.suggest_stage(idx, total)
            else:
                suggested = ""
            outline = await outline_repo.create(chapter_id=ch.id, stage_assignment=suggested)
            outline_map[ch.id] = outline
    return outline_map


def chapter_in_storyboard(
    chapter: Chapter,
    outline_map: Mapping[uuid.UUID, ChapterOutline],
    idx: int,
    adapter: object,
    total: int,
) -> ChapterInStoryboard:
    """Build a ChapterInStoryboard for a single chapter."""
    from narrare.planning.schemas import ChapterInStoryboard
    from narrare_core.planning.adapters.base import StructureAdapter

    outline = outline_map.get(chapter.id)
    suggested = ""
    if isinstance(adapter, StructureAdapter):
        suggested = adapter.suggest_stage(idx, total)
    status = compute_sync(chapter, outline, suggested)
    return ChapterInStoryboard(
        chapter_id=chapter.id,
        title=chapter.title,
        word_count=chapter.word_count,
        sync_status=status.value,
        position=chapter.position,
    )
