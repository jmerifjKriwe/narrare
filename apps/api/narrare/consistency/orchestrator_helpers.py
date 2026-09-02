"""Helper functions for staged consistency orchestration (ADR-044).

Keeps ``consistency_orchestrator.py`` focused on stage sequencing while this
module owns the shared response/dependency construction used by REST and SSE.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from narrare.consistency.rule_helpers import deduplicate_issues, rule_based_check
from narrare_core.agents.consistency_types import ConsistencyDeps

if TYPE_CHECKING:
    from narrare.consistency.schemas import ConsistencyResponse
    from narrare_core.agents.fact_extractor_types import (
        FactExtractorOutput,
        TimelineEventEnvelope,
    )
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ModelRegistry, ResolvedModelConfig
    from narrare_core.prompts import PromptComposer

logger = structlog.get_logger(__name__)


def build_enriched_deps(
    deps: ConsistencyDeps,
    fact_output: FactExtractorOutput,
    timeline_envelopes: list[TimelineEventEnvelope],
) -> ConsistencyDeps:
    """Build Stage 2 deps with structured Stage 1 output.

    Args:
        deps: Base consistency dependencies collected by the service.
        fact_output: Structured facts extracted in Stage 1.
        timeline_envelopes: Enriched timeline envelopes.

    Returns:
        ConsistencyDeps carrying extracted facts and timeline envelopes.
    """
    return ConsistencyDeps(
        language=deps.language,
        novel_id=deps.novel_id,
        chapter_texts=deps.chapter_texts,
        kb_entity_summaries=deps.kb_entity_summaries,
        timeline_events=deps.timeline_events,
        check_types=deps.check_types,
        existing_issue_count=deps.existing_issue_count,
        extracted_facts=fact_output.facts,
        timeline_envelopes=timeline_envelopes,
    )


async def run_consistency_stage(
    *,
    registry: ModelRegistry,
    consistency_config: ResolvedModelConfig,
    composer: PromptComposer,
    novel_id: uuid.UUID,
    deps: ConsistencyDeps,
    kb_summaries: list[dict[str, object]],
    timeline_envelopes: list[TimelineEventEnvelope],
    language: str,
    max_chapter_tokens: int,
    fact_output: FactExtractorOutput,
    invocation_pipeline: InvocationPipeline | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> ConsistencyResponse:
    """Run Stage 2 and map output to ``ConsistencyResponse``.

    Args:
        registry: Model registry used to resolve the consistency model.
        consistency_config: Model config for the consistency intent.
        composer: Prompt composer for cascade prompt resolution.
        novel_id: The novel being checked.
        deps: Base consistency dependencies.
        kb_summaries: KB summaries for rule-based and LLM analysis.
        timeline_envelopes: Enriched timeline data.
        language: Output language.
        max_chapter_tokens: Token budget per chapter preview.
        fact_output: Structured Stage 1 output.
        invocation_pipeline: Optional InvocationPipeline for evidence recording.
        api_key: Optional per-user provider API key override (model-routing
            cascade) — reaches the ``registry.get_model`` resolution point.
        base_url: Optional per-user provider base URL override.

    Returns:
        Final consistency response.
    """
    from narrare._app.invocation_context import build_invocation_context
    from narrare.consistency.prompt_builder import build_consistency_prompt_context
    from narrare.consistency.schemas import ConsistencyResponse
    from narrare_core.agents.consistency_agent import ConsistencyAgent
    from narrare_core.ai_invocation import compose_invocation
    from narrare_core.llm.intents import LLMIntent

    enriched_deps = build_enriched_deps(deps, fact_output, timeline_envelopes)
    prompt_context = build_consistency_prompt_context(
        language,
        enriched_deps,
        enriched_deps.check_types,
        max_chapter_tokens=max_chapter_tokens,
    )
    invocation_context = build_invocation_context(
        feature_id="consistency_staged_check",
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
            feature_id="consistency_staged_check",
            exc_info=True,
        )
        composed = await composer.build(LLMIntent.CONSISTENCY, prompt_context)
        system_prompt = composed.system
        user_prompt = composed.user

    model = await registry.get_model(
        consistency_config,
        api_key=api_key,
        base_url=base_url,
    )
    agent = ConsistencyAgent(model=model, system_prompt=system_prompt)
    result = await agent.run(prompt=user_prompt, deps=enriched_deps)
    issues = deduplicate_issues(rule_based_check(kb_summaries) + result.issues)

    return ConsistencyResponse(
        novel_id=novel_id,
        chapter_ids=[uuid.UUID(chapter_id) for chapter_id in deps.chapter_texts],
        check_types=result.checked_types,
        issues=issues,
        overall_assessment=result.overall_assessment,
        analyzed_at=datetime.now(tz=UTC).isoformat(),
    )
