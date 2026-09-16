"""Storyboard remap execution + lazy model-resolution state (ADR-086 L21).

Split from ``service.py`` for the RULE-04 size limit the lazy seam
crossed (mirrors ``_writing_support.py``, L37). Two responsibilities:

- ``StoryboardResolution``: per-instance lazy PLAN-cascade state —
  idempotent ``ensure_resolved`` (honest: errors propagate, RULE-11) and
  ``resolve_graceful``, the entry-point policy carrying the eager
  factory's wiring-time swallow: log ``no_ai_provider_configured`` and
  leave the triple unset so AI remap degrades to the position-ratio
  heuristic exactly as before (Pattern M-graceful).
- ``execute_remap``: the first-use remap path — resolve, read, AI/
  heuristic stage suggestion, confirm-persist.

Model acquisition is timing-only (RULE-18): the eager factory resolved
the same PLAN cascade with the same args at wiring time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.planning._remap_helpers import build_remap_items
from narrare.planning.schemas import RemapResponse
from narrare_core.planning.adapters import registry as adapter_registry
from narrare_core.shared.errors import ConfigurationError

if TYPE_CHECKING:
    import uuid

    from narrare._app.dependencies_services import ModelResolution
    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.chapters.models import Chapter
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.novels.models import Novel
    from narrare.planning.contracts import OutlineRepositoryProtocol
    from narrare.planning.models import ChapterOutline
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.planning.remap import AIRemapService

logger = structlog.get_logger(__name__)


class StoryboardResolution:
    """Per-instance lazy PLAN-cascade state for the storyboard service.

    Wraps the injected ``ModelResolution``; the resolved triple is cached
    after the first successful resolve and stays unset for the instance's
    lifetime when the resolve failed gracefully.
    """

    def __init__(self, model_resolution: ModelResolution) -> None:
        self._model_resolution = model_resolution
        self._config: ResolvedModelConfig | None = None
        self._api_key: str | None = None
        self._base_url: str | None = None
        self._resolve_attempted = False

    async def ensure_resolved(self) -> None:
        """Resolve the per-user PLAN routing cascade once.

        First call awaits the injected ``ModelResolution`` and caches the
        triple; repeat calls are idempotent — the cascade runs at most
        once per instance (the eager factory also resolved exactly once
        per request). ``ConfigurationError`` propagates UNCHANGED: the
        graceful swallow is entry-point policy (see :meth:`resolve_graceful`),
        so this method stays honest about what happened (RULE-11).
        """
        if self._resolve_attempted:
            return
        self._resolve_attempted = True
        resolved = await self._model_resolution.resolve()
        self._config = resolved.config
        self._api_key = resolved.api_key
        self._base_url = resolved.base_url

    async def resolve_graceful(self, novel_id: uuid.UUID) -> None:
        """First-use resolve with the preserved graceful degradation.

        A missing AI provider (``ConfigurationError``) is logged with the
        eager factory's byte-identical ``no_ai_provider_configured`` event
        and leaves the triple unset, so AI remap degrades to the
        position-ratio heuristic exactly as it did when the eager factory
        swallowed this error at wiring time — timing only (RULE-11
        sanctioned graceful set, AI-optional feature).
        """
        try:
            await self.ensure_resolved()
        except ConfigurationError:
            logger.info("no_ai_provider_configured", novel_id=str(novel_id))

    @property
    def config(self) -> ResolvedModelConfig | None:
        """The resolved model config, or ``None`` when degraded."""
        return self._config

    @property
    def api_key(self) -> str | None:
        """The resolved API key, or ``None`` when degraded."""
        return self._api_key

    @property
    def base_url(self) -> str | None:
        """The resolved base URL, or ``None`` when degraded."""
        return self._base_url


async def execute_remap(
    *,
    outline_repo: OutlineRepositoryProtocol,
    chapter_repo: ChapterRepositoryProtocol,
    novel_repo: NovelRepositoryProtocol,
    novel: Novel,
    resolution: StoryboardResolution,
    ai_remap_service: AIRemapService | None,
    model_registry: ModelRegistry | None,
    invocation_pipeline: InvocationPipeline | None,
    new_structure: str,
    confirm: bool,
) -> RemapResponse:
    """Run the remap for an already-guarded novel (ADR-086 L21 first use).

    The uid-scoped novel guard has run in the service (gate-before-
    resolution); the first statement here is therefore the lazy resolve —
    graceful (see :meth:`StoryboardResolution.resolve_graceful`), so a
    missing provider degrades the AI path to the heuristic exactly as in
    the eager world.

    Uses AI-powered stage suggestions when AIRemapService is available
    and enough chapters have summaries. Falls back to position-ratio
    heuristic otherwise (see WRITE-012).
    """
    await resolution.resolve_graceful(novel.id)
    chapters: list[Chapter] = await chapter_repo.list_by_novel(novel.id)
    outlines = await outline_repo.get_all_for_novel(novel.id)
    outline_map: dict[uuid.UUID, ChapterOutline] = {o.chapter_id: o for o in outlines}
    new_adapter = adapter_registry.get(new_structure)

    # AI-powered stage suggestions when service + coverage + model allow;
    # degrades to the position-ratio heuristic per chapter (WRITE-012).
    items = await build_remap_items(
        chapters,
        outline_map,
        new_adapter,
        new_structure,
        ai_remap_service,
        model_registry,
        resolution.config,
        api_key=resolution.api_key,
        base_url=resolution.base_url,
        invocation_pipeline=invocation_pipeline,
    )

    if confirm:
        for item in items:
            outline = outline_map.get(item.chapter_id)
            if outline:
                await outline_repo.update(item.chapter_id, stage_assignment=item.new_stage)
            else:
                await outline_repo.create(
                    chapter_id=item.chapter_id,
                    stage_assignment=item.new_stage,
                )
        from narrare.novels.schemas import UpdateNovelRequest

        await novel_repo.update(novel, UpdateNovelRequest(story_structure=new_structure))

    return RemapResponse(new_structure=new_structure, remapped=items, confirmed=confirm)
