"""Unit tests for the analysis_metrics eval suite (dataset + evaluators).

Follows the pattern established by ``tests/unit/evals/test_evaluators.py``:
direct construction of evaluator contexts with ``DummyContext`` doubles and
targeted assertions on the deterministic smoke task outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from evals.datasets.analysis_metrics import build_dataset
from evals.evaluators import (
    ChapterSummarySchemaValidator,
    POVDetectionSchemaValidator,
    ReadabilitySchemaValidator,
)
from evals.models import (
    AnalysisMetricsInput,
    AnalysisMetricsResult,
    POVMetricsIssue,
    POVMetricsScene,
    POVSection,
    ReadabilitySection,
    SummarySection,
)
from evals.tasks.analysis_metrics_smoke import analysis_metrics as run_analysis_metrics_smoke

if TYPE_CHECKING:
    from pydantic_evals.evaluators import EvaluatorContext


@dataclass(frozen=True)
class DummyContext:
    """Small evaluator context double with only fields our evaluators read."""

    output: Any
    metadata: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Dataset structure
# ---------------------------------------------------------------------------


def test_analysis_metrics_dataset_has_three_cases_per_agent() -> None:
    dataset = build_dataset()

    assert dataset.name == "analysis_metrics"
    agent_counts = _count_agent_types(dataset)
    assert agent_counts == {"readability": 3, "pov": 3, "summary": 3}


def test_analysis_metrics_dataset_registers_in_factory() -> None:
    from evals.datasets import DATASET_FACTORIES

    assert "analysis_metrics" in DATASET_FACTORIES
    assert DATASET_FACTORIES["analysis_metrics"] is build_dataset


def test_analysis_metrics_suite_available_in_cli_order() -> None:
    from evals.datasets import available_suites

    assert "analysis_metrics" in available_suites()


# ---------------------------------------------------------------------------
# Smoke task — schema-valid deterministic output per agent
# ---------------------------------------------------------------------------


async def test_smoke_readability_produces_schema_valid_section() -> None:
    result = await run_analysis_metrics_smoke(
        AnalysisMetricsInput(
            agent_type="readability",
            text_content=(
                "This is a short sentence. "
                "This is an extremely long and winding sentence that goes on and on "
                "and on with many many words far beyond any reasonable readability "
                "threshold so it should definitely be flagged by the smoke producer."
            ),
        )
    )

    assert isinstance(result, AnalysisMetricsResult)
    assert result.readability is not None
    assert result.pov is None and result.summary is None
    assert result.readability.overall_assessment.strip()
    # The long sentence must be flagged with too_long + 2 suggestions.
    flagged = result.readability.problematic_sentences
    assert flagged, "long sentence should be flagged"
    for sentence in flagged:
        issues = sentence.get("issues")
        assert isinstance(issues, list) and issues
        assert all(i["type"] == "too_long" for i in issues)
        assert 0 <= len(sentence.get("suggestions", [])) <= 3


async def test_smoke_readability_clean_passage_flags_nothing() -> None:
    result = await run_analysis_metrics_smoke(
        AnalysisMetricsInput(
            agent_type="readability",
            text_content="The cat sat. The dog ran. Both were happy.",
        )
    )

    assert result.readability is not None
    assert result.readability.problematic_sentences == []
    # Evaluator must still score 1.0 (no problematic sentences is valid).
    score = ReadabilitySchemaValidator().evaluate(
        _ctx(
            output=result,
            metadata={"agent_type": "readability"},
        )
    )
    assert score == 1.0


async def test_smoke_pov_first_person_classification() -> None:
    result = await run_analysis_metrics_smoke(
        AnalysisMetricsInput(
            agent_type="pov",
            text_content=("I walked to the gate alone. I did not look back at the city."),
        )
    )

    assert result.pov is not None
    assert result.pov.analysis_type == "first_person"
    assert result.pov.overall_assessment.strip()
    assert result.pov.switch_count >= 0
    assert all(0.0 <= v <= 1.0 for v in result.pov.pov_distribution.values())


async def test_smoke_pov_mixed_multi_scene_adds_head_hop_issue() -> None:
    result = await run_analysis_metrics_smoke(
        AnalysisMetricsInput(
            agent_type="pov",
            text_content=(
                "Kael studied the map, certain the pass lay to the east.\n\n"
                "Mira watched him from across the tent and wondered.\n\n"
                "Soren paced outside, sure both were hiding something."
            ),
        )
    )

    assert result.pov is not None
    assert result.pov.analysis_type == "mixed"
    assert len(result.pov.scenes) == 3
    # Each scene has a non-empty POV character (agent invariant).
    assert all(scene.pov_character.strip() for scene in result.pov.scenes)
    assert any(issue.type == "head_hop" for issue in result.pov.issues)


async def test_smoke_summary_produces_bounded_summary_with_key_points() -> None:
    result = await run_analysis_metrics_smoke(
        AnalysisMetricsInput(
            agent_type="summary",
            text_content=(
                "The blacksmith forged a nail. The apprentice tried again. "
                "The forge grew hot. Smoke filled the room."
            ),
        )
    )

    assert result.summary is not None
    assert result.summary.summary.strip()
    assert result.summary.key_points
    assert result.summary.word_count == len(result.summary.summary.split())
    assert 0 < result.summary.word_count <= 200


# ---------------------------------------------------------------------------
# Evaluator scoring — happy path and violation detection
# ---------------------------------------------------------------------------


def test_readability_validator_scores_violating_issue_type_below_one() -> None:
    section = ReadabilitySection(
        overall_assessment="Non-empty assessment.",
        problematic_sentences=[
            {
                "content": "Some sentence.",
                "issues": [{"type": "not_a_real_label", "description": "x"}],
                "suggestions": [],
            }
        ],
    )
    result = AnalysisMetricsResult(readability=section)

    score = ReadabilitySchemaValidator().evaluate(
        _ctx(output=result, metadata={"agent_type": "readability"})
    )

    assert 0.0 <= score < 1.0


def test_readability_validator_not_applicable_for_other_agents() -> None:
    result = AnalysisMetricsResult(pov=POVSection(analysis_type="first_person"))

    # readability evaluator must be a no-op for a pov case.
    assert (
        ReadabilitySchemaValidator().evaluate(_ctx(output=result, metadata={"agent_type": "pov"}))
        == 1.0
    )


def test_readability_validator_zero_when_section_missing() -> None:
    result = AnalysisMetricsResult(pov=POVSection())

    assert (
        ReadabilitySchemaValidator().evaluate(
            _ctx(output=result, metadata={"agent_type": "readability"})
        )
        == 0.0
    )


def test_pov_validator_rejects_unknown_analysis_type() -> None:
    section = POVSection(
        analysis_type="second_person",  # not a real value per pov_types schema
        overall_assessment="Assessment.",
        scenes=[POVMetricsScene(scene_index=0, pov_character="Mara", confidence=0.9)],
    )
    result = AnalysisMetricsResult(pov=section)

    score = POVDetectionSchemaValidator().evaluate(
        _ctx(output=result, metadata={"agent_type": "pov"})
    )

    assert 0.0 <= score < 1.0


def test_pov_validator_rejects_out_of_range_distribution() -> None:
    # pov_distribution values are NOT range-constrained by the schema (dict[str,float]),
    # so this is a real property the evaluator catches that the model does not.
    # (scene.confidence, by contrast, IS enforced at the schema level via le=1.0.)
    section = POVSection(
        analysis_type="third_limited",
        overall_assessment="Assessment.",
        pov_distribution={"Mara": 1.5},
        scenes=[
            POVMetricsScene(scene_index=0, pov_character="Mara", confidence=0.9),
        ],
    )
    result = AnalysisMetricsResult(pov=section)

    score = POVDetectionSchemaValidator().evaluate(
        _ctx(output=result, metadata={"agent_type": "pov"})
    )

    assert 0.0 <= score < 1.0


def test_pov_schema_itself_enforces_confidence_range() -> None:
    """Regression guard: the model schema enforces confidence in [0,1].

    This documents that the evaluator's confidence check is a redundant safety
    net (the schema already rejects out-of-range values at construction).
    """

    from pydantic import ValidationError

    try:
        POVMetricsScene(scene_index=0, pov_character="Mara", confidence=1.5)
    except ValidationError:
        return
    raise AssertionError("schema should reject confidence > 1.0")


def test_pov_validator_rejects_invalid_issue_severity() -> None:
    section = POVSection(
        analysis_type="third_limited",
        overall_assessment="Assessment.",
        issues=[
            POVMetricsIssue(type="head_hop", severity="critical"),
        ],
    )
    result = AnalysisMetricsResult(pov=section)

    score = POVDetectionSchemaValidator().evaluate(
        _ctx(output=result, metadata={"agent_type": "pov"})
    )

    assert 0.0 <= score < 1.0


def test_summary_validator_rejects_empty_key_points() -> None:
    section = SummarySection(summary="A summary.", key_points=[], word_count=2)
    result = AnalysisMetricsResult(summary=section)

    score = ChapterSummarySchemaValidator().evaluate(
        _ctx(output=result, metadata={"agent_type": "summary"})
    )

    assert 0.0 <= score < 1.0


def test_summary_validator_rejects_inconsistent_word_count() -> None:
    section = SummarySection(
        summary="A summary with words.",
        key_points=["A key point."],
        word_count=999,  # inconsistent with len(summary.split())
    )
    result = AnalysisMetricsResult(summary=section)

    score = ChapterSummarySchemaValidator().evaluate(
        _ctx(output=result, metadata={"agent_type": "summary"})
    )

    assert 0.0 <= score < 1.0


async def test_all_three_validators_pass_on_smoke_outputs() -> None:
    """End-to-end: each smoke output satisfies its matching validator with score 1.0."""

    cases = [
        ("readability", "The cat sat. " * 15 + "Long filler sentence " * 12 + "end."),
        ("pov", "Mara opened the door. She stepped inside the dark hall."),
        ("summary", "The hero arrived. The dragon woke. They fought at dawn."),
    ]
    evaluators = {
        "readability": ReadabilitySchemaValidator(),
        "pov": POVDetectionSchemaValidator(),
        "summary": ChapterSummarySchemaValidator(),
    }
    for agent_type, text in cases:
        result = await run_analysis_metrics_smoke(
            AnalysisMetricsInput(agent_type=agent_type, text_content=text)
        )
        # Only the evaluator matching this output's agent_type applies; the
        # metadata carries the output's real agent_type so the gate matches.
        score = evaluators[agent_type].evaluate(
            _ctx(output=result, metadata={"agent_type": agent_type})
        )
        assert score == 1.0, f"{agent_type} validator scored {score} on its own smoke output"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_agent_types(dataset: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in dataset.cases:
        agent_type = case.metadata.get("agent_type")
        assert agent_type is not None
        counts[agent_type] = counts.get(agent_type, 0) + 1
    return counts


def _ctx(
    *,
    output: object,
    metadata: dict[str, Any] | None = None,
) -> EvaluatorContext[object, Any, dict[str, Any]]:
    return cast(
        "EvaluatorContext[object, Any, dict[str, Any]]",
        DummyContext(output=output, metadata=metadata),
    )
