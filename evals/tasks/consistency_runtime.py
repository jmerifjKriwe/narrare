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
    from narrare_core.agents.consistency_triage_types import TriageAssessment
    from narrare_core.agents.consistency_types import ConsistencyIssue, ConsistencyOutput
    from narrare_core.agents.fact_extractor_types import (
        ExtractedFact,
        TimelineEventEnvelope,
    )
    from narrare_core.llm import ModelRegistry, ResolvedModelConfig


def _chapter_texts_var(chapter_texts: dict[str, str]) -> str:
    """Format chapter texts as a template variable (API prompt_builder pattern)."""
    parts = [f"### Chapter {ch_id}\n{text}\n" for ch_id, text in chapter_texts.items()]
    return "\n".join(parts).strip()


def _kb_entities_var(summaries: list[dict[str, object]]) -> str:
    """Format KB entity summaries as a template variable."""
    return "\n".join(
        f"- [{e.get('entity_type', 'unknown')}] {e.get('name', 'unnamed')}: {e.get('fields', {})}"
        for e in summaries
    )


def _extracted_facts_var(facts: list[ExtractedFact]) -> str:
    """Format Stage 1 facts as a template variable (provenance per template v2.1.0)."""
    return "\n".join(
        f"- [ch {f.chapter_id}] {f.subject} {f.predicate} {f.object_value} "
        f"({f.fact_type}, conf {f.confidence})"
        for f in facts
    )


def _timeline_position_var(envelopes: list[TimelineEventEnvelope]) -> str:
    """Format timeline envelopes as a template variable (temporal ordering context)."""
    return "\n".join(
        f'- [{e.timestamp_raw}] "{e.event_name}" (order {e.temporal_order}, {e.source_chapter_id})'
        for e in envelopes
    )


def _fact_extraction_variables(inputs: StagedConsistencyInput) -> dict[str, str]:
    """Required + data-bearing FACT_EXTRACT route variables (Core-only Mode 1).

    The bundled template requires chapter_texts / kb_characters / kb_factions /
    kb_locations / kb_relationships; without extras the composer raises
    PromptVariableError (pre-existing runtime-task defect fixed here).
    """

    return {
        "chapter_texts": _chapter_texts_var(inputs.chapter_texts),
        "kb_characters": "",
        "kb_factions": "",
        "kb_locations": "",
        "kb_relationships": "",
        "kb_entities": _kb_entities_var(inputs.kb_entity_summaries),
        "existing_entity_names": ", ".join(inputs.kb_entity_names),
    }


def _consistency_variables(
    inputs: StagedConsistencyInput, facts: list[ExtractedFact]
) -> dict[str, str]:
    """Required + data-bearing CONSISTENCY route variables (Core-only Mode 1)."""

    return {
        "chapter_texts": _chapter_texts_var(inputs.chapter_texts),
        "kb_entities": _kb_entities_var(inputs.kb_entity_summaries),
        "kb_relationships": "",
        "check_types": ", ".join(t.value for t in inputs.check_types),
        "timeline_position": _timeline_position_var(inputs.timeline_envelopes),
        "extracted_facts": _extracted_facts_var(facts),
    }


async def consistency_staged_task(
    inputs: object,
    *,
    config: ResolvedModelConfig,
    api_key: str | None,
    base_url: str | None,
    triage_config: ResolvedModelConfig | None = None,
    triage_api_key: str | None = None,
) -> object:
    """Run staged consistency through Narrare agent/runtime abstractions."""

    case = StagedConsistencyInput.model_validate(inputs)
    return await consistency_staged(
        case,
        config=config,
        api_key=api_key,
        base_url=base_url,
        triage_config=triage_config,
        triage_api_key=triage_api_key,
    )


async def consistency_staged(
    inputs: StagedConsistencyInput,
    *,
    config: ResolvedModelConfig,
    api_key: str | None,
    base_url: str | None,
    triage_config: ResolvedModelConfig | None = None,
    triage_api_key: str | None = None,
) -> StagedConsistencyResult:
    """Run the selected ADR-044 stage with a real configured model.

    When *triage_config* is set (env ``NARRARE_EVAL_TRIAGE_MODEL``), the
    consistency output is additionally re-scored by the decision-pattern
    triage agent; raw and triaged variants are both attached to the
    result for the pilot measurement. Detection scoring stays on the raw
    issues so scores remain comparable with triage disabled.
    """

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
            extra=_fact_extraction_variables(inputs),
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
        PromptContext(
            language=inputs.language,
            genre=inputs.genre,
            mode="consistency",
            extra=_consistency_variables(inputs, facts),
        ),
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
    result = StagedConsistencyResult(
        extracted_facts=facts,
        issues=output.issues,
        overall_assessment=output.overall_assessment,
    )
    if triage_config is not None:
        triaged_issues, assessments = await _triage_issues(
            output,
            registry=registry,
            triage_config=triage_config,
            triage_api_key=triage_api_key,
            base_url=base_url,
            language=inputs.language,
        )
        result = result.model_copy(
            update={
                "triaged": True,
                "triaged_issues": triaged_issues,
                "triage_assessments": assessments,
            }
        )
    return result


async def _triage_issues(
    output: ConsistencyOutput,
    *,
    registry: ModelRegistry,
    triage_config: ResolvedModelConfig,
    triage_api_key: str | None,
    base_url: str | None,
    language: str,
) -> tuple[list[ConsistencyIssue], list[TriageAssessment]]:
    """Re-score detected issues via ConsistencyTriageAgent (decision-pattern pilot).

    Returns the triaged issues (NO_ISSUE assessments dropped, severity and
    confidence re-mapped by ``apply_triage``) plus the raw rubric
    assessments for the pilot report. Empty issues skip the model call —
    there is nothing to re-score.
    """

    from narrare_core.agents.consistency_triage_agent import (
        ConsistencyTriageAgent,
        build_triage_prompt,
    )
    from narrare_core.agents.consistency_triage_types import (
        ConsistencyTriageDeps,
        apply_triage,
    )

    if not output.issues:
        return [], []

    model = await registry.get_model(triage_config, api_key=triage_api_key, base_url=base_url)
    deps = ConsistencyTriageDeps(language=language, issues=output.issues)
    agent = ConsistencyTriageAgent(model=model)
    triage_output = await agent.run(prompt=build_triage_prompt(deps), deps=deps)
    triaged = apply_triage(output, triage_output)
    return triaged.issues, triage_output.assessments
