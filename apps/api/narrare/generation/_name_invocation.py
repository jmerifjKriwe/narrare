"""Invocation-pipeline composition for name generation (ADR-048 Mode 2).

The name generator composes its prompt inline (system channel via
PromptComposer + user channel via an inline builder) and calls
``ModelRegistry.run`` directly rather than a first-class NarrareAgent. Per
ADR-045 Decision 3 Option C this is a manual-injection (Mode 2) exception:
the pipeline runs ``prepare`` (enrichment) and ``finalize`` (evidence), but
prompt composition is owned by the caller. The evidence record therefore
carries a typed manual-injection marker instead of a composed-prompt
fingerprint.

This module has one responsibility (RULE-06): orchestrate the
InvocationPipeline for name generation. Parsing, prompt building, and
registry invocation stay in :mod:`narrare.generation.name_service`.

See:
    ADR-048, ADR-045 Decision 3/7,
    CONSTRAINTS.md RULE-02a/RULE-03/RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.ai_invocation import ManualInjectionDeclaration

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.prompts.context import PromptContext

logger = structlog.get_logger(__name__)

# ADR-048 Mode 2 declaration. NameGeneratorService composes its complete
# prompt inline (PromptComposer for the system channel + an inline user-prompt
# builder) and passes it directly to ModelRegistry.run without a first-class
# NarrareAgent. The pipeline therefore records a manual-injection marker
# rather than a composed-prompt fingerprint.
_NAME_GENERATOR_MANUAL_INJECTION = ManualInjectionDeclaration(
    reason=(
        "NameGeneratorService composes its prompt inline (PromptComposer for "
        "the system channel plus an inline user-prompt builder) and passes it "
        "directly to ModelRegistry.run without a first-class NarrareAgent."
    ),
    variables=(
        "name_style",
        "name_type",
        "count",
        "gender",
        "existing_names",
        "explanation_language",
    ),
    injection_mechanism="agent_deps",
)


async def compose_name_invocation(
    pipeline: InvocationPipeline | None,
    *,
    project_id: UUID,
    language: str,
    prompt_context: PromptContext,
) -> PromptContext:
    """Compose the name-generation invocation (Mode 2) via the pipeline.

    Runs ``prepare`` (enrichment) and ``finalize`` (evidence) through the
    :func:`~narrare_core.ai_invocation.compose_invocation` adapter, returning
    the enriched :class:`PromptContext` for the caller's inline composition.

    Failures are logged and non-fatal: the caller always receives a usable
    context (the original when ``pipeline`` is ``None`` or composition fails),
    so name generation proceeds regardless of evidence/enrichment issues
    (RULE-11 -- logged, never silently swallowed, but no hard outage).

    Args:
        pipeline: The InvocationPipeline, or ``None`` for backward-compatible
            fallback (no enrichment, no evidence).
        project_id: Project (novel) the names are generated for.
        language: Output/explanation language for the invocation context.
        prompt_context: The base PromptContext built from the request.

    Returns:
        The enriched PromptContext (merged with prepared dynamic inputs), or
        the original ``prompt_context`` when enrichment did not occur.
    """
    from narrare._app.invocation_context import build_invocation_context
    from narrare_core.ai_invocation import compose_invocation
    from narrare_core.llm.intents import LLMIntent

    invocation_context = build_invocation_context(
        feature_id="generation_name",
        intent=LLMIntent.NAME_GENERATE,
        project_id=project_id,
        language=language,
    )
    try:
        result = await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=invocation_context,
            prompt_context=prompt_context,
            manual_injection=_NAME_GENERATOR_MANUAL_INJECTION,
        )
    except Exception:
        logger.warning(
            "invocation_composition_failed",
            feature_id="generation_name",
            exc_info=True,
        )
        return prompt_context

    return result.merged_context if result.merged_context is not None else prompt_context
