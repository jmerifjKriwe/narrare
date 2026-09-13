"""Outline mapping helpers and AI remap helpers — converts between ORM
models and schemas.

Extracted from service.py to respect the 300-line file size limit (RULE-04).
Includes AI-powered remap helpers for WRITE-012.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from narrare.planning.schemas import BeatSchema, OutlineResponse, RemapPreviewItem
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
    from narrare_core.agents.summary_agent import ChapterSummaryAgent
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry

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


async def ai_suggest_stage(
    ai_remap_service: object | None,
    summary: str,
    structure_type: str,
    position: int,
    total: int,
    adapter: object,
    agent: object | None = None,
    invocation_pipeline: InvocationPipeline | None = None,
) -> str:
    """Ask AIRemapService to suggest a stage from summary content.

    Forwards the optional agent and invocation pipeline to the governed
    remap service. Falls back to adapter suggestion when the AI service
    returns empty (no agent, composition failure, or invalid output).
    """
    from narrare_core.planning.remap import AIRemapService

    if not isinstance(ai_remap_service, AIRemapService):
        from narrare_core.planning.adapters.base import StructureAdapter

        if isinstance(adapter, StructureAdapter):
            return adapter.suggest_stage(position, total)
        return ""

    try:
        stage = await ai_remap_service.analyze_chapter_role(
            summary=summary,
            structure_type=structure_type,
            agent=agent,
            invocation_pipeline=invocation_pipeline,
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


async def build_remap_agent(
    model_registry: ModelRegistry | None,
    model_config: ResolvedModelConfig | None,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> ChapterSummaryAgent | None:
    """Lazily build the remap agent from the resolved model routing.

    Resolution goes through the single assembly point
    ``ModelRegistry.prepare()`` (Task 6b — Task 4/5 pattern): model +
    intent-aware runtime settings + usage limits as one coherent triple
    (PLAN — the intent the storyboard factory routes this config for,
    mirroring ``_timeline_consistency_helpers.py``).

    Known limitation (documented in-code per the guard's design):
    ``AIRemapService.analyze_chapter_role`` (packages/core) invokes
    ``agent.run(prompt, deps)`` with no model_settings/usage_limits
    surface, so only ``prepared.model`` can be consumed here — the
    settings/limits halves of the triple stop at that core boundary
    (same gap class as the wiki path noted in
    ``test_prepare_coverage_guard.py``). Widening the core remap
    surface is out of scope for this file; the guard itself stays
    intact (no sanctioned-exception entry).

    Returns ``None`` when no provider is configured (model_config is
    None) or model construction fails — AI remap then degrades to the
    position-ratio heuristic per chapter (RULE-11: logged, never silent).
    """
    if model_registry is None or model_config is None:
        return None
    from uuid import uuid4

    from narrare_core.agents.summary_agent import ChapterSummaryAgent
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.llm.run_limits import DefaultRunLimitResolver

    try:
        resolved = DefaultRunLimitResolver().resolve(
            config=model_config, budget=None, invocation_id=uuid4()
        )
        prepared = await model_registry.prepare(
            model_config,
            intent=LLMIntent.PLAN,
            usage_limits=resolved.usage_limits,
            api_key=api_key,
            base_url=base_url,
        )
        # Only the model half crosses the AIRemapService boundary — see
        # the limitation note in the docstring above.
        return ChapterSummaryAgent(model=prepared.model)
    except Exception as exc:
        _logger.warning("remap_agent_build_failed", exc_info=exc)
        return None


async def build_remap_items(
    chapters: list[Chapter],
    outline_map: Mapping[uuid.UUID, ChapterOutline],
    new_adapter: object,
    structure_type: str,
    ai_remap_service: object | None,
    model_registry: ModelRegistry | None,
    model_config: ResolvedModelConfig | None,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    invocation_pipeline: InvocationPipeline | None = None,
) -> list[RemapPreviewItem]:
    """Build remap preview items, suggesting stages via AI when warranted.

    The AI path (WRITE-012) requires an injected AIRemapService, >=50%
    chapter-summary coverage, and a resolvable model; the agent is built
    lazily once per remap call. Chapters without a summary always use the
    position-ratio heuristic; every unmet condition degrades per chapter
    (RULE-11: logged, never silent).
    """
    use_ai = await should_use_ai_remap(ai_remap_service, chapters)
    remap_agent = (
        await build_remap_agent(model_registry, model_config, api_key=api_key, base_url=base_url)
        if use_ai
        else None
    )
    total = max(len(chapters), 1)
    items: list[RemapPreviewItem] = []
    for idx, ch in enumerate(chapters, start=1):
        outline = outline_map.get(ch.id)
        old_stage = outline.stage_assignment if outline else ""
        if use_ai and ai_remap_service is not None and ch.summary:
            new_stage = await ai_suggest_stage(
                ai_remap_service,
                ch.summary,
                structure_type,
                idx,
                total,
                new_adapter,
                agent=remap_agent,
                invocation_pipeline=invocation_pipeline,
            )
        else:
            new_stage = _adapter_suggested_stage(new_adapter, idx, total)
        items.append(
            RemapPreviewItem(
                chapter_id=ch.id,
                chapter_title=ch.title,
                old_stage=old_stage,
                new_stage=new_stage,
            )
        )
    return items


def _adapter_suggested_stage(adapter: object, position: int, total: int) -> str:
    """Position-ratio stage suggestion; empty when not a StructureAdapter."""
    from narrare_core.planning.adapters.base import StructureAdapter

    if isinstance(adapter, StructureAdapter):
        return adapter.suggest_stage(position, total)
    return ""
