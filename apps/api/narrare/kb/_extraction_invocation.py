"""Extraction LLM invocation scaffolding — compose + resolve + prepare.

Extracted from ``extraction_service.py`` (RULE-04 split: the service
module exceeded the 300-line limit after the IDOR gate + ADR-085
provenance merge). One responsibility (RULE-06): the extraction LLM
invocation path — Mode 1 prompt composition (ADR-048, with graceful
fallback), ADR-045 run-limit resolution, and the single assembly point
(``ModelRegistry.prepare``).

See:
    :class:`narrare.kb.extraction_service.ExtractionService`,
    ADR-040, ADR-045, ADR-048, RULE-02/05/11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm._prepared_call import PreparedModelCall
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.prompts.context import PromptContext

logger = structlog.get_logger(__name__)


async def compose_and_prepare(
    *,
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    registry: ModelRegistry,
    config: ResolvedModelConfig,
    api_key: str | None,
    base_url: str | None,
    run_limit_resolver: DefaultRunLimitResolver | None,
    novel_id: UUID,
    user_id: UUID,
    prompt_context: PromptContext,
) -> tuple[str, PreparedModelCall]:
    """Compose the extraction system prompt and prepare the model call.

    Steps (behavior preserved verbatim from the service):
      3. Compose prompt via compose_invocation (Mode 1 — composer-driven,
         ADR-048). Enrichment flows through the composer into the system
         prompt; on pipeline failure the call degrades to a direct
         composer build (RULE-11, logged).
      4. Resolve run limits first (ADR-045 Decision 4) so the prepared
         call can carry them: usage_limits (+ max_tokens mirrored into
         model_settings) bound generation even on thinking models with
         tool_choice: required. None (legacy/test default) applies no
         output caps.
      5. Single assembly point (ModelRegistry.prepare): resolves the
         model with per-user credentials injected (model-routing
         cascade — the user's wizard-configured provider is used) AND
         builds the runtime model_settings (intent-aware thinking
         policy + ADR-045 output cap) as one coherent triple.

    Returns:
        ``(system_prompt, prepared)`` — the composed system prompt and the
        coherent prepared call for ``ExtractionAgent``.
    """
    from narrare._app.invocation_context import build_invocation_context
    from narrare_core.ai_invocation import compose_invocation
    from narrare_core.llm.intents import LLMIntent

    invocation_context = build_invocation_context(
        feature_id="kb_extract",
        intent=LLMIntent.KB_EXTRACT,
        user_id=user_id,
        project_id=novel_id,
    )
    try:
        invocation_result = await compose_invocation(
            invocation_pipeline=invocation_pipeline,
            invocation_context=invocation_context,
            composer=composer,
            prompt_context=prompt_context,
            intent=LLMIntent.KB_EXTRACT,
        )
        assert invocation_result.composed_prompt is not None  # Mode 1 always composes
        system_prompt = invocation_result.composed_prompt.system
    except Exception:
        logger.warning(
            "invocation_composition_failed",
            feature_id="kb_extract",
            exc_info=True,
        )
        composed = await composer.build(LLMIntent.KB_EXTRACT, prompt_context)
        system_prompt = composed.system

    # 4. Resolve run limits first (ADR-045 Decision 4) so the prepared
    #    call can carry them: usage_limits (+ max_tokens mirrored into
    #    model_settings) bound generation even on thinking models with
    #    tool_choice: required. None (legacy/test default) applies no
    #    output caps.
    resolved_limits = (
        run_limit_resolver.resolve(
            config=config,
            budget=None,
            invocation_id=uuid4(),
        )
        if run_limit_resolver is not None
        else None
    )

    # 5. Single assembly point (ModelRegistry.prepare): resolves the
    #    model with per-user credentials injected (model-routing
    #    cascade — the user's wizard-configured provider is used) AND
    #    builds the runtime model_settings (intent-aware thinking
    #    policy + ADR-045 output cap) as one coherent triple. The
    #    historical duplicate get_model call and the fragmented
    #    settings assembly are impossible by construction now.
    prepared = await registry.prepare(
        config,
        intent=LLMIntent.KB_EXTRACT,
        usage_limits=resolved_limits.usage_limits if resolved_limits else None,
        api_key=api_key,
        base_url=base_url,
    )
    return system_prompt, prepared
