"""Timeline extraction invocation assembly (RULE-04 split, ADR-086 L24).

Extracted from ``TimelineExtractionService.stream_extraction`` so the
service stays under the 300-line limit when the lazy model-resolution
seam (``ensure_resolved`` + graceful entry-point policy) was added for
ADR-086 L24. Pure assembly of the per-novel extraction invocation:

- Prompt resolution is Mode 1 (composer-driven) per ADR-054 D2/D7/D8:
  the governed system prompt is composed ONCE via ``compose_invocation``
  before the per-chapter loop (the framing does not vary per chapter);
  per-chapter content is runtime data (RULE-02a category 3) and flows
  as the run prompt. No inline prompt strings (RULE-02).
- Task 6b single assembly point: the coherent
  ``(model, model_settings, usage_limits)`` triple from
  ``ModelRegistry.prepare``, with the resolved credential triple
  threaded through (ADR-086 L24, L20-L22 family shape).
- The ``TemporalExtractionAgent`` is built once — same model + composed
  system prompt for every chapter.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, NamedTuple

from narrare_core.shared.errors import ConfigurationError

if TYPE_CHECKING:
    from narrare.novels.models import Novel
    from narrare_core.agents.temporal_extraction_agent import (
        TemporalExtractionAgent,
        TemporalExtractionDeps,
    )
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm._prepared_call import PreparedModelCall
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.composer import ComposedPrompt, PromptComposer


class ExtractionInvocation(NamedTuple):
    """Everything the per-chapter extraction loop consumes.

    ``composed_prompt`` supplies the shared user channel (with the
    per-chapter runtime-data fallback); ``agent``/``deps``/``prepared``
    feed ``agent.run`` (Task 6b single assembly point).
    """

    composed_prompt: ComposedPrompt
    agent: TemporalExtractionAgent
    deps: TemporalExtractionDeps
    prepared: PreparedModelCall


async def prepare_extraction_invocation(
    *,
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    registry: ModelRegistry,
    config: ResolvedModelConfig,
    api_key: str | None,
    base_url: str | None,
    run_limit_resolver: DefaultRunLimitResolver,
    novel: Novel,
    novel_id: uuid.UUID,
    language: str,
    existing_event_names: list[str],
) -> ExtractionInvocation:
    """Assemble the extraction invocation (prompt, agent, prepared triple).

    Args:
        composer: PromptComposer for the governed template (RULE-02b).
        invocation_pipeline: Optional pipeline for invocation evidence.
        registry: Shared LLM model registry (``prepare`` assembly point).
        config: Resolved model config (from the lazy cascade, ADR-086 L24).
        api_key: Resolved per-user API key (threaded to ``prepare``).
        base_url: Resolved per-user base URL (threaded to ``prepare``).
        run_limit_resolver: ADR-045 run-limit resolver.
        novel: The novel (title/genre metadata).
        novel_id: Target novel UUID (invocation-context project id).
        language: Resolved writing language.
        existing_event_names: Already-known event names (dedup hint),
            rendered into the template's ``existing_events`` variable.

    Returns:
        The assembled :class:`ExtractionInvocation`.

    Raises:
        ConfigurationError: If composition produced no system prompt
            (Mode 1 invariant) or composition itself fails (RULE-11 —
            propagated, never swallowed).
    """
    from narrare._app.invocation_context import build_invocation_context
    from narrare_core.agents.temporal_extraction_agent import (
        TemporalExtractionAgent,
        TemporalExtractionDeps,
    )
    from narrare_core.ai_invocation import compose_invocation
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.context import PromptContext

    ctx = PromptContext(
        language=language,
        writing_language=language,
        project_title=novel.title,
        genre=novel.genre or "",
        mode="timeline_extraction",
        extra={
            "existing_events": ("\n".join(existing_event_names) if existing_event_names else ""),
        },
    )

    invocation_context = build_invocation_context(
        feature_id="planning_timeline_extraction",
        intent=LLMIntent.PLAN,
        project_id=novel_id,
    )
    invocation = await compose_invocation(
        invocation_pipeline=invocation_pipeline,
        invocation_context=invocation_context,
        composer=composer,
        prompt_context=ctx,
        intent=LLMIntent.PLAN,
    )
    composed_prompt = invocation.composed_prompt
    # Mode 1 guarantees composed_prompt is set; the guard documents the
    # invariant and satisfies the type-checker (RULE-11: no silent None).
    if composed_prompt is None:  # pragma: no cover - Mode 1 invariant
        raise ConfigurationError(
            "Prompt composition produced no system prompt for timeline extraction.",
            code="COMPOSITION_EMPTY",
        )

    # Task 6b single assembly point: coherent (model, model_settings,
    # usage_limits) triple, with the resolved credential triple threaded
    # through (ADR-086 L24, L20-L22 family shape).
    resolved = run_limit_resolver.resolve(config=config, budget=None, invocation_id=uuid.uuid4())
    prepared = await registry.prepare(
        config,
        intent=LLMIntent.PLAN,
        usage_limits=resolved.usage_limits,
        api_key=api_key,
        base_url=base_url,
    )
    deps = TemporalExtractionDeps(
        genre=novel.genre or "",
        language=language,
        existing_events=existing_event_names,
    )
    # Same model + composed system prompt for every chapter — build the agent once.
    agent = TemporalExtractionAgent(model=prepared.model, system_prompt=composed_prompt.system)
    return ExtractionInvocation(
        composed_prompt=composed_prompt, agent=agent, deps=deps, prepared=prepared
    )
