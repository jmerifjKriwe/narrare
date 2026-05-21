"""Outline mapping helpers and AI remap helpers — converts between ORM
models and schemas.

Extracted from service.py to respect the 300-line file size limit (RULE-04).
Includes AI-powered remap helpers for WRITE-012.
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

    from narrare.chapters.models import Chapter
    from narrare.planning.models import ChapterOutline
    from narrare.planning.schemas import ChapterInStoryboard

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.models import Chapter
    from narrare.planning.models import ChapterOutline
    from narrare.planning.schemas import ChapterInStoryboard

_logger = logging.getLogger(__name__)

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
            has_summary=bool(chapter.summary),
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
        has_summary=bool(chapter.summary),
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


# ---------------------------------------------------------------------------
# AI Remap helpers (WRITE-012)
# ---------------------------------------------------------------------------


async def should_use_ai_remap(
    ai_remap_service: object | None,
    chapters: list[Chapter],
) -> bool:
    """Check if AI remap should be used based on summary coverage.

    Returns True when AIRemapService is available and at least 50%
    of chapters have non-empty summaries.
    """
    from narrare_core.planning.remap import AIRemapService

    if not isinstance(ai_remap_service, AIRemapService):
        return False

    chapters_with_summaries = sum(1 for ch in chapters if ch.summary)
    meets = ai_remap_service.meets_coverage_threshold(
        total_chapters=len(chapters),
        chapters_with_summaries=chapters_with_summaries,
    )
    if meets:
        _logger.info(
            "ai_remap_coverage_met",
            extra={
                "total": len(chapters),
                "with_summaries": chapters_with_summaries,
            },
        )
    return meets


async def ensure_outlines(
    outline_repo: object,
    novel_id: uuid.UUID,
    chapters: list[Chapter],
    adapter: object,
) -> dict[uuid.UUID, ChapterOutline]:
    """Ensure every chapter has an outline, auto-creating missing ones."""
    from narrare_core.planning.adapters.base import StructureAdapter

    raw = await outline_repo.get_all_for_novel(novel_id)  # type: ignore[union-attr]
    outlines = cast("list[ChapterOutline]", raw or [])
    outline_map: dict[uuid.UUID, ChapterOutline] = {o.chapter_id: o for o in outlines}
    total = max(len(chapters), 1)

    for idx, ch in enumerate(chapters, start=1):
        if ch.id not in outline_map:
            if isinstance(adapter, StructureAdapter):
                suggested = adapter.suggest_stage(idx, total)
            else:
                suggested = ""
            outline = await outline_repo.create(  # type: ignore[union-attr]
                chapter_id=ch.id, stage_assignment=suggested
            )
            outline_map[ch.id] = outline
    return outline_map


def chapter_in_storyboard(
    chapter: Chapter,
    outline_map: Mapping[uuid.UUID, object],
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


async def ai_suggest_stage(
    ai_remap_service: object | None,
    summary: str,
    structure_type: str,
    position: int,
    total: int,
    adapter: object,
) -> str:
    """Ask AIRemapService to suggest a stage from summary content.

    Creates a ChapterSummaryAgent if model_registry + model_config
    are available for deeper AI analysis. Falls back to adapter
    suggestion when the AI service returns empty.
    """
    from narrare_core.planning.remap import AIRemapService

    if not isinstance(ai_remap_service, AIRemapService):
        from narrare_core.planning.adapters.base import StructureAdapter

        if isinstance(adapter, StructureAdapter):
            return adapter.suggest_stage(position, total)
        return ""

    try:
        agent: object = None
        stage = await ai_remap_service.analyze_chapter_role(
            summary=summary,
            structure_type=structure_type,
            agent=agent,
        )
        if stage:
            return stage
    except Exception as exc:
        _logger.warning("ai_stage_suggestion_failed", exc_info=exc)

    # Fall back to position-ratio heuristic
    from narrare_core.planning.adapters.base import StructureAdapter

    if isinstance(adapter, StructureAdapter):
        return adapter.suggest_stage(position, total)
    return ""
