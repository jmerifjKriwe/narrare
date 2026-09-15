"""Shared ExtendService test factories (ADR-086 L32 lazy-runtime ctor).

The L32 ctor swap replaced ``pipeline``/``config``/``api_key``/``base_url``
with a single ``runtime_factory`` callable. These builders pin a FIXED
runtime so existing tests stay render- and outcome-inert (same
config/pipeline the eager factory passed) — the service-side lazy
semantics themselves are pinned in
``test_extend_service_lazy_resolution.py``.

Mirrors ``tests/unit/api/writing/_rewrite_factories.py`` (ADR-086 L33
precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.writing._extend_support import ExtendRuntime

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.writing.extend_service import ExtendService
    from narrare.writing.repository import GenerationRepository
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline


def make_static_runtime_factory(
    pipeline: WritingPipeline,
    config: ResolvedModelConfig,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Callable[[], Awaitable[ExtendRuntime]]:
    """A runtime factory returning a fixed runtime (render-inert pin).

    Mirrors ``StaticModelResolution`` for the M-budget composite: the
    service composes this at first use; the runtime is pre-built here.
    """
    runtime = ExtendRuntime(
        config=config,
        api_key=api_key,
        base_url=base_url,
        pipeline=pipeline,
    )

    async def _static_runtime() -> ExtendRuntime:
        return runtime

    return _static_runtime


def make_matrix_extend_service(
    *,
    repo: GenerationRepository,
    pipeline: WritingPipeline,
    chapter_repo: ChapterRepository,
    novel_repo: NovelRepository,
    draft_processor: DraftProcessor,
    config: ResolvedModelConfig,
) -> ExtendService:
    """Build the access-matrix ExtendService over its fakes (ADR-086 pin).

    ``pipeline`` stays the matrix's guard/working mock — the runtime
    factory pins it verbatim, so ``working_llm=False`` still fails the
    test the moment ``pipeline.generate`` (the real LLM boundary) is
    reached.
    """
    from narrare.writing.extend_service import ExtendService

    return ExtendService(
        repo=repo,
        runtime_factory=make_static_runtime_factory(pipeline, config),
        draft_processor=draft_processor,
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
    )
