"""ADR-048 Mode 2 invocation declaration for the KB consistency LLM phases.

Extracted from ``consistency_service.py`` (IDOR fix S9, RULE-04) — the
declaration is a static, self-contained evidence concern, distinct from
the orchestration logic. One responsibility (RULE-06): describe HOW the
consistency LLM phases compose their prompts so the invocation pipeline
can record evidence for them.

The composition call itself lives here too (moved from
``consistency_service.py`` in ADR-086 L15 for the same RULE-04 limit):
same behavior, only the module home changed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.ai_invocation import ManualInjectionDeclaration

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.ai_invocation.pipeline import InvocationPipeline

logger = structlog.get_logger(__name__)

# KBConsistencyAnalyzer and WorldbuildingAnalyzer compose their prompts
# internally from deps (entity summaries, template structures, existing
# relationships). Evidence is recorded at the parent service layer,
# covering both Phase 2 (entry-internal) and Phase 3 (cross-entity) LLM
# calls.
CONSISTENCY_MANUAL_INJECTION = ManualInjectionDeclaration(
    reason=(
        "KBConsistencyAnalyzer and WorldbuildingAnalyzer compose their prompts "
        "internally from deps (entity summaries, template structures, "
        "existing relationships). See ADR-044 staged consistency pipeline."
    ),
    variables=("entity_summaries", "template_structures", "existing_relationships"),
    injection_mechanism="agent_deps",
)


async def compose_consistency_invocation(
    *,
    invocation_pipeline: InvocationPipeline | None,
    novel_id: UUID,
) -> None:
    """Record invocation evidence for the consistency LLM phases (ADR-048).

    Mode 2 (agent-internal): declares the manual injection and composes
    the invocation so the pipeline can record evidence for Phase 2
    (entry-internal) and Phase 3 (cross-entity).

    Best-effort (RULE-11): composition failure is logged and swallowed —
    evidence loss must never fail the consistency check.
    """
    from narrare._app.invocation_context import build_invocation_context
    from narrare_core.ai_invocation import compose_invocation
    from narrare_core.llm.intents import LLMIntent

    invocation_context = build_invocation_context(
        feature_id="kb_consistency",
        intent=LLMIntent.KB_CONSISTENCY,
        project_id=novel_id,
    )
    try:
        await compose_invocation(
            invocation_pipeline=invocation_pipeline,
            invocation_context=invocation_context,
            manual_injection=CONSISTENCY_MANUAL_INJECTION,
        )
    except Exception:
        logger.warning(
            "invocation_composition_failed",
            feature_id="kb_consistency",
            exc_info=True,
        )
