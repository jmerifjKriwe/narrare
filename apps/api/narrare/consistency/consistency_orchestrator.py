"""Consistency orchestrator — staged pipeline sequencing (ADR-044).

Orchestrates the two-stage consistency pipeline:
1. FactExtractorAgent extracts structured facts with provenance.
2. ConsistencyAgent checks enriched facts for contradictions.

The external ``ConsistencyCheckerProtocol`` remains unchanged; this class is an
internal collaborator injected into ``ConsistencyCheckerService``.

ADR-086 L13: the per-stage model wiring is consumed as ``ModelResolution``
sems — one per intent (FACT_EXTRACT + CONSISTENCY, the S4b-dual shape) —
and resolves on first use (``ensure_resolved``), never at construction,
with the legacy temperature overrides (0.2 extractor / 0.3 checker)
composed once onto the RESOLVED cascade configs.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from narrare.consistency.orchestrator_helpers import run_consistency_stage
from narrare.consistency.stage_schemas import ConsistencyStageEvent
from narrare_core.agents.fact_extractor_types import (
    FactExtractorDeps,
    TimelineEventEnvelope,
)
from narrare_core.llm.run_limits import DefaultRunLimitResolver

if TYPE_CHECKING:
    import uuid
    from collections.abc import AsyncIterator

    from narrare._app.dependencies_services import ModelResolution
    from narrare.consistency.schemas import ConsistencyResponse
    from narrare_core.agents.consistency_types import ConsistencyDeps
    from narrare_core.agents.fact_extractor_types import FactExtractorOutput
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ModelRegistry, ResolvedModelConfig
    from narrare_core.prompts import PromptComposer

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class StagedModelConfigs:
    """Composed per-stage model wiring (ADR-086 L13).

    Both routing cascades resolve at the orchestrator's first use; the
    legacy temperature overrides (0.2 extractor / 0.3 checker) are
    applied exactly once here, on the RESOLVED cascade configs
    (``dataclasses.replace`` — model/provider routing stays intact).
    """

    fact_extractor_config: ResolvedModelConfig
    consistency_config: ResolvedModelConfig
    fact_extractor_api_key: str | None
    fact_extractor_base_url: str | None
    consistency_api_key: str | None
    consistency_base_url: str | None


class ConsistencyOrchestrator:
    """Orchestrate FactExtractorAgent → ConsistencyAgent.

    Args:
        registry: ModelRegistry for LLM model resolution.
        fact_extractor_resolution: Lazy FACT_EXTRACT cascade (ADR-086
            L13) — resolves at first use, never at construction.
        consistency_resolution: Lazy CONSISTENCY cascade (ADR-086 L13)
            for stage 2 (and the service's legacy fallback mirror).
        composer: PromptComposer for prompt cascade resolution.
        invocation_pipeline: Optional InvocationPipeline for evidence recording.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        fact_extractor_resolution: ModelResolution,
        consistency_resolution: ModelResolution,
        composer: PromptComposer,
        invocation_pipeline: InvocationPipeline | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        self._registry = registry
        self._fact_extractor_resolution = fact_extractor_resolution
        self._consistency_resolution = consistency_resolution
        self._composer = composer
        self._invocation_pipeline = invocation_pipeline
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()
        self._configs: StagedModelConfigs | None = None

    async def ensure_resolved(self) -> StagedModelConfigs:
        """Resolve BOTH routing cascades at first use (ADR-086 L13).

        Idempotent: the composed configs are cached and the underlying
        ``LazyModelResolution``s cache their cascade results. The eager
        factory's cascade call order is preserved verbatim: FACT_EXTRACT
        first, CONSISTENCY second. ``ConfigurationError`` propagates
        loudly (RULE-11 — consistency endpoints are AI-mandatory).
        """
        if self._configs is None:
            fact_resolved = await self._fact_extractor_resolution.resolve()
            consistency_resolved = await self._consistency_resolution.resolve()
            # Legacy temperature overrides preserved on the RESOLVED
            # cascade configs (dataclasses.replace — routing intact).
            self._configs = StagedModelConfigs(
                fact_extractor_config=replace(fact_resolved.config, temperature=0.2),
                consistency_config=replace(consistency_resolved.config, temperature=0.3),
                fact_extractor_api_key=fact_resolved.api_key,
                fact_extractor_base_url=fact_resolved.base_url,
                consistency_api_key=consistency_resolved.api_key,
                consistency_base_url=consistency_resolved.base_url,
            )
        return self._configs

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
        configs = await self.ensure_resolved()
        fact_output = await self._run_fact_extraction(
            deps=deps,
            kb_summaries=kb_summaries,
            timeline_envelopes=timeline_envelopes,
            language=language,
            configs=configs,
        )
        logger.info(
            "consistency_stage1_complete",
            novel_id=str(novel_id),
            fact_count=len(fact_output.facts),
        )
        return await run_consistency_stage(
            registry=self._registry,
            consistency_config=configs.consistency_config,
            composer=self._composer,
            novel_id=novel_id,
            deps=deps,
            kb_summaries=kb_summaries,
            timeline_envelopes=timeline_envelopes,
            language=language,
            max_chapter_tokens=max_chapter_tokens,
            fact_output=fact_output,
            invocation_pipeline=self._invocation_pipeline,
            api_key=configs.consistency_api_key,
            base_url=configs.consistency_base_url,
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
        configs = await self.ensure_resolved()
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
            configs=configs,
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
            consistency_config=configs.consistency_config,
            composer=self._composer,
            novel_id=novel_id,
            deps=deps,
            kb_summaries=kb_summaries,
            timeline_envelopes=timeline_envelopes,
            language=language,
            max_chapter_tokens=max_chapter_tokens,
            fact_output=fact_output,
            invocation_pipeline=self._invocation_pipeline,
            api_key=configs.consistency_api_key,
            base_url=configs.consistency_base_url,
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
        configs: StagedModelConfigs,
    ) -> FactExtractorOutput:
        """Run Stage 1: FactExtractorAgent.

        Args:
            deps: ConsistencyDeps with chapter texts.
            kb_summaries: KB entity summaries.
            timeline_envelopes: Enriched timeline events.
            language: Output language.
            configs: Composed per-stage model wiring (resolved at the
                orchestrator's first use — ADR-086 L13).

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
        # policy actually reaches this call.
        resolved = self._run_limit_resolver.resolve(
            config=configs.fact_extractor_config, budget=None, invocation_id=uuid4()
        )
        prepared = await self._registry.prepare(
            configs.fact_extractor_config,
            intent=LLMIntent.FACT_EXTRACT,
            usage_limits=resolved.usage_limits,
            api_key=configs.fact_extractor_api_key,
            base_url=configs.fact_extractor_base_url,
        )
        agent = FactExtractorAgent(model=prepared.model, system_prompt=system_prompt)
        return await agent.run(
            prompt=user_prompt,
            deps=extractor_deps,
            model_settings=prepared.model_settings,
            usage_limits=prepared.usage_limits,
        )
