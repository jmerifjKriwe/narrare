"""Summary-invocation support — frozen runtime + single invocation assembly.

Extracted from ``summary_service.py`` (ADR-086 L38) to keep the service
under the 300-line RULE-04 limit after the ``ensure_resolved`` lazy seam
was added — mirroring ``series/_band_summary_support.py`` (L25) and
``writing/_style_variants_support.py`` (L35) precedents:

- :class:`SummaryModelRuntime` — the frozen first-use composite the DI
  factory's deferred composition hands to the service: the effective
  model config (sampling overrides applied) and the routing cascade's
  verbatim per-user credentials;
- :func:`run_summary_invocation` — the single SUMMARIZE assembly point:
  canonical KB-context fetch (ADR-067), composer-driven prompt
  composition (Mode 1, ADR-048) with the composer fallback, run-limit
  resolution over the frozen runtime config, ``registry.prepare`` with
  the per-user credentials, and the agent run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from narrare_core.agents.summary_agent import ChapterSummaryAgent, SummaryDeps
from narrare_core.ai_invocation import compose_invocation
from narrare_core.context._render_options import RenderOptions
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from narrare.chapters.models import Chapter
    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare_core.agents.summary_types import SummaryOutput
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SummaryModelRuntime:
    """Frozen first-use resolution output (config + per-user credentials).

    ``config`` already carries the eager factory's sampling overlay
    (temperature 0.3 / cascade ``output_limit``) — the service consumes it
    verbatim via ``ModelRegistry.prepare`` (timing-only migration: WHAT
    unchanged, only WHEN).
    """

    config: ResolvedModelConfig
    api_key: str | None = None
    base_url: str | None = None


async def run_summary_invocation(
    *,
    run_limit_resolver: DefaultRunLimitResolver,
    runtime: SummaryModelRuntime,
    registry: ModelRegistry,
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    kb_context_provider: KBContextProviderProtocol | None,
    chapter: Chapter,
    max_sentences: int,
    language: str,
) -> SummaryOutput:
    """Compose the SUMMARIZE prompt and run the agent (single assembly point).

    Canonical KB context (ADR-067): the kb_characters / kb_locations /
    kb_factions / kb_relationships slots are fetched+rendered through the
    reusable provider (mirrors coreference_service). Degrades to an empty
    bundle when no provider is wired or the KB is empty (RULE-11) — the
    provider never raises. Spreading ``to_prompt_variables()`` — not a
    literal ``""`` assignment — keeps every slot fed from real KB context
    (architectural-discipline §7). Active since the summarize template's
    header-demotion activation slice: the Knowledge-Base region is
    rendered (no longer below the ``extract_section`` parse cutoff), so
    these variables land in the composed render; degradation stays an
    empty bundle (RULE-11).
    """
    from narrare._app.invocation_context import build_invocation_context
    from narrare.kb.context_contracts import KBContextBundle

    if kb_context_provider is None:
        kb_bundle = KBContextBundle.empty(RenderOptions(annotate_provenance=True))
    else:
        kb_bundle = await kb_context_provider.fetch_context(
            chapter.novel_id,
            entity_types=["character", "location", "faction"],
            options=RenderOptions(annotate_provenance=True),
        )
    kb_vars = kb_bundle.to_prompt_variables()

    # Compose prompt via compose_invocation (Mode 1 — composer-driven,
    # ADR-048). Enrichment flows through the composer into the system
    # prompt; chapter content is passed as the user prompt at agent.run.
    context = PromptContext(
        language=language,
        genre="",
        chapter_title=chapter.title,
        mode="summarize",
        extra={
            "max_sentences": str(max_sentences),
            **(kb_vars or {}),
        },
    )
    invocation_context = build_invocation_context(
        feature_id="writing_summary",
        intent=LLMIntent.SUMMARIZE,
        project_id=chapter.novel_id,
        language=language,
    )
    try:
        invocation_result = await compose_invocation(
            invocation_pipeline=invocation_pipeline,
            invocation_context=invocation_context,
            composer=composer,
            prompt_context=context,
            intent=LLMIntent.SUMMARIZE,
        )
        assert invocation_result.composed_prompt is not None  # Mode 1 always composes
        system_prompt = invocation_result.composed_prompt.system
    except Exception:
        logger.warning(
            "invocation_composition_failed",
            feature_id="writing_summary",
            exc_info=True,
        )
        composed = await composer.build(LLMIntent.SUMMARIZE, context)
        system_prompt = composed.system

    # Run the summary agent — single assembly point (Task 6c —
    #    Task 4/5 pattern): model + intent-aware runtime settings +
    #    usage limits as one coherent triple.
    resolved = run_limit_resolver.resolve(config=runtime.config, budget=None, invocation_id=uuid4())
    prepared = await registry.prepare(
        runtime.config,
        intent=LLMIntent.SUMMARIZE,
        usage_limits=resolved.usage_limits,
        api_key=runtime.api_key,
        base_url=runtime.base_url,
    )
    agent = ChapterSummaryAgent(model=prepared.model, system_prompt=system_prompt)

    deps = SummaryDeps(
        language=language,
        genre="",
        chapter_title=chapter.title,
        max_sentences=max_sentences,
    )

    return await agent.run(
        prompt=chapter.content[:3000],
        deps=deps,
        model_settings=prepared.model_settings,
        usage_limits=prepared.usage_limits,
    )
