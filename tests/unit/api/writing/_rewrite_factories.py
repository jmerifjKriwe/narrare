"""Shared RewriteService test factories (ADR-086 L33 lazy-runtime ctor).

The L33 ctor swap replaced ``pipeline``/``config``/``api_key``/``base_url``
with a single ``runtime_factory`` callable. These builders pin a FIXED
runtime so existing tests stay render- and outcome-inert (same
config/pipeline the eager factory passed) — the service-side lazy
semantics themselves are pinned in
``test_rewrite_service_lazy_resolution.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.writing._rewrite_support import RewriteRuntime

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.rewrite_service import RewriteService
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline


def make_static_runtime_factory(
    pipeline: WritingPipeline,
    config: ResolvedModelConfig,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Callable[[], Awaitable[RewriteRuntime]]:
    """A runtime factory returning a fixed runtime (render-inert pin).

    Mirrors ``StaticModelResolution`` for the M-budget composite: the
    service composes this at first use; the runtime is pre-built here.
    """
    runtime = RewriteRuntime(
        config=config,
        api_key=api_key,
        base_url=base_url,
        pipeline=pipeline,
    )

    async def _static_runtime() -> RewriteRuntime:
        return runtime

    return _static_runtime


def make_matrix_rewrite_service(
    *,
    repo: GenerationRepository,
    pipeline: WritingPipeline,
    chapter_repo: ChapterRepository,
    novel_repo: NovelRepository,
    draft_processor: DraftProcessor,
    config: ResolvedModelConfig,
) -> RewriteService:
    """Build the access-matrix RewriteService over its fakes (ADR-086 pin).

    ``pipeline`` stays the matrix's guard/working mock — the runtime
    factory pins it verbatim, so ``working_llm=False`` still fails the
    test the moment ``pipeline.generate`` (the real LLM boundary) is
    reached.
    """
    from narrare.writing.rewrite_service import RewriteService

    return RewriteService(
        repo=repo,
        runtime_factory=make_static_runtime_factory(pipeline, config),
        draft_processor=draft_processor,
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
    )
