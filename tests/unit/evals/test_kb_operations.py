"""Unit tests for the kb_operations eval suite (dataset + evaluators)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from evals.datasets.kb_operations import build_dataset
from evals.evaluators import (
    KBAgentOperationSchemaValidator,
    KBAssistSchemaValidator,
    KBImproveSchemaValidator,
    KBMergeSchemaValidator,
)
from evals.models import (
    KBAgentOperationSection,
    KBAssistSection,
    KBImproveSection,
    KBImproveSuggestionSection,
    KBMergeDecisionSection,
    KBMergeSection,
    KBMergeStrategySection,
    KBOperationsInput,
    KBOperationsResult,
)
from evals.tasks.kb_operations_smoke import kb_operations as run_kb_operations_smoke
from pydantic import ValidationError

from narrare_core.agents.kb_assist_types import KBAssistOutput
from narrare_core.agents.kb_improve_types import SuggestionType
from narrare_core.agents.merge_types import MergeDecision, MergeOutput

if TYPE_CHECKING:
    from pydantic_evals.evaluators import EvaluatorContext


@dataclass(frozen=True)
class DummyContext:
    """Small evaluator context double with only fields our evaluators read."""

    output: Any
    metadata: dict[str, Any] | None = None


def test_kb_operations_dataset_has_expected_case_mix() -> None:
    dataset = build_dataset()

    assert dataset.name == "kb_operations"
    assert _count_agent_types(dataset) == {
        "kb_agent": 3,
        "kb_assist": 4,
        "kb_improve": 3,
        "kb_merge": 3,
    }


def test_kb_operations_dataset_registers_in_factory() -> None:
    from evals.datasets import DATASET_FACTORIES

    assert "kb_operations" in DATASET_FACTORIES
    assert DATASET_FACTORIES["kb_operations"] is build_dataset


def test_kb_operations_suite_available_in_cli_order() -> None:
    from evals.datasets import available_suites

    assert "kb_operations" in available_suites()


async def test_smoke_kb_agent_routes_lookup_intent_to_entity_operation() -> None:
    result = await run_kb_operations_smoke(
        KBOperationsInput(
            agent_type="kb_agent",
            prompt_text="Get details for Mara Silverwood before the council scene.",
            entity_type="character",
        )
    )

    assert isinstance(result, KBOperationsResult)
    assert result.kb_agent is not None
    assert result.kb_assist is None
    assert result.kb_agent.operation == "get_entity"
    assert result.kb_agent.entity_name == "Mara Silverwood"
    assert result.kb_agent.formatted_response.startswith("Entity:")


async def test_smoke_kb_agent_routes_related_intent_to_relationship_operation() -> None:
    result = await run_kb_operations_smoke(
        KBOperationsInput(
            agent_type="kb_agent",
            prompt_text="Find related entities for Iron Guild allies.",
            entity_type="faction",
        )
    )

    assert result.kb_agent is not None
    assert result.kb_agent.operation == "get_related_entities"
    assert result.kb_agent.entity_name == "Iron Guild"
    assert "related to" in result.kb_agent.formatted_response


async def test_smoke_kb_assist_produces_question_answer_pair_structure() -> None:
    result = await run_kb_operations_smoke(
        KBOperationsInput(
            agent_type="kb_assist",
            prompt_text="Ask the next question about Mara's motivation.",
            entity_type="character",
            field_key="motivation",
        )
    )

    assert result.kb_assist is not None
    assert result.kb_assist.mode == "question"
    assert result.kb_assist.field_key == "motivation"
    assert result.kb_assist.question is not None and result.kb_assist.question.endswith("?")
    assert result.kb_assist.progress is not None
    assert 0.0 <= result.kb_assist.progress <= 1.0


async def test_smoke_kb_assist_complete_mode_has_final_entry_pairs() -> None:
    result = await run_kb_operations_smoke(
        KBOperationsInput(
            agent_type="kb_assist",
            prompt_text="Complete the entry for Mara Silverwood.",
            entity_type="character",
            field_key="role",
        )
    )

    assert result.kb_assist is not None
    assert result.kb_assist.mode == "complete"
    assert result.kb_assist.final_entry
    assert all(str(k).strip() and str(v).strip() for k, v in result.kb_assist.final_entry.items())


async def test_smoke_kb_improve_emits_real_suggestion_schema() -> None:
    result = await run_kb_operations_smoke(
        KBOperationsInput(
            agent_type="kb_improve",
            prompt_text="This entry is sparse and missing motivation; connect it to Iron Guild.",
            entity_type="character",
            field_key="motivation",
        )
    )

    assert result.kb_improve is not None
    assert result.kb_improve.overall_assessment.strip()
    assert 0.0 <= result.kb_improve.completeness_score <= 1.0
    assert result.kb_improve.suggestions
    assert all(
        s.type in {item.value for item in SuggestionType} for s in result.kb_improve.suggestions
    )
    assert all(s.target.strip() and s.description.strip() for s in result.kb_improve.suggestions)


async def test_smoke_kb_merge_emits_merge_decision_with_confidence() -> None:
    result = await run_kb_operations_smoke(
        KBOperationsInput(
            agent_type="kb_merge",
            prompt_text="Mara Silverwood and Mara of Silverwood are the same person.",
            entity_type="character",
        )
    )

    assert result.kb_merge is not None
    assert result.kb_merge.merge_decisions
    decision = result.kb_merge.merge_decisions[0]
    assert decision.decision == "merge"
    assert 0.0 <= decision.confidence <= 1.0
    assert decision.merge_strategy is not None
    assert decision.merge_strategy.keep_name.strip()


def test_kb_agent_validator_rejects_unknown_operation() -> None:
    result = KBOperationsResult(
        kb_agent=KBAgentOperationSection(
            operation="delete_entity",
            query="Mara",
            formatted_response="Deleted.",
        )
    )

    score = KBAgentOperationSchemaValidator().evaluate(
        _ctx(output=result, metadata={"agent_type": "kb_agent"})
    )

    assert 0.0 <= score < 1.0


def test_kb_assist_validator_rejects_question_without_field_key() -> None:
    result = KBOperationsResult(
        kb_assist=KBAssistSection(mode="question", question="What does Mara want?")
    )

    score = KBAssistSchemaValidator().evaluate(
        _ctx(output=result, metadata={"agent_type": "kb_assist"})
    )

    assert 0.0 <= score < 1.0


def test_kb_assist_eval_model_matches_actual_mode_literal() -> None:
    section = KBAssistSection(mode="question", question="What does Mara want?", field_key="goal")

    actual = KBAssistOutput.model_validate(section.model_dump())

    assert actual.mode == "question"
    assert actual.field_key == "goal"


def test_kb_improve_validator_rejects_unknown_suggestion_type() -> None:
    result = KBOperationsResult(
        kb_improve=KBImproveSection(
            suggestions=[
                KBImproveSuggestionSection(
                    type="not_real",
                    target="motivation",
                    description="Explain the motivation.",
                    confidence=0.8,
                )
            ],
            overall_assessment="Assessment: usable but incomplete.",
            completeness_score=0.6,
        )
    )

    score = KBImproveSchemaValidator().evaluate(
        _ctx(output=result, metadata={"agent_type": "kb_improve"})
    )

    assert 0.0 <= score < 1.0


def test_kb_improve_schema_itself_enforces_confidence_range() -> None:
    try:
        KBImproveSuggestionSection(
            type="expand",
            target="motivation",
            description="Add motivation.",
            confidence=1.5,
        )
    except ValidationError:
        return
    raise AssertionError("schema should reject confidence > 1.0")


def test_kb_merge_validator_rejects_duplicate_pair_ids() -> None:
    decision = KBMergeDecisionSection(pair_id="pair-1", decision="distinct", confidence=0.9)
    result = KBOperationsResult(
        kb_merge=KBMergeSection(
            merge_decisions=[decision, decision.model_copy()],
            overall_notes="Two duplicate decisions.",
        )
    )

    score = KBMergeSchemaValidator().evaluate(
        _ctx(output=result, metadata={"agent_type": "kb_merge"})
    )

    assert 0.0 <= score < 1.0


def test_kb_merge_validator_rejects_merge_without_strategy() -> None:
    result = KBOperationsResult(
        kb_merge=KBMergeSection(
            merge_decisions=[
                KBMergeDecisionSection(pair_id="pair-1", decision="merge", confidence=0.9)
            ],
            overall_notes="Missing strategy.",
        )
    )

    score = KBMergeSchemaValidator().evaluate(
        _ctx(output=result, metadata={"agent_type": "kb_merge"})
    )

    assert 0.0 <= score < 1.0


def test_kb_merge_eval_model_matches_actual_merge_output_schema() -> None:
    section = KBMergeSection(
        merge_decisions=[
            KBMergeDecisionSection(
                pair_id="pair-1",
                decision="merge",
                confidence=0.91,
                reasoning="Same aliases and biography.",
                merge_strategy=KBMergeStrategySection(keep_name="Mara Silverwood"),
            )
        ],
        overall_notes="One duplicate found.",
    )

    actual = MergeOutput.model_validate(section.model_dump())

    assert isinstance(actual.merge_decisions[0], MergeDecision)
    assert actual.merge_decisions[0].decision == "merge"


async def test_all_four_validators_pass_on_smoke_outputs() -> None:
    cases = [
        KBOperationsInput(
            agent_type="kb_agent",
            prompt_text="Search the KB for Iron Guild factions.",
            entity_type="faction",
        ),
        KBOperationsInput(
            agent_type="kb_assist",
            prompt_text="Suggest a value for the role field.",
            entity_type="character",
            field_key="role",
        ),
        KBOperationsInput(
            agent_type="kb_improve",
            prompt_text="Improve a sparse character entry and add missing motivation.",
            entity_type="character",
            field_key="motivation",
        ),
        KBOperationsInput(
            agent_type="kb_merge",
            prompt_text="Mara and Captain Mara are likely the same person.",
            entity_type="character",
        ),
    ]
    validators = [
        KBAgentOperationSchemaValidator(),
        KBAssistSchemaValidator(),
        KBImproveSchemaValidator(),
        KBMergeSchemaValidator(),
    ]

    for case in cases:
        output = await run_kb_operations_smoke(case)
        for validator in validators:
            score = validator.evaluate(
                _ctx(output=output, metadata={"agent_type": case.agent_type})
            )
            assert score == 1.0


def _count_agent_types(dataset: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in dataset.cases:
        agent_type = case.metadata["agent_type"]
        counts[agent_type] = counts.get(agent_type, 0) + 1
    return counts


def _ctx(
    *, output: KBOperationsResult, metadata: dict[str, Any] | None = None
) -> EvaluatorContext[Any, KBOperationsResult, dict[str, Any]]:
    return cast(
        "EvaluatorContext[Any, KBOperationsResult, dict[str, Any]]",
        DummyContext(output=output, metadata=metadata),
    )
