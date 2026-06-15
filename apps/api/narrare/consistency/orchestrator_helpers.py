"""Helper functions for staged consistency orchestration (ADR-044).

Keeps ``consistency_orchestrator.py`` focused on stage sequencing while this
module owns the shared response/dependency construction used by REST and SSE.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from narrare.consistency.rule_helpers import deduplicate_issues, rule_based_check
from narrare_core.agents.consistency_types import ConsistencyDeps
from narrare_core.ai_invocation import ManualInjectionDeclaration

if TYPE_CHECKING:
    from narrare.consistency.schemas import ConsistencyResponse
    from narrare_core.agents.fact_extractor_types import (
        FactExtractorOutput,
        TimelineEventEnvelope,
    )
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ModelRegistry, ResolvedModelConfig
    from narrare_core.prompts import PromptComposer


# ADR-048 Mode 2 declaration: Stage 2 ConsistencyAgent composes its prompt
# internally from enriched ConsistencyDeps (chapter texts, staged facts,
# timeline envelopes). Evidence is recorded at the stage-runner layer.
_STAGED_CHECK_INJECTION = ManualInjectionDeclaration(
    reason=(
        "Stage 2 ConsistencyAgent composes its prompt internally from enriched "
        "ConsistencyDeps (chapter texts, staged extracted facts, timeline envelopes)."
    ),
    variables=("chapter_text", "staged_facts", "timeline_events"),
    injection_mechanism="agent_deps",
)


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

    Returns:
        Final consistency response.
    """
    from narrare._app.invocation_context import safe_compose_invocation
    from narrare.consistency.prompt_builder import compose_consistency_prompt
    from narrare.consistency.schemas import ConsistencyResponse
    from narrare_core.agents.consistency_agent import ConsistencyAgent
    from narrare_core.llm.intents import LLMIntent

    enriched_deps = build_enriched_deps(deps, fact_output, timeline_envelopes)
    system_prompt, user_prompt = await compose_consistency_prompt(
        composer,
        language,
        enriched_deps,
        enriched_deps.check_types,
        max_chapter_tokens=max_chapter_tokens,
    )

    model = await registry.get_model(consistency_config)
    agent = ConsistencyAgent(model=model, system_prompt=system_prompt)
    await safe_compose_invocation(
        invocation_pipeline,
        feature_id="consistency_staged_check",
        intent=LLMIntent.CONSISTENCY,
        project_id=novel_id,
        manual_injection=_STAGED_CHECK_INJECTION,
    )
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
