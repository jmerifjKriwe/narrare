"""Storyboard service — business logic for the planning domain.

Orchestrates outline CRUD, storyboard assembly, sync status calculation,
and structure remap. Delegates mapping helpers to ``_helpers.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.planning._helpers import compute_sync, find_position, to_outline_response
from narrare.planning.schemas import (
    ChapterInStoryboard,
    OutlineResponse,
    OutlineUpdateRequest,
    RemapPreviewItem,
    RemapResponse,
    StoryboardResponse,
    StoryboardStageResponse,
    SyncStatusResponse,
)
from narrare_core.planning.adapters import registry as adapter_registry
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.models import Chapter
    from narrare.novels.models import Novel
    from narrare.planning.contracts import OutlineRepositoryProtocol
    from narrare_core.planning.adapters.base import StructureAdapter

logger = structlog.get_logger(__name__)

# TODO: WRITE-012 Chapter Summary — once chapters.summary is populated by
# WRITE-012, use AI analysis of summaries for intelligent stage suggestions
# instead of position-ratio heuristic. Related: INFRA-003 Context Assembly
# Tier 2 (Recent History) would also benefit from summaries.


class StoryboardService:
    """Business logic for storyboard views, outlines, and remap."""

    def __init__(
        self,
        outline_repo: OutlineRepositoryProtocol,
        chapter_repo: object,
        novel_repo: object,
    ) -> None:
        self._outline_repo = outline_repo
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo

    # ------------------------------------------------------------------
    # Storyboard view
    # ------------------------------------------------------------------

    async def get_storyboard(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> StoryboardResponse:
        """Assemble the full storyboard view for a novel."""
        novel = await self._get_novel(novel_id, user_id)
        adapter = adapter_registry.get(novel.story_structure)
        chapters = await self._list_chapters(novel_id)
        outline_map = await self._ensure_outlines(novel_id, chapters, adapter)
        total = max(len(chapters), 1)

        stages: list[StoryboardStageResponse] = []
        for stage_def in adapter.stages:
            stage_chapters = [
                self._chapter_in_storyboard(ch, outline_map, idx, adapter, total)
                for idx, ch in enumerate(chapters, start=1)
                if outline_map.get(ch.id) and outline_map[ch.id].stage_assignment == stage_def.id  # type: ignore[union-attr]
            ]
            stages.append(
                StoryboardStageResponse(
                    stage_id=stage_def.id,
                    stage_name=stage_def.name,
                    chapters=stage_chapters,
                )
            )
        return StoryboardResponse(structure_type=novel.story_structure, stages=stages)

    async def get_sync_status(
        self, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[SyncStatusResponse]:
        """Calculate sync status for all chapters in a novel."""
        novel = await self._get_novel(novel_id, user_id)
        adapter = adapter_registry.get(novel.story_structure)
        chapters = await self._list_chapters(novel_id)
        outlines = await self._outline_repo.get_all_for_novel(novel_id)
        outline_map = {o.chapter_id: o for o in outlines}
        total = max(len(chapters), 1)

        return [
            SyncStatusResponse(
                chapter_id=ch.id,
                sync_status=compute_sync(
                    ch, outline_map.get(ch.id), adapter.suggest_stage(i, total)
                ).value,
            )
            for i, ch in enumerate(chapters, start=1)
        ]

    # ------------------------------------------------------------------
    # Outline CRUD
    # ------------------------------------------------------------------

    async def get_or_create_outline(
        self,
        chapter_id: uuid.UUID,
        structure_type: str,
        user_id: uuid.UUID,
        *,
        novel_id: uuid.UUID | None = None,
    ) -> OutlineResponse:
        """Get an existing outline or create one with a suggested stage."""
        existing = await self._outline_repo.get_by_chapter_id(chapter_id)
        if existing is not None:
            return to_outline_response(existing)

        # Need novel_id to look up chapters
        if novel_id is None:
            raise NotFoundError("Chapter", identifier=str(chapter_id))
        chapters = await self._list_chapters(novel_id)
        chapter = next((ch for ch in chapters if ch.id == chapter_id), None)
        if chapter is None:
            raise NotFoundError("Chapter", identifier=str(chapter_id))

        adapter = adapter_registry.get(structure_type)
        position = find_position(chapters, chapter_id)
        total = max(len(chapters), 1)

        outline = await self._outline_repo.create(
            chapter_id=chapter_id,
            stage_assignment=adapter.suggest_stage(position, total),
        )
        logger.info("outline_auto_created", chapter_id=str(chapter_id))
        return to_outline_response(outline)

    async def update_outline(
        self,
        chapter_id: uuid.UUID,
        request: OutlineUpdateRequest,
        user_id: uuid.UUID,
        *,
        novel_id: uuid.UUID | None = None,
    ) -> OutlineResponse:
        """Update specific fields on a chapter outline."""
        updates = request.model_dump(exclude_none=True)
        if "planned_beats" in updates and request.planned_beats is not None:
            updates["planned_beats"] = [
                b.model_dump() if hasattr(b, "model_dump") else b for b in request.planned_beats
            ]

        existing = await self._outline_repo.get_by_chapter_id(chapter_id)
        if existing is not None:
            outline = await self._outline_repo.update(chapter_id, **updates)
        else:
            stage = updates.pop("stage_assignment", "")
            beats = updates.pop("planned_beats", [])
            notes = updates.pop("outline_notes", "")
            outline = await self._outline_repo.create(
                chapter_id=chapter_id,
                stage_assignment=stage,
                planned_beats=beats,
                outline_notes=notes,
            )
        logger.info("outline_updated", chapter_id=str(chapter_id))
        return to_outline_response(outline)

    # ------------------------------------------------------------------
    # Remap
    # ------------------------------------------------------------------

    async def preview_remap(
        self, novel_id: uuid.UUID, new_structure: str, user_id: uuid.UUID
    ) -> RemapResponse:
        """Preview what a structure change would do (no DB writes)."""
        return await self._do_remap(novel_id, new_structure, user_id, confirm=False)

    async def confirm_remap(
        self, novel_id: uuid.UUID, new_structure: str, user_id: uuid.UUID
    ) -> RemapResponse:
        """Execute the structure remap — updates outlines and novel."""
        result = await self._do_remap(novel_id, new_structure, user_id, confirm=True)
        logger.info(
            "remap_confirmed",
            novel_id=str(novel_id),
            new_structure=new_structure,
            count=len(result.remapped),
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _do_remap(
        self,
        novel_id: uuid.UUID,
        new_structure: str,
        user_id: uuid.UUID,
        *,
        confirm: bool,
    ) -> RemapResponse:
        """Shared logic for preview and confirm remap."""
        adapter_registry.get(new_structure)  # validate early
        novel = await self._get_novel(novel_id, user_id)
        chapters = await self._list_chapters(novel_id)
        outlines = await self._outline_repo.get_all_for_novel(novel_id)
        outline_map = {o.chapter_id: o for o in outlines}
        new_adapter = adapter_registry.get(new_structure)
        total = max(len(chapters), 1)

        items: list[RemapPreviewItem] = []
        for idx, ch in enumerate(chapters, start=1):
            outline = outline_map.get(ch.id)
            old_stage = outline.stage_assignment if outline else ""
            new_stage = new_adapter.suggest_stage(idx, total)
            items.append(
                RemapPreviewItem(
                    chapter_id=ch.id,
                    chapter_title=ch.title,
                    old_stage=old_stage,
                    new_stage=new_stage,
                )
            )

        if confirm:
            for item in items:
                outline = outline_map.get(item.chapter_id)
                if outline:
                    await self._outline_repo.update(
                        item.chapter_id, stage_assignment=item.new_stage
                    )
                else:
                    await self._outline_repo.create(
                        chapter_id=item.chapter_id,
                        stage_assignment=item.new_stage,
                    )
            from narrare.novels.schemas import UpdateNovelRequest

            await self._novel_repo.update(  # type: ignore[union-attr]
                novel, UpdateNovelRequest(story_structure=new_structure)
            )

        return RemapResponse(new_structure=new_structure, remapped=items, confirmed=confirm)

    async def _ensure_outlines(
        self, novel_id: uuid.UUID, chapters: list[Chapter], adapter: StructureAdapter
    ) -> dict[uuid.UUID, object]:
        """Ensure every chapter has an outline, auto-creating missing ones."""
        outlines = await self._outline_repo.get_all_for_novel(novel_id)
        outline_map: dict[uuid.UUID, object] = {o.chapter_id: o for o in outlines}
        total = max(len(chapters), 1)

        for idx, ch in enumerate(chapters, start=1):
            if ch.id not in outline_map:
                suggested = adapter.suggest_stage(idx, total)
                outline = await self._outline_repo.create(
                    chapter_id=ch.id, stage_assignment=suggested
                )
                outline_map[ch.id] = outline
        return outline_map

    def _chapter_in_storyboard(
        self,
        chapter: Chapter,
        outline_map: dict[uuid.UUID, object],
        idx: int,
        adapter: StructureAdapter,
        total: int,
    ) -> ChapterInStoryboard:
        """Build a ChapterInStoryboard for a single chapter."""
        outline = outline_map.get(chapter.id)
        suggested = adapter.suggest_stage(idx, total)
        status = compute_sync(chapter, outline, suggested)
        return ChapterInStoryboard(
            chapter_id=chapter.id,
            title=chapter.title,
            word_count=chapter.word_count,
            sync_status=status.value,
            position=chapter.position,
        )

    async def _get_novel(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> Novel:
        """Fetch a novel by ID or raise NotFoundError."""
        novel = await self._novel_repo.get_by_id(novel_id, user_id)  # type: ignore[union-attr]
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))
        return novel  # type: ignore[no-any-return]

    async def _list_chapters(self, novel_id: uuid.UUID) -> list[Chapter]:
        """List all chapters for a novel, ordered by position."""
        return await self._chapter_repo.list_by_novel(novel_id)  # type: ignore[union-attr]
