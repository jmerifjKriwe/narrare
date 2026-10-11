"""Storyboard service — business logic for the planning domain.

Orchestrates outline CRUD, storyboard assembly, sync status calculation,
and structure remap. Delegates mapping helpers to ``_helpers.py``, AI
remap helpers (WRITE-012) to ``_remap_helpers.py``, and remap execution
+ lazy resolution state to ``_storyboard_support.py``.

AI Enhancement (WRITE-012): When chapter summaries exist and an
AIRemapService is injected, structure remap uses AI analysis of summaries
for intelligent stage suggestions instead of position-ratio heuristic.

Model acquisition (ADR-086 L21): the per-user PLAN routing cascade is
injected as a ``ModelResolution`` and resolved on first remap use —
after the uid-scoped novel guard, never at construction (the eager
factory resolved — and ran its wiring-time guard — at wiring time).
Graceful degradation (AI-optional feature) is service policy: a missing
provider is logged and degrades to the preserved heuristic-remap
outcome (the eager ``model_config=None`` semantics).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.planning._helpers import (
    chapter_in_storyboard,
    compute_sync,
    ensure_outlines,
    find_position,
    to_outline_response,
)
from narrare.planning._storyboard_support import StoryboardResolution, execute_remap
from narrare.planning.schemas import (
    OutlineResponse,
    OutlineUpdateRequest,
    RemapResponse,
    StoryboardResponse,
    StoryboardStageResponse,
    SyncStatusResponse,
)
from narrare_core.planning.adapters import registry as adapter_registry
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare._app.dependencies_services import ModelResolution
    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.chapters.models import Chapter
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.novels.models import Novel
    from narrare.planning.contracts import OutlineRepositoryProtocol, ScenePlanRepositoryProtocol
    from narrare.planning.models import ScenePlan
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.planning.remap import AIRemapService

logger = structlog.get_logger(__name__)


class StoryboardService:
    """Business logic for storyboard views, outlines, and remap.

    Optionally integrates AIRemapService for AI-powered structure remap
    when chapter summaries are available (WRITE-012).

    Sync (PLAN-001 T14 — ADR-096) is scene-driven: storyboard assembly
    and sync status fetch the novel's scene plans via the injected scene
    repository and thread a per-chapter scene map into the Core sync
    checker.
    """

    def __init__(
        self,
        outline_repo: OutlineRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
        scene_repo: ScenePlanRepositoryProtocol,
        ai_remap_service: AIRemapService | None = None,
        model_registry: ModelRegistry | None = None,
        *,
        model_resolution: ModelResolution,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._outline_repo = outline_repo
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._scene_repo = scene_repo
        self._ai_remap_service = ai_remap_service
        self._model_registry = model_registry
        # Lazy per-user PLAN cascade (ADR-086 L21) — resolved on first
        # remap use, never at construction.
        self._resolution = StoryboardResolution(model_resolution)
        self._invocation_pipeline = invocation_pipeline

    # ------------------------------------------------------------------
    # Storyboard view
    # ------------------------------------------------------------------

    async def get_storyboard(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> StoryboardResponse:
        """Assemble the full storyboard view for a novel."""
        novel = await self._get_novel(novel_id, user_id)
        adapter = adapter_registry.get(novel.story_structure)
        chapters = await self._list_chapters(novel_id)
        outline_map = await ensure_outlines(self._outline_repo, novel_id, chapters, adapter)
        scene_map = await self._fetch_scene_map(novel_id)
        total = max(len(chapters), 1)

        stages: list[StoryboardStageResponse] = []
        for stage_def in adapter.stages:
            stage_chapters = [
                chapter_in_storyboard(
                    ch,
                    outline_map,
                    idx,
                    adapter,
                    total,
                    scenes=scene_map.get(ch.id, ()),
                )
                for idx, ch in enumerate(chapters, start=1)
                if (outline := outline_map.get(ch.id)) is not None
                and outline.stage_assignment == stage_def.id
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
        scene_map = await self._fetch_scene_map(novel_id)
        total = max(len(chapters), 1)

        return [
            SyncStatusResponse(
                chapter_id=ch.id,
                sync_status=compute_sync(
                    ch,
                    outline_map.get(ch.id),
                    adapter.suggest_stage(i, total),
                    scenes=scene_map.get(ch.id, ()),
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
        """Update specific fields on a chapter outline.

        PLAN-001 T14: stage + notes only — scene plans are managed through
        the aggregate PUT (``ScenePlanService.save_aggregate``).
        """
        updates = request.model_dump(exclude_none=True)

        existing = await self._outline_repo.get_by_chapter_id(chapter_id)
        if existing is not None:
            outline = await self._outline_repo.update(chapter_id, **updates)
        else:
            stage = updates.pop("stage_assignment", "")
            notes = updates.pop("outline_notes", "")
            outline = await self._outline_repo.create(
                chapter_id=chapter_id,
                stage_assignment=stage,
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
        """Validate the remap request, then delegate execution.

        The uid-scoped novel guard (``_get_novel`` — the eager factory's
        wiring-time guard, relocated per the ADR-086 planning guard
        ruling) stays immediately ahead of the first-use resolve inside
        ``execute_remap`` (gate-before-resolution ordering).
        """
        adapter_registry.get(new_structure)  # validate early
        novel = await self._get_novel(novel_id, user_id)
        return await execute_remap(
            outline_repo=self._outline_repo,
            chapter_repo=self._chapter_repo,
            novel_repo=self._novel_repo,
            novel=novel,
            resolution=self._resolution,
            ai_remap_service=self._ai_remap_service,
            model_registry=self._model_registry,
            invocation_pipeline=self._invocation_pipeline,
            new_structure=new_structure,
            confirm=confirm,
        )

    async def _get_novel(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> Novel:
        """Fetch a novel by ID or raise NotFoundError."""
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))
        return novel

    async def _fetch_scene_map(self, novel_id: uuid.UUID) -> dict[uuid.UUID, tuple[ScenePlan, ...]]:
        """Fetch the novel's scene plans grouped by chapter (sync input)."""
        scenes = await self._scene_repo.list_by_novel(novel_id)
        scene_map: dict[uuid.UUID, tuple[ScenePlan, ...]] = {}
        for scene in scenes:
            scene_map[scene.chapter_id] = (*scene_map.get(scene.chapter_id, ()), scene)
        return scene_map

    async def _list_chapters(self, novel_id: uuid.UUID) -> list[Chapter]:
        """List all chapters for a novel, ordered by position."""
        return await self._chapter_repo.list_by_novel(novel_id)
