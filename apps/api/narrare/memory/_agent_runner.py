"""Preference-analysis agent invocation helper (one LLM call).

Extracted from ``analysis_service.py`` for RULE-04 compliance (the
service sat at its 300-line hard limit after the Task 6d prepare()
migration). Owns the single responsibility of running the
``PreferenceAnalysisAgent`` with the resolved prompt — mirroring the
``ai_assist/_agent_runner.py`` precedent.

Model acquisition follows the per-user model-routing cascade with LAZY
first-use resolution (ADR-086): the DI factory
(``router_analysis._get_analysis_service``) wires a
``LazyModelResolution`` around ``resolver.resolve(LLMIntent.EXTRACT, …)``
— no resolution at construction; the service resolves on first use at
the top of its ``_run_agent()`` (after request-body validation) and
passes the resolved config + credentials in; this runner threads them
to its ACTUAL ``registry.prepare()`` resolution point (the single
assembly point). All prompts come from PromptComposer (RULE-02).

See:
    RULE-01b (agents are the primary LLM surface),
    RULE-04 (Modularise, never compress),
    RULE-06 (One responsibility per file),
    RULE-11 (errors logged, degraded output — never swallowed silently).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.agents.preference_analysis_types import PreferenceAnalysisOutput
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


async def run_preference_analysis_agent(
    *,
    model_registry: ModelRegistry,
    model_config: ResolvedModelConfig,
    api_key: str | None = None,
    base_url: str | None = None,
    run_limit_resolver: DefaultRunLimitResolver | None = None,
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    feedback_text: str,
    event_count: int,
    user_id: UUID,
    project_id: UUID,
) -> PreferenceAnalysisOutput:
    """Build Deps + run one PreferenceAnalysisAgent call.

    Falls back to a degraded-but-honest analysis output when model
    resolution, prompt composition, or the agent run fails (RULE-11:
    logged, never silent) — the preference profile degrades instead of
    failing the caller.

    Args:
        model_registry: Model registry.
        model_config: Resolved model config from the per-user routing
            cascade (production wiring always supplies a real config).
        api_key: Resolved per-user credential — overrides the provider
            env var when provided.
        base_url: Resolved base-URL override for OpenAI-compatible
            providers. ``None`` uses the provider default endpoint.
        composer: PromptComposer for the governed analysis prompt.
        invocation_pipeline: Optional pipeline for invocation evidence
            (ADR-048 Mode 1); ``None`` skips the pipeline path.
        feedback_text: Formatted feedback text (runtime content).
        event_count: Number of events being analyzed.
        user_id: The user whose feedback is being analyzed.
        project_id: The project scope for the analysis.

    Returns:
        PreferenceAnalysisOutput with analysis results.
    """
    from narrare_core.agents.preference_analysis_agent import (
        PreferenceAnalysisAgent,
        PreferenceAnalysisDeps,
    )
    from narrare_core.agents.preference_analysis_types import PreferenceAnalysisOutput

    try:
        from uuid import uuid4

        from narrare_core.llm.run_limits import DefaultRunLimitResolver

        # Real resolution point: the config was resolved for THIS user
        # at first use (ADR-086 lazy resolution — the service resolved
        # the per-user model-routing cascade at the top of its
        # _run_agent(), not in the DI factory); the credentials must
        # reach the resolution call so the provider actually
        # authenticates as the user (the setup-wizard bug class).
        # Single assembly point (Task 6d — Task 4/5 pattern): model +
        # intent-aware runtime settings + usage limits as one
        # coherent triple.
        resolved = (run_limit_resolver or DefaultRunLimitResolver()).resolve(
            config=model_config, budget=None, invocation_id=uuid4()
        )
        prepared = await model_registry.prepare(
            model_config,
            intent=LLMIntent.EXTRACT,
            usage_limits=resolved.usage_limits,
            api_key=api_key,
            base_url=base_url,
        )
    except Exception:
        logger.warning("agent_model_unavailable", exc_info=True)
        return PreferenceAnalysisOutput(
            summary="Analysis unavailable — model could not be loaded.",
            confidence=0.0,
        )

    # Compose prompt via compose_invocation (Mode 1 — composer-driven,
    # ADR-048). Enrichment flows through the composer; feedback text is
    # passed as the user prompt at agent.run.
    from narrare._app.invocation_context import build_invocation_context
    from narrare_core.ai_invocation import compose_invocation

    context = PromptContext(
        language="en",
        genre="",
        mode="preferences",
        extra={"event_count": str(event_count)},
    )
    invocation_context = build_invocation_context(
        feature_id="memory_preference_analysis",
        intent=LLMIntent.EXTRACT,
        user_id=user_id,
        project_id=project_id,
    )
    try:
        invocation_result = await compose_invocation(
            invocation_pipeline=invocation_pipeline,
            invocation_context=invocation_context,
            composer=composer,
            prompt_context=context,
            intent=LLMIntent.EXTRACT,
        )
        assert invocation_result.composed_prompt is not None  # Mode 1 always composes
        system_prompt = invocation_result.composed_prompt.system
    except Exception:
        logger.warning(
            "invocation_composition_failed",
            feature_id="memory_preference_analysis",
            exc_info=True,
        )
        composed = await composer.build(LLMIntent.EXTRACT, context)
        system_prompt = composed.system

    agent = PreferenceAnalysisAgent(model=prepared.model, system_prompt=system_prompt)
    deps = PreferenceAnalysisDeps(
        language="en",
        genre="",
        event_count=event_count,
        feedback_text=feedback_text,
    )

    try:
        return await agent.run(
            prompt=feedback_text,
            deps=deps,
            model_settings=prepared.model_settings,
            usage_limits=prepared.usage_limits,
        )
    except Exception:
        logger.warning("agent_run_failed", exc_info=True)
        return PreferenceAnalysisOutput(
            summary="Analysis failed — could not process feedback.",
            confidence=0.0,
        )
