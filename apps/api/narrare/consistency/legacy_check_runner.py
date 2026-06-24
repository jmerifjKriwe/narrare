"""Legacy single-pass consistency check runner (RULE-04 extraction).

Extracted from :mod:`narrare.consistency.checker_service` to keep that
file under the 300-line service limit. Owns the legacy (non-staged)
``ConsistencyAgent`` invocation path: compose prompt → run agent →
deduplicate issues → build response.

Parallel to :func:`narrare.consistency.orchestrator_helpers.run_consistency_stage`,
which owns the staged (ADR-044) path.

See:
    :class:`narrare.consistency.checker_service.ConsistencyCheckerService`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.consistency.schemas import ConsistencyResponse
from narrare_core.agents.consistency_agent import ConsistencyAgent

if TYPE_CHECKING:
    import uuid

    from narrare.consistency.checker_context import CheckContext
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ModelRegistry, ResolvedModelConfig
    from narrare_core.prompts import PromptComposer

logger = structlog.get_logger(__name__)


async def run_legacy_check(
    *,
    registry: ModelRegistry,
    config: ResolvedModelConfig,
    composer: PromptComposer,
    novel_id: uuid.UUID,
    context: CheckContext,
    invocation_pipeline: InvocationPipeline | None = None,
) -> ConsistencyResponse:
    """Run the legacy single-pass consistency check.

    Args:
        registry: ModelRegistry for LLM model resolution.
        config: Resolved model config for the CONSISTENCY intent.
        composer: PromptComposer for system/user prompt assembly.
        novel_id: The novel being checked.
        context: Collected check context (chapters, KB, rule issues).
        invocation_pipeline: Optional InvocationPipeline for evidence recording.

    Returns:
        ConsistencyResponse with deduplicated issues from rules + LLM.
    """
    from datetime import UTC, datetime

    from narrare._app.invocation_context import build_invocation_context
    from narrare.consistency.prompt_builder import build_consistency_prompt_context
    from narrare.consistency.rule_helpers import deduplicate_issues
    from narrare_core.ai_invocation import compose_invocation
    from narrare_core.llm.intents import LLMIntent

    prompt_context = build_consistency_prompt_context(
        context.language,
        context.deps,
        context.deps.check_types,
        max_chapter_tokens=context.max_chapter_tokens,
    )
    invocation_context = build_invocation_context(
        feature_id="consistency_check",
        intent=LLMIntent.CONSISTENCY,
        project_id=novel_id,
    )
    try:
        invocation_result = await compose_invocation(
            invocation_pipeline=invocation_pipeline,
            invocation_context=invocation_context,
            composer=composer,
            prompt_context=prompt_context,
            intent=LLMIntent.CONSISTENCY,
        )
        assert invocation_result.composed_prompt is not None  # Mode 1 always composes
        system_prompt = invocation_result.composed_prompt.system
        user_prompt = invocation_result.composed_prompt.user
    except Exception:
        logger.warning(
            "invocation_composition_failed",
            feature_id="consistency_check",
            exc_info=True,
        )
        composed = await composer.build(LLMIntent.CONSISTENCY, prompt_context)
        system_prompt = composed.system
        user_prompt = composed.user

    model = await registry.get_model(config)
    agent = ConsistencyAgent(model=model, system_prompt=system_prompt)
    result = await agent.run(prompt=user_prompt, deps=context.deps)

    all_issues = context.rule_issues + result.issues
    deduped_issues = deduplicate_issues(all_issues)

    now = datetime.now(tz=UTC).isoformat()
    return ConsistencyResponse(
        novel_id=novel_id,
        chapter_ids=context.resolved_ids,
        check_types=result.checked_types,
        issues=deduped_issues,
        overall_assessment=result.overall_assessment,
        analyzed_at=now,
    )
