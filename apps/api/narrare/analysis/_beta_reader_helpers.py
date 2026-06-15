"""Beta reader invocation helpers — extracted from beta_reader_service.py (RULE-04).

Encapsulates the ADR-048 Mode 2 invocation composition for both Phase 1
(analyze) and Phase 2 (deep_dive) to keep the service file under the
300-line limit.

Each helper builds an invocation context, composes the invocation with the
appropriate ``ManualInjectionDeclaration``, and records evidence via the
``InvocationPipeline``.  Failures are logged and swallowed — analysis
proceeds regardless of evidence recording issues.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.ai_invocation import ManualInjectionDeclaration
from narrare_core.llm import LLMIntent

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.ai_invocation.pipeline import InvocationPipeline

logger = structlog.get_logger(__name__)

# ADR-048 Mode 2 declarations: BetaReaderAgent composes its prompt internally
# from BetaReaderDeps (chapter text, focus categories, language, budget tier).
_BETA_READER_PHASE1_MANUAL_INJECTION = ManualInjectionDeclaration(
    reason=(
        "BetaReaderAgent composes its Phase 1 prompt internally from "
        "BetaReaderDeps (chapter text, word count, focus categories, language)."
    ),
    variables=("chapter_text", "focus_categories", "language"),
    injection_mechanism="agent_deps",
)

_BETA_READER_PHASE2_MANUAL_INJECTION = ManualInjectionDeclaration(
    reason=(
        "BetaReaderAgent composes its Phase 2 deep-dive prompt internally from "
        "BetaReaderDeps (chapter text, deepdive category, Phase 1 summaries)."
    ),
    variables=("chapter_text", "deepdive_category", "phase1_summaries"),
    injection_mechanism="agent_deps",
)


async def compose_phase1_invocation(
    pipeline: InvocationPipeline | None,
    *,
    novel_id: UUID,
    user_id: UUID,
    language: str,
) -> None:
    """Compose invocation (Mode 2 — agent-internal) and record evidence for Phase 1.

    ADR-048. Replaces the former placeholder-evidence path. Failures are
    logged and swallowed — analysis proceeds regardless.
    """
    from narrare._app.invocation_context import build_invocation_context
    from narrare_core.ai_invocation import compose_invocation

    invocation_context = build_invocation_context(
        feature_id="analysis_beta_read",
        intent=LLMIntent.BETA_READ,
        user_id=user_id,
        project_id=novel_id,
        language=language,
    )
    try:
        await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=invocation_context,
            manual_injection=_BETA_READER_PHASE1_MANUAL_INJECTION,
        )
    except Exception:
        logger.warning(
            "invocation_composition_failed",
            feature_id="analysis_beta_read",
            exc_info=True,
        )


async def compose_phase2_invocation(
    pipeline: InvocationPipeline | None,
    *,
    novel_id: UUID,
    user_id: UUID,
    language: str,
) -> None:
    """Compose invocation (Mode 2 — agent-internal) and record evidence for deep-dive.

    ADR-048. Replaces the former placeholder-evidence path. Failures are
    logged and swallowed — analysis proceeds regardless.
    """
    from narrare._app.invocation_context import build_invocation_context
    from narrare_core.ai_invocation import compose_invocation

    deepdive_context = build_invocation_context(
        feature_id="analysis_beta_read_deepdive",
        intent=LLMIntent.BETA_READ,
        user_id=user_id,
        project_id=novel_id,
        language=language,
    )
    try:
        await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=deepdive_context,
            manual_injection=_BETA_READER_PHASE2_MANUAL_INJECTION,
        )
    except Exception:
        logger.warning(
            "invocation_composition_failed",
            feature_id="analysis_beta_read_deepdive",
            exc_info=True,
        )
