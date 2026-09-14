"""AI remap helpers for the planning domain (WRITE-012).

Extracted from _helpers.py to respect the 400-line file size limit
(RULE-04) after the remap prepared-triple threading wave.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from narrare.planning.schemas import RemapPreviewItem

if TYPE_CHECKING:
    import uuid
    from collections.abc import Mapping

    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.usage import UsageLimits

    from narrare.chapters.models import Chapter
    from narrare.planning.models import ChapterOutline
    from narrare_core.agents.summary_agent import ChapterSummaryAgent
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry

_logger = logging.getLogger(__name__)


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


async def ai_suggest_stage(
    ai_remap_service: object | None,
    summary: str,
    structure_type: str,
    position: int,
    total: int,
    adapter: object,
    agent: object | None = None,
    invocation_pipeline: InvocationPipeline | None = None,
    model_settings: ModelSettings | None = None,
    usage_limits: UsageLimits | None = None,
) -> str:
    """Ask AIRemapService to suggest a stage from summary content.

    Forwards the optional agent, invocation pipeline, and the
    settings/limits halves of the prepared triple to the governed remap
    service (kwargs pass-through, 19009e17 convention — the triple
    crosses the ``analyze_chapter_role`` boundary in full). Falls back
    to adapter suggestion when the AI service returns empty (no agent,
    composition failure, or invalid output).
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
            model_settings=model_settings,
            usage_limits=usage_limits,
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
) -> tuple[ChapterSummaryAgent, ModelSettings | None, UsageLimits | None] | None:
    """Lazily build the remap agent plus the prepared-triple run halves.

    Resolution goes through the single assembly point
    ``ModelRegistry.prepare()`` (Task 6b — Task 4/5 pattern): model +
    intent-aware runtime settings + usage limits as one coherent triple
    (PLAN — the intent the storyboard factory routes this config for,
    mirroring ``_timeline_consistency_helpers.py``).

    Returns the agent together with ``prepared.model_settings`` /
    ``prepared.usage_limits`` so the caller threads the full triple into
    ``AIRemapService.analyze_chapter_role`` (kwargs pass-through,
    19009e17 convention) instead of binding it into constructor state
    (the wiki ``PreparedWikiAgent`` adapter route — rejected here because
    the remap core boundary is ours to widen). The former gap (only the
    model half crossing) is closed.

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
        # The full triple crosses the AIRemapService boundary — the
        # model half at construction, settings + limits via the
        # analyze_chapter_role kwargs at every run.
        return (
            ChapterSummaryAgent(model=prepared.model),
            prepared.model_settings,
            prepared.usage_limits,
        )
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
    chapter-summary coverage, and a resolvable model; the agent plus the
    settings/limits halves of the prepared triple are built lazily once
    per remap call and threaded through ``ai_suggest_stage`` into
    ``analyze_chapter_role`` so the whole triple reaches ``agent.run``.
    Chapters without a summary always use the position-ratio heuristic;
    every unmet condition degrades per chapter (RULE-11: logged, never
    silent).
    """
    use_ai = await should_use_ai_remap(ai_remap_service, chapters)
    remap_agent: ChapterSummaryAgent | None = None
    remap_model_settings: ModelSettings | None = None
    remap_usage_limits: UsageLimits | None = None
    if use_ai:
        prepared_agent = await build_remap_agent(
            model_registry, model_config, api_key=api_key, base_url=base_url
        )
        if prepared_agent is not None:
            remap_agent, remap_model_settings, remap_usage_limits = prepared_agent
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
                model_settings=remap_model_settings,
                usage_limits=remap_usage_limits,
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
