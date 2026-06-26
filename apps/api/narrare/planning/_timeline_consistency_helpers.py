"""Timeline LLM consistency-check helpers — extracted from
``timeline_consistency_service.py`` (RULE-04).

Encapsulates the LLM-based consistency checking via TimelineAgent: prompt
context construction, ADR-046/048 Mode 1 invocation composition (system
prompt resolution via PromptComposer), agent execution, and mapping of
LLM-identified conflicts to :class:`TemporalIssueResponse`.

Extracted to keep ``timeline_consistency_service.py`` under the 300-line
file size limit (RULE-04). The helpers take their dependencies (registry,
config, composer, invocation pipeline) as explicit parameters rather than
as instance state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.planning.timeline_schemas import TemporalIssueResponse

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.planning.models import TimelineEvent
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


async def run_llm_consistency_checks(
    *,
    events: list[TimelineEvent],
    novel: object,
    novel_id: UUID,
    registry: ModelRegistry,
    config: ResolvedModelConfig,
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
) -> list[TemporalIssueResponse]:
    """Run LLM-based consistency checks via TimelineAgent.

    Resolves the system prompt through ``PromptComposer.build()`` with
    ``mode="temporal_consistency"`` (RULE-02b / ADR-046). The cascade
    handles language fallback, user overrides, and governed variable
    substitution. Event context is passed as the user prompt (dynamic
    data) — it is NOT baked into the system prompt.

    LLM checks are supplementary — they find contextual issues that
    deterministic rules cannot detect. Failures are logged and an empty
    list is returned so the request never fails on account of LLM checks.

    Args:
        events: Timeline events to check (must be non-empty).
        novel: Novel object (title/genre/writing_language are read via
            ``getattr``).
        novel_id: UUID of the novel (for invocation evidence recording).
        registry: Shared LLM model registry.
        config: Resolved model config for the LLM checks.
        composer: PromptComposer for resolving the temporal consistency
            system prompt via the governed cascade (RULE-02b).
        invocation_pipeline: For ADR-048 invocation evidence recording.

    Returns:
        List of LLM-identified temporal issues mapped to
        :class:`TemporalIssueResponse` (empty on failure).
    """
    try:
        from narrare_core.agents.timeline_agent import TimelineAgent, TimelineDeps
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.prompts.context import PromptContext

        model = await registry.get_model(config)

        # Build a compact event context for the LLM (user prompt — dynamic data).
        # Per AC-2 (CR-AUFG-02-06): event data goes in the user channel,
        # NOT in the system prompt.
        event_context = "\n".join(
            f"- {e.event_name} (order: {e.temporal_order}, timestamp: {e.timestamp_raw})"
            for e in events[:50]  # Limit context size
        )

        novel_title = getattr(novel, "title", "Unknown")
        genre = getattr(novel, "genre", "") or ""
        language = getattr(novel, "writing_language", "") or "en"

        # Resolve system prompt via PromptComposer (RULE-02b — ADR-046).
        # The temporal_consistency template carries instructions and project
        # metadata only; event data is delivered as the user prompt below.
        ctx = PromptContext(
            language=language,
            writing_language=language,
            project_title=novel_title,
            genre=genre,
            mode="temporal_consistency",
        )
        # Resolve system prompt via compose_invocation (Mode 1 —
        # composer-driven, RULE-02b / ADR-046/048). Enrichment flows
        # through the composer; event data is passed as the user prompt.
        from narrare._app.invocation_context import build_invocation_context
        from narrare_core.ai_invocation import compose_invocation

        invocation_context = build_invocation_context(
            feature_id="planning_timeline_consistency",
            intent=LLMIntent.PLAN,
            project_id=novel_id,
        )
        try:
            invocation_result = await compose_invocation(
                invocation_pipeline=invocation_pipeline,
                invocation_context=invocation_context,
                composer=composer,
                prompt_context=ctx,
                intent=LLMIntent.PLAN,
            )
            assert invocation_result.composed_prompt is not None  # Mode 1 always composes
            system_prompt_text = invocation_result.composed_prompt.system
        except Exception:
            logger.warning(
                "invocation_composition_failed",
                feature_id="planning_timeline_consistency",
                exc_info=True,
            )
            composed = await composer.build(LLMIntent.PLAN, ctx)
            system_prompt_text = composed.system

        deps = TimelineDeps(
            genre=genre,
            language=language,
        )

        agent = TimelineAgent(model=model)
        result = await agent.run(
            prompt=event_context,
            system_prompt=system_prompt_text,
            deps=deps,
        )

        # Convert LLM-identified conflicts to TemporalIssueResponse
        llm_issues: list[TemporalIssueResponse] = []
        for conflict in getattr(result, "temporal_conflicts", []):
            if isinstance(conflict, str):
                llm_issues.append(
                    TemporalIssueResponse(
                        severity="warning",
                        rule_id="llm_temporal_conflict",
                        event_ids=[],
                        description=conflict,
                        suggestion="Review this temporal conflict manually.",
                        source="llm",
                    )
                )
        return llm_issues

    except Exception:
        logger.warning("llm_consistency_checks_failed", exc_info=True)
        # LLM checks are supplementary — don't fail the whole request
        return []
