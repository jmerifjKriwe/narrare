"""Consistency orchestrator — staged pipeline sequencing (ADR-044).

Orchestrates the two-stage consistency pipeline:
1. FactExtractorAgent extracts structured facts with provenance.
2. ConsistencyAgent checks enriched facts for contradictions.

The external ``ConsistencyCheckerProtocol`` remains unchanged; this class is an
internal collaborator injected into ``ConsistencyCheckerService``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.consistency.orchestrator_helpers import run_consistency_stage
from narrare.consistency.stage_schemas import ConsistencyStageEvent
from narrare_core.agents.fact_extractor_types import (
    FactExtractorDeps,
    TimelineEventEnvelope,
)

if TYPE_CHECKING:
    import uuid
    from collections.abc import AsyncIterator

    from narrare.consistency.schemas import ConsistencyResponse
    from narrare_core.agents.consistency_types import ConsistencyDeps
    from narrare_core.agents.fact_extractor_types import FactExtractorOutput
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ModelRegistry, ResolvedModelConfig
    from narrare_core.prompts import PromptComposer

logger = structlog.get_logger(__name__)


class ConsistencyOrchestrator:
    """Orchestrate FactExtractorAgent → ConsistencyAgent.

    Args:
        registry: ModelRegistry for LLM model resolution.
        fact_extractor_config: ResolvedModelConfig for FACT_EXTRACT intent.
        consistency_config: ResolvedModelConfig for CONSISTENCY intent.
        composer: PromptComposer for prompt cascade resolution.
        invocation_pipeline: Optional InvocationPipeline for evidence recording.
        fact_extractor_api_key: Optional per-user provider API key for the
            FACT_EXTRACT stage (model-routing cascade).
        fact_extractor_base_url: Optional per-user provider base URL for the
            FACT_EXTRACT stage.
        consistency_api_key: Optional per-user provider API key for the
            CONSISTENCY stage (model-routing cascade).
        consistency_base_url: Optional per-user provider base URL for the
            CONSISTENCY stage.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        fact_extractor_config: ResolvedModelConfig,
        consistency_config: ResolvedModelConfig,
        composer: PromptComposer,
        invocation_pipeline: InvocationPipeline | None = None,
        fact_extractor_api_key: str | None = None,
        fact_extractor_base_url: str | None = None,
        consistency_api_key: str | None = None,
        consistency_base_url: str | None = None,
    ) -> None:
        self._registry = registry
        self._fact_extractor_config = fact_extractor_config
        self._consistency_config = consistency_config
        self._composer = composer
        self._invocation_pipeline = invocation_pipeline
        self._fact_extractor_api_key = fact_extractor_api_key
        self._fact_extractor_base_url = fact_extractor_base_url
        self._consistency_api_key = consistency_api_key
        self._consistency_base_url = consistency_base_url

    async def run_staged_check(
        self,
        *,
        novel_id: uuid.UUID,
        deps: ConsistencyDeps,
        kb_summaries: list[dict[str, object]],
        timeline_envelopes: list[TimelineEventEnvelope],
        language: str,
        max_chapter_tokens: int,
    ) -> ConsistencyResponse:
        """Run the full staged pipeline and return the final response.

        Args:
            novel_id: The novel being checked.
            deps: ConsistencyDeps with chapter texts and check configuration.
            kb_summaries: KB entity summaries for context.
            timeline_envelopes: Enriched timeline events with provenance.
            language: Output language.
            max_chapter_tokens: Token budget per chapter.

        Returns:
            Consistency response with issues grouped by severity and type.
        """
        fact_output = await self._run_fact_extraction(
            deps=deps,
            kb_summaries=kb_summaries,
            timeline_envelopes=timeline_envelopes,
            language=language,
        )
        logger.info(
            "consistency_stage1_complete",
            novel_id=str(novel_id),
            fact_count=len(fact_output.facts),
        )
        return await run_consistency_stage(
            registry=self._registry,
            consistency_config=self._consistency_config,
            composer=self._composer,
            novel_id=novel_id,
            deps=deps,
            kb_summaries=kb_summaries,
            timeline_envelopes=timeline_envelopes,
            language=language,
            max_chapter_tokens=max_chapter_tokens,
            fact_output=fact_output,
            invocation_pipeline=self._invocation_pipeline,
            api_key=self._consistency_api_key,
            base_url=self._consistency_base_url,
        )

    async def stream_staged_check(
        self,
        *,
        novel_id: uuid.UUID,
        deps: ConsistencyDeps,
        kb_summaries: list[dict[str, object]],
        timeline_envelopes: list[TimelineEventEnvelope],
        language: str,
        max_chapter_tokens: int,
    ) -> AsyncIterator[ConsistencyStageEvent | ConsistencyResponse]:
        """Stream stage progress events and final response (RULE-13).

        Args:
            novel_id: The novel being checked.
            deps: ConsistencyDeps with chapter texts and check configuration.
            kb_summaries: KB entity summaries for context.
            timeline_envelopes: Enriched timeline events with provenance.
            language: Output language.
            max_chapter_tokens: Token budget per chapter.

        Yields:
            Stage events during processing, then final ConsistencyResponse.
        """
        yield ConsistencyStageEvent(
            stage="extracting_facts",
            status="start",
            progress=0.0,
            message="Extracting facts from chapters, KB, and timeline.",
        )
        fact_output = await self._run_fact_extraction(
            deps=deps,
            kb_summaries=kb_summaries,
            timeline_envelopes=timeline_envelopes,
            language=language,
        )
        yield ConsistencyStageEvent(
            stage="extracting_facts",
            status="complete",
            progress=1.0,
            message="Fact extraction complete.",
            facts_extracted=len(fact_output.facts),
        )
        yield ConsistencyStageEvent(
            stage="checking_consistency",
            status="start",
            progress=0.0,
            message="Checking extracted facts for contradictions.",
            facts_extracted=len(fact_output.facts),
        )
        response = await run_consistency_stage(
            registry=self._registry,
            consistency_config=self._consistency_config,
            composer=self._composer,
            novel_id=novel_id,
            deps=deps,
            kb_summaries=kb_summaries,
            timeline_envelopes=timeline_envelopes,
            language=language,
            max_chapter_tokens=max_chapter_tokens,
            fact_output=fact_output,
            invocation_pipeline=self._invocation_pipeline,
            api_key=self._consistency_api_key,
            base_url=self._consistency_base_url,
        )
        for index, issue in enumerate(response.issues, start=1):
            yield ConsistencyStageEvent(
                stage="checking_consistency",
                status="issue",
                progress=index / max(response.total_issues, 1),
                message="Consistency issue found.",
                facts_extracted=len(fact_output.facts),
                issues_found=index,
                issue=issue,
            )
        yield ConsistencyStageEvent(
            stage="checking_consistency",
            status="complete",
            progress=1.0,
            message="Consistency checking complete.",
            facts_extracted=len(fact_output.facts),
            issues_found=response.total_issues,
        )
        yield ConsistencyStageEvent(
            stage="complete",
            status="complete",
            progress=1.0,
            message="Staged consistency pipeline complete.",
            facts_extracted=len(fact_output.facts),
            issues_found=response.total_issues,
        )
        yield response

    async def _run_fact_extraction(
        self,
        deps: ConsistencyDeps,
        kb_summaries: list[dict[str, object]],
        timeline_envelopes: list[TimelineEventEnvelope],
        language: str,
    ) -> FactExtractorOutput:
        """Run Stage 1: FactExtractorAgent.

        Args:
            deps: ConsistencyDeps with chapter texts.
            kb_summaries: KB entity summaries.
            timeline_envelopes: Enriched timeline events.
            language: Output language.

        Returns:
            Structured fact extraction output with provenance-traced facts.
        """
        from narrare._app.invocation_context import build_invocation_context
        from narrare_core.agents.fact_extractor_agent import FactExtractorAgent
        from narrare_core.ai_invocation import compose_invocation
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.prompts.context import PromptContext

        entity_names = [
            str(entity.get("name", ""))
            for entity in kb_summaries
            if str(entity.get("name", "")).strip()
        ]
        extractor_deps = FactExtractorDeps(
            chapter_texts=deps.chapter_texts,
            kb_entity_names=entity_names,
            kb_entity_summaries=kb_summaries,
            timeline_envelopes=timeline_envelopes,
            language=language,
        )
        prompt_context = PromptContext(
            language=language,
            mode="fact_extraction",
            project_title="",
        )
        invocation_context = build_invocation_context(
            feature_id="consistency_fact_extraction",
            intent=LLMIntent.FACT_EXTRACT,
            project_id=deps.novel_id,
        )
        try:
            invocation_result = await compose_invocation(
                invocation_pipeline=self._invocation_pipeline,
                invocation_context=invocation_context,
                composer=self._composer,
                prompt_context=prompt_context,
                intent=LLMIntent.FACT_EXTRACT,
            )
            assert invocation_result.composed_prompt is not None  # Mode 1 always composes
            system_prompt = invocation_result.composed_prompt.system
            user_prompt = invocation_result.composed_prompt.user
        except Exception:
            logger.warning(
                "invocation_composition_failed",
                feature_id="consistency_fact_extraction",
                exc_info=True,
            )
            composed = await self._composer.build(LLMIntent.FACT_EXTRACT, prompt_context)
            system_prompt = composed.system
            user_prompt = composed.user

        # Single assembly point (Task 6b — Task 4/5 pattern): model + intent-aware
        # runtime settings + usage limits as one coherent triple, so the thinking
        # policy actually reaches this call. No run-limit resolver is wired on
        # this path, so ``usage_limits`` is ``None`` (no output caps).
        prepared = await self._registry.prepare(
            self._fact_extractor_config,
            intent=LLMIntent.FACT_EXTRACT,
            api_key=self._fact_extractor_api_key,
            base_url=self._fact_extractor_base_url,
        )
        agent = FactExtractorAgent(model=prepared.model, system_prompt=system_prompt)
        return await agent.run(
            prompt=user_prompt,
            deps=extractor_deps,
            model_settings=prepared.model_settings,
            usage_limits=prepared.usage_limits,
        )
