"""Band-summary lazy-resolution runtime + invocation assembly (ADR-086 L25).

``BandSummaryModelRuntime`` is the frozen composite the deferred factory
closure (``series/dependencies_band_summary.py::
build_band_summary_service``) composes at the service's first use: the
SUMMARIZE routing cascade resolved post-entry, overlaid with the eager
factory's verbatim sampling composition (``temperature=0.3``,
``max_tokens=limits.output_limit`` from the token-limits cascade), plus the
per-user credentials.

``run_band_summary_invocation`` is the agent invocation assembly (model +
intent-aware runtime settings + usage limits as one coherent triple, then the
agent run) — relocated from ``band_summary_service.py`` for the 300-line
RULE-04 limit the ``ensure_resolved`` addition crossed (same behavior, only
moved; ``_series_voice_invocation.py`` precedent).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from narrare_core.agents.band_summary_types import BandSummaryDeps
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from collections.abc import Callable

    from narrare_core.agents.band_summary_agent import BandSummaryAgent
    from narrare_core.agents.band_summary_types import BandSummaryOutput
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.run_limits import DefaultRunLimitResolver


@dataclass(frozen=True)
class BandSummaryModelRuntime:
    """Frozen first-use resolution output (config + per-user credentials).

    ``config`` already carries the eager factory's sampling overlay
    (temperature 0.3 / cascade ``output_limit``) — the service consumes it
    verbatim via ``ModelRegistry.prepare`` (timing-only migration: WHAT
    unchanged, only WHEN).
    """

    config: ResolvedModelConfig
    api_key: str | None = None
    base_url: str | None = None


async def run_band_summary_invocation(
    *,
    run_limit_resolver: DefaultRunLimitResolver,
    runtime: BandSummaryModelRuntime,
    registry: ModelRegistry,
    agent_factory: Callable[..., BandSummaryAgent],
    system_prompt: str,
    novel_title: str,
    genre: str,
    chapter_summaries: list[str],
) -> BandSummaryOutput:
    """Resolve the model triple and run ``BandSummaryAgent`` (RULE-01b).

    Single assembly point (Spec 2 Task 6d): run-limit resolution over the
    frozen runtime config, ``registry.prepare`` with the per-user
    credentials, then the agent run — chapter summaries flow as runtime
    content in the user-channel prompt (RULE-02a category 3);
    ``BandSummaryDeps`` carries the same data for validators/tools.
    """
    from narrare.series.band_summary_prompt import format_chapter_summaries

    resolved = run_limit_resolver.resolve(config=runtime.config, budget=None, invocation_id=uuid4())
    prepared = await registry.prepare(
        runtime.config,
        intent=LLMIntent.SUMMARIZE,
        usage_limits=resolved.usage_limits,
        api_key=runtime.api_key,
        base_url=runtime.base_url,
    )
    agent = agent_factory(prepared.model, system_prompt)

    deps = BandSummaryDeps(
        novel_title=novel_title,
        genre=genre,
        chapter_summaries=chapter_summaries,
    )
    return await agent.run(
        prompt=format_chapter_summaries(chapter_summaries),
        deps=deps,
        model_settings=prepared.model_settings,
        usage_limits=prepared.usage_limits,
    )
