"""Shared StyleVariantService test factories (ADR-086 L35 lazy-runtime ctor).

The L35 ctor swap replaced ``pipeline``/``config``/``api_key``/``base_url``
with a single ``runtime_factory`` callable. These builders pin a FIXED
runtime so existing tests stay render- and outcome-inert (same
config/pipeline the eager factory passed) — the service-side lazy
semantics themselves are pinned in
``test_style_variant_service_lazy_resolution.py``.

Mirrors ``tests/unit/api/writing/_extend_factories.py`` (ADR-086 L32
precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.writing._style_variants_support import StyleVariantRuntime

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.style_variant_service import StyleVariantService
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline


def make_static_runtime_factory(
    pipeline: WritingPipeline,
    config: ResolvedModelConfig,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Callable[[], Awaitable[StyleVariantRuntime]]:
    """A runtime factory returning a fixed runtime (render-inert pin).

    Mirrors ``StaticModelResolution`` for the M-budget composite: the
    service composes this at first use; the runtime is pre-built here.
    """
    runtime = StyleVariantRuntime(
        config=config,
        api_key=api_key,
        base_url=base_url,
        pipeline=pipeline,
    )

    async def _static_runtime() -> StyleVariantRuntime:
        return runtime

    return _static_runtime


def make_matrix_style_variant_service(
    *,
    repo: GenerationRepository,
    pipeline: WritingPipeline,
    chapter_repo: ChapterRepository,
    novel_repo: NovelRepository,
    draft_processor: DraftProcessor,
    config: ResolvedModelConfig,
) -> StyleVariantService:
    """Build the access-matrix StyleVariantService over its fakes (ADR-086 pin).

    ``pipeline`` stays the matrix's guard/working mock — the runtime
    factory pins it verbatim, so ``working_llm=False`` still fails the
    test the moment ``pipeline.generate`` (the real LLM boundary) is
    reached.
    """
    from narrare.writing.style_variant_service import StyleVariantService

    return StyleVariantService(
        repo=repo,
        runtime_factory=make_static_runtime_factory(pipeline, config),
        draft_processor=draft_processor,
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
    )
