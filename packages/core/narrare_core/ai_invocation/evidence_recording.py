"""Evidence recording step for InvocationPipeline.

Extracted from ``pipeline.py`` to keep orchestration below RULE-04 limits while
preserving the two-phase invocation contract.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.ai_invocation._evidence import build_invocation_evidence

if TYPE_CHECKING:
    from narrare_core.ai_invocation.contracts import FeatureInvocationEvidenceSink
    from narrare_core.ai_invocation.models import (
        FeatureInvocationEvidence,
        PromptInvocationContext,
        ValidationResult,
    )
    from narrare_core.ai_invocation.pipeline import PreparedInvocation
    from narrare_core.prompts.composer import ComposedPrompt

logger = structlog.get_logger(__name__)


async def record_pipeline_evidence(
    *,
    evidence_sink: FeatureInvocationEvidenceSink | None,
    context: PromptInvocationContext,
    prepared: PreparedInvocation | None,
    final_validation: ValidationResult,
    final_validator_ran: bool,
    prompt: ComposedPrompt,
) -> bool:
    """Build and record evidence. Returns True if recorded successfully."""
    if evidence_sink is None:
        return False

    evidence = build_pipeline_evidence(
        context=context,
        prepared=prepared,
        final_validation=final_validation,
        final_validator_ran=final_validator_ran,
        prompt=prompt,
    )

    try:
        await evidence_sink.record(evidence)
        return True
    except Exception:
        logger.warning(
            "pipeline_evidence_recording_failed",
            feature_id=context.feature_id,
            exc_info=True,
        )
        return False


def build_pipeline_evidence(
    *,
    context: PromptInvocationContext,
    prepared: PreparedInvocation | None,
    final_validation: ValidationResult,
    final_validator_ran: bool,
    prompt: ComposedPrompt,
) -> FeatureInvocationEvidence:
    """Build a privacy-safe evidence record from pipeline state."""
    return build_invocation_evidence(
        context=context,
        prepared=prepared,
        final_validation=final_validation,
        final_validator_ran=final_validator_ran,
    )
