"""Runtime task for ADR-044 staged consistency evals."""

from __future__ import annotations

from typing import TYPE_CHECKING

from evals.consistency_models import StagedConsistencyInput, StagedConsistencyResult
from narrare_core.agents.consistency_types import ConsistencyDeps
from narrare_core.agents.fact_extractor_types import FactExtractorDeps
from narrare_core.llm import LLMIntent
from narrare_core.prompts import PromptComposer, PromptContext
from narrare_core.prompts.registry import PromptRegistry

if TYPE_CHECKING:
    from narrare_core.llm import ResolvedModelConfig


async def consistency_staged_task(
    inputs: object,
    *,
    config: ResolvedModelConfig,
    api_key: str | None,
    base_url: str | None,
) -> object:
    """Run staged consistency through Narrare agent/runtime abstractions."""

    case = StagedConsistencyInput.model_validate(inputs)
    return await consistency_staged(
        case,
        config=config,
        api_key=api_key,
        base_url=base_url,
    )


async def consistency_staged(
    inputs: StagedConsistencyInput,
    *,
    config: ResolvedModelConfig,
    api_key: str | None,
    base_url: str | None,
) -> StagedConsistencyResult:
    """Run the selected ADR-044 stage with a real configured model."""

    from narrare_core.agents.consistency_agent import ConsistencyAgent
    from narrare_core.agents.fact_extractor_agent import FactExtractorAgent
    from narrare_core.llm import ModelRegistry

    registry = ModelRegistry()
    model = await registry.get_model(config, api_key=api_key, base_url=base_url)
    composer = PromptComposer(registry=PromptRegistry())
    facts = inputs.extracted_facts
    if inputs.stage in {"fact_extraction", "end_to_end"}:
        prompt_context = PromptContext(
            language=inputs.language,
            genre=inputs.genre,
            mode="fact_extraction",
        )
        composed = await composer.build(LLMIntent.FACT_EXTRACT, prompt_context)
        extractor = FactExtractorAgent(model=model, system_prompt=composed.system)
        extraction = await extractor.run(
            prompt=composed.user,
            deps=FactExtractorDeps(
                chapter_texts=inputs.chapter_texts,
                kb_entity_names=inputs.kb_entity_names,
                kb_entity_summaries=inputs.kb_entity_summaries,
                timeline_envelopes=inputs.timeline_envelopes,
                language=inputs.language,
                genre=inputs.genre,
            ),
        )
        facts = extraction.facts
        if inputs.stage == "fact_extraction":
            return StagedConsistencyResult(
                extracted_facts=facts,
                issues=[],
                overall_assessment=extraction.assessment_summary,
            )

    consistency_prompt = await composer.build(
        LLMIntent.CONSISTENCY,
        PromptContext(language=inputs.language, genre=inputs.genre, mode="consistency"),
    )
    consistency = ConsistencyAgent(model=model, system_prompt=consistency_prompt.system)
    output = await consistency.run(
        prompt=consistency_prompt.user,
        deps=ConsistencyDeps(
            language=inputs.language,
            chapter_texts=inputs.chapter_texts,
            kb_entity_summaries=inputs.kb_entity_summaries,
            check_types=inputs.check_types,
            extracted_facts=facts,
            timeline_envelopes=inputs.timeline_envelopes,
        ),
    )
    return StagedConsistencyResult(
        extracted_facts=facts,
        issues=output.issues,
        overall_assessment=output.overall_assessment,
    )
