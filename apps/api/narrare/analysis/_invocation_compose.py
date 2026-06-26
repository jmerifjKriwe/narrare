"""Shared Mode 1 (composer-driven) invocation composition helper for analysis services.

Extracted from POV, Readability, and BetaReader services (RULE-04) to
deduplicate the identical ``compose_invocation`` wiring pattern. Each
service calls :func:`compose_analysis_invocation_prompt` with its
domain-specific ``feature_id``, ``intent``, and ``mode``.

Single ``compose_invocation`` call: prepare -> merge enrichment ->
compose -> finalize. Enrichment (kb_suggested, user_preferences) flows
through the composer into the feature-specific system prompt, and evidence
is correlated with the real composed prompt.

On pipeline failure (enrichment, validation, evidence recording), falls back
to direct ``composer.build()`` so analysis proceeds regardless of
evidence/enrichment issues — preserving the prior Mode 2 behavioural
contract that evidence problems don't block analysis (RULE-11: logged,
not silent).

See:
    ADR-048, ADR-045 Decision 3/7,
    CONSTRAINTS.md RULE-02/RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.analysis.errors import AnalysisError
from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts import PromptComposer
    from narrare_core.prompts.composer import ComposedPrompt

logger = structlog.get_logger(__name__)


async def compose_analysis_invocation_prompt(
    *,
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    feature_id: str,
    intent: LLMIntent,
    novel_id: UUID,
    user_id: UUID,
    language: str,
    mode: str,
) -> ComposedPrompt:
    """Compose an analysis system prompt via Mode 1 (composer-driven, ADR-048).

    Single ``compose_invocation`` call: prepare -> merge enrichment ->
    compose -> finalize. Enrichment (kb_suggested, user_preferences) flows
    through the composer into the feature-specific system prompt, and evidence
    is correlated with the real composed prompt.

    On pipeline failure (enrichment, validation, evidence recording), falls
    back to direct ``composer.build()`` so analysis proceeds regardless of
    evidence/enrichment issues (RULE-11: logged, not silent).

    Args:
        composer: PromptComposer for system prompt assembly.
        invocation_pipeline: The InvocationPipeline, or ``None`` for the
            backward-compatible fallback (no enrichment, no evidence).
        feature_id: Domain feature identifier (e.g. ``"analysis_pov"``,
            ``"analysis_readability"``, ``"analysis_beta_read"``).
        intent: LLMIntent for composition (``ANALYSE`` or ``BETA_READ``).
        novel_id: The project containing the analysed chapters.
        user_id: The user requesting analysis (for enrichment).
        language: Resolved language code.
        mode: PromptComposer mode (e.g. ``"pov"``, ``"readability"``,
            ``"beta_reader"``).

    Returns:
        The composed prompt (with ``.system`` for the agent constructor).

    Raises:
        AnalysisError: If both pipeline composition and fallback composition
            fail.
    """
    from narrare._app.invocation_context import build_invocation_context
    from narrare_core.ai_invocation import compose_invocation

    ctx = PromptContext(language=language, mode=mode, project_title="")
    invocation_context = build_invocation_context(
        feature_id=feature_id,
        intent=intent,
        user_id=user_id,
        project_id=novel_id,
        language=language,
    )
    try:
        invocation = await compose_invocation(
            invocation_pipeline=invocation_pipeline,
            invocation_context=invocation_context,
            composer=composer,
            prompt_context=ctx,
            intent=intent,
        )
        composed = invocation.composed_prompt
        if composed is not None:
            return composed
        # Mode 1 invariant: composed_prompt is set. Log + fall through.
        logger.warning(
            "invocation_composition_empty",
            feature_id=feature_id,
            mode=mode,
        )
    except Exception:
        logger.warning(
            "invocation_composition_failed",
            feature_id=feature_id,
            mode=mode,
            exc_info=True,
        )
    # Fallback: compose directly without pipeline (no enrichment, no
    # evidence). Raises AnalysisError on failure (RULE-11).
    ctx = PromptContext(language=language, mode=mode, project_title="")
    try:
        return await composer.build(intent, ctx)
    except Exception as exc:
        logger.error(
            "prompt_composition_failed",
            feature_id=feature_id,
            mode=mode,
            error=str(exc),
        )
        raise AnalysisError(f"Failed to compose {feature_id} prompt") from exc
