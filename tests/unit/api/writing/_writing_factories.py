"""Shared WritingService test factories (ADR-086 L37 lazy-runtime ctor).

The L37 ctor swap replaced ``pipeline``/``config``/``api_key``/``base_url``/
``series_history_budget`` with a single ``runtime_factory`` callable. These
builders pin a FIXED runtime so existing tests stay render- and outcome-inert
(same config/pipeline the eager factory passed) — the service-side lazy
semantics themselves are pinned in
``test_writing_service_lazy_resolution.py``.

Mirrors ``tests/unit/api/writing/_style_variant_factories.py`` (ADR-086 L35
precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.writing._summary_invocation import SummaryModelRuntime
from narrare.writing._writing_support import WritingRuntime

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.writing.pipeline import WritingPipeline


def make_static_runtime_factory(
    pipeline: WritingPipeline,
    config: ResolvedModelConfig,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    series_history_budget: int | None = None,
) -> Callable[[], Awaitable[WritingRuntime]]:
    """A runtime factory returning a fixed runtime (render-inert pin).

    Mirrors ``StaticModelResolution`` for the M-budget composite: the
    service composes this at first use; the runtime is pre-built here.
    """
    runtime = WritingRuntime(
        config=config,
        api_key=api_key,
        base_url=base_url,
        pipeline=pipeline,
        series_history_budget=series_history_budget,
    )

    async def _static_runtime() -> WritingRuntime:
        return runtime

    return _static_runtime


def make_static_summary_runtime_factory(
    config: ResolvedModelConfig,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Callable[[], Awaitable[SummaryModelRuntime]]:
    """A runtime factory returning a fixed summary runtime (render-inert pin).

    ADR-086 L38 mirror of :func:`make_static_runtime_factory`: the summary
    service composes this at first use; the frozen ``SummaryModelRuntime``
    is pre-built here (same config/credentials the eager factory passed).
    """
    runtime = SummaryModelRuntime(config=config, api_key=api_key, base_url=base_url)

    async def _static_runtime() -> SummaryModelRuntime:
        return runtime

    return _static_runtime
