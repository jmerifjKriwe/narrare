"""Unit tests for the planning_structure eval suite (dataset + evaluators)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from evals.datasets.planning_structure import build_dataset
from evals.evaluators import (
    CharacterArcSchemaValidator,
    OutlineSchemaValidator,
    TimelineSchemaValidator,
    WorldbuildingSchemaValidator,
)
from evals.models import (
    CharacterArcPhaseSection,
    CharacterArcSection,
    OutlineSection,
    PlanningStructureInput,
    PlanningStructureResult,
    TimelineEventSection,
    TimelineSection,
    WorldbuildingConnectionSection,
    WorldbuildingGapSection,
    WorldbuildingSection,
)
from evals.tasks.planning_structure_smoke import planning_structure as run_planning_smoke

if TYPE_CHECKING:
    from pydantic_evals.evaluators import EvaluatorContext


@dataclass(frozen=True)
class DummyContext:
    """Small evaluator context double with only fields our evaluators read."""

    output: Any
    metadata: dict[str, Any] | None = None


def test_planning_structure_dataset_has_expected_case_mix() -> None:
    dataset = build_dataset()

    assert dataset.name == "planning_structure"
    assert _count_agent_types(dataset) == {
        "outline": 3,
        "character_arc": 3,
        "timeline": 3,
        "worldbuilding": 2,
    }


def test_planning_structure_dataset_registers_in_factory() -> None:
    from evals.datasets import DATASET_FACTORIES

    assert "planning_structure" in DATASET_FACTORIES
    assert DATASET_FACTORIES["planning_structure"] is build_dataset


def test_planning_structure_suite_available_in_cli_order() -> None:
    from evals.datasets import available_suites

    assert "planning_structure" in available_suites()


async def test_smoke_outline_produces_title_and_scene_structure() -> None:
    result = await run_planning_smoke(
        PlanningStructureInput(
            agent_type="outline",
            prompt_text=(
                "The Bridge of Glass\n"
                "Mara finds the bridge. It cracks under her feet. "
                "She reaches the far bank changed."
            ),
        )
    )

    assert isinstance(result, PlanningStructureResult)
    assert result.outline is not None
    assert result.character_arc is None and result.timeline is None and result.worldbuilding is None
    assert result.outline.chapter_title == "The Bridge of Glass"
    assert len(result.outline.scenes) == 3
    assert all(scene.strip() for scene in result.outline.scenes)
    assert result.outline.outline_text.strip()


async def test_smoke_character_arc_identifies_phase_and_goal_state_structure() -> None:
    result = await run_planning_smoke(
        PlanningStructureInput(
            agent_type="character_arc",
            prompt_text="Lyra: from timid apprentice to confident leader. Mentored by Soren.",
        )
    )

    assert result.character_arc is not None
    assert result.character_arc.character_name == "Lyra"
    assert result.character_arc.starting_state == "timid apprentice"
    assert result.character_arc.ending_state == "confident leader"
    assert result.character_arc.arc_type == "growth"
    assert len(result.character_arc.phases) == 3
    assert all(
        phase.phase_name.strip() and phase.description.strip()
        for phase in result.character_arc.phases
    )


async def test_smoke_timeline_orders_events_and_links_chapters() -> None:
    result = await run_planning_smoke(
        PlanningStructureInput(
            agent_type="timeline",
            prompt_text=(
                "Chapter 1: The council meets. "
                "Chapter 2: The fleet sails. "
                "Chapter 3: The storm breaks."
            ),
        )
    )

    assert result.timeline is not None
    assert [event.timestamp for event in result.timeline.timeline_events] == [
        "Chapter 1",
        "Chapter 2",
        "Chapter 3",
    ]
    assert [event.chapter_reference for event in result.timeline.timeline_events] == [
        "Chapter 1",
        "Chapter 2",
        "Chapter 3",
    ]
    assert all(
        event.event_name.strip() and event.description.strip()
        for event in result.timeline.timeline_events
    )


async def test_smoke_worldbuilding_emits_phase_one_schema() -> None:
    result = await run_planning_smoke(
        PlanningStructureInput(
            agent_type="worldbuilding",
            prompt_text="character: Lyra Silvermoon\nplace: Alderaan\nfaction: The Iron Guild",
        )
    )

    assert result.worldbuilding is not None
    assert result.worldbuilding.assessment.strip()
    assert 0.0 <= result.worldbuilding.worldbuilding_score <= 1.0
    assert result.worldbuilding.gaps
    assert result.worldbuilding.connection_suggestions
    assert result.worldbuilding.candidate_pairs_for_consistency == [("ent-1", "ent-2")]
    assert all(
        gap.description.strip() and gap.gap_type.strip() for gap in result.worldbuilding.gaps
    )


def test_outline_validator_rejects_missing_scenes() -> None:
    result = PlanningStructureResult(
        outline=OutlineSection(chapter_title="A Title", scenes=[], outline_text="")
    )

    score = OutlineSchemaValidator().evaluate(
        _ctx(output=result, metadata={"agent_type": "outline"})
    )

    assert 0.0 <= score < 1.0


def test_character_arc_validator_rejects_unknown_arc_type() -> None:
    result = PlanningStructureResult(
        character_arc=CharacterArcSection(
            character_name="Lyra",
            starting_state="timid",
            ending_state="brave",
            arc_type="spiral",
            phases=[
                CharacterArcPhaseSection(phase_name="Start", description="Begins"),
                CharacterArcPhaseSection(phase_name="Middle", description="Struggles"),
                CharacterArcPhaseSection(phase_name="End", description="Resolves"),
            ],
        )
    )

    score = CharacterArcSchemaValidator().evaluate(
        _ctx(output=result, metadata={"agent_type": "character_arc"})
    )

    assert 0.0 <= score < 1.0


def test_timeline_validator_rejects_duplicate_event_timestamp_pairs() -> None:
    event = TimelineEventSection(
        event_name="Council meets",
        description="The council meets.",
        timestamp="Chapter 1",
        chapter_reference="Chapter 1",
    )
    result = PlanningStructureResult(
        timeline=TimelineSection(
            timeline_events=[event, event.model_copy()],
            overall_assessment="Assessment.",
        )
    )

    score = TimelineSchemaValidator().evaluate(
        _ctx(output=result, metadata={"agent_type": "timeline"})
    )

    assert 0.0 <= score < 1.0


def test_timeline_validator_rejects_out_of_order_chapters() -> None:
    result = PlanningStructureResult(
        timeline=TimelineSection(
            timeline_events=[
                TimelineEventSection(
                    event_name="Fleet sails",
                    description="The fleet sails.",
                    timestamp="Chapter 2",
                    chapter_reference="Chapter 2",
                ),
                TimelineEventSection(
                    event_name="Council meets",
                    description="The council meets.",
                    timestamp="Chapter 1",
                    chapter_reference="Chapter 1",
                ),
            ],
            overall_assessment="Assessment.",
        )
    )

    score = TimelineSchemaValidator().evaluate(
        _ctx(output=result, metadata={"agent_type": "timeline"})
    )

    assert 0.0 <= score < 1.0


def test_worldbuilding_validator_rejects_unknown_gap_type() -> None:
    result = PlanningStructureResult(
        worldbuilding=WorldbuildingSection(
            gaps=[
                WorldbuildingGapSection(
                    entity_id="ent-1",
                    entity_name="Lyra",
                    entity_type="character",
                    gap_type="unknown_gap",
                    description="A real description.",
                )
            ],
            connection_suggestions=[
                WorldbuildingConnectionSection(
                    source_entity_id="ent-1",
                    source_entity_name="Lyra",
                    target_entity_id="ent-2",
                    target_entity_name="Alderaan",
                    suggested_rel_type="related_to",
                    reasoning="A link is useful.",
                    confidence=0.8,
                )
            ],
            assessment="Assessment.",
            worldbuilding_score=0.7,
        )
    )

    score = WorldbuildingSchemaValidator().evaluate(
        _ctx(output=result, metadata={"agent_type": "worldbuilding"})
    )

    assert 0.0 <= score < 1.0


def test_planning_validators_are_noops_for_other_agents() -> None:
    result = PlanningStructureResult(
        outline=OutlineSection(chapter_title="Title", scenes=["Scene"])
    )

    assert (
        CharacterArcSchemaValidator().evaluate(
            _ctx(output=result, metadata={"agent_type": "outline"})
        )
        == 1.0
    )


def _ctx(
    *, output: PlanningStructureResult, metadata: dict[str, Any] | None = None
) -> EvaluatorContext[Any, PlanningStructureResult, dict[str, Any]]:
    return cast(
        "EvaluatorContext[Any, PlanningStructureResult, dict[str, Any]]",
        DummyContext(output, metadata),
    )


def _count_agent_types(dataset: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in dataset.cases:
        agent_type = case.metadata["agent_type"]
        counts[agent_type] = counts.get(agent_type, 0) + 1
    return counts
