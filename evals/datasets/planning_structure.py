"""Planning structure Pydantic Evals dataset.

Covers four planning-panel agents (Tier 2 of the eval-expansion plan):

- OutlineAgent       — chapter outline (title + scene list)
- CharacterArcAgent  — multi-phase character development arc
- TimelineAgent      — chronologically ordered narrative events
- WorldbuildingAgent — Phase 1 gaps + connection suggestions

Three cases per agent for outline/character_arc/timeline and two for
worldbuilding (11 total), covering happy path plus edge behaviour. Metadata
tags ``agent_type`` so the metadata-aware evaluators select the right
validator per case (mirrors the ``analysis_metrics`` suite pattern).
"""

from __future__ import annotations

from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance

from evals.evaluators import (
    CharacterArcSchemaValidator,
    OutlineSchemaValidator,
    TimelineSchemaValidator,
    WorldbuildingSchemaValidator,
)
from evals.models import PlanningStructureInput, PlanningStructureResult


def build_dataset() -> Dataset[PlanningStructureInput, PlanningStructureResult, dict[str, Any]]:
    """Build the planning structure eval dataset.

    Three cases per agent for outline/character_arc/timeline and two for
    worldbuilding (11 total) with realistic fantasy fiction briefs. Metadata
    tags the ``agent_type`` for evaluator filtering.
    """

    return Dataset(
        name="planning_structure",
        cases=[
            # --- OutlineAgent cases ---
            Case(
                name="outline-multi-scene",
                inputs=PlanningStructureInput(
                    agent_type="outline",
                    prompt_text=(
                        "The Hero Enters the Forest\n"
                        "Mara crosses the threshold into the whispering wood. "
                        "She meets the hedge-witch guide at the standing stone. "
                        "They are ambushed by theriver bandits at the crossing."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "outline"},
            ),
            Case(
                name="outline-single-scene",
                inputs=PlanningStructureInput(
                    agent_type="outline",
                    prompt_text=(
                        "The Letter Arrives\n"
                        "A single quiet scene in which the sealed letter reaches the keep."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "outline"},
            ),
            Case(
                name="outline-no-body-edge",
                inputs=PlanningStructureInput(
                    agent_type="outline",
                    prompt_text="The Quiet Chapter",
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "outline"},
            ),
            # --- CharacterArcAgent cases ---
            Case(
                name="character-arc-growth",
                inputs=PlanningStructureInput(
                    agent_type="character_arc",
                    prompt_text=(
                        "Lyra: from a timid orphan to a confident leader. "
                        "Mentored by Soren along the way."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "character_arc"},
            ),
            Case(
                name="character-arc-flat",
                inputs=PlanningStructureInput(
                    agent_type="character_arc",
                    prompt_text=(
                        "The Innkeeper: steady and unchanging throughout the saga. "
                        "A flat, reliable presence for the wandering hero."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "character_arc"},
            ),
            Case(
                name="character-arc-transformation",
                inputs=PlanningStructureInput(
                    agent_type="character_arc",
                    prompt_text=(
                        "Kael: a betrayer seeking redemption, transformed by guilt. "
                        "His fall began the war; his transformation may end it."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "character_arc"},
            ),
            # --- TimelineAgent cases ---
            Case(
                name="timeline-linear-multi-event",
                inputs=PlanningStructureInput(
                    agent_type="timeline",
                    prompt_text=(
                        "Chapter 1: The council meets in the high hall. "
                        "Chapter 2: War is declared against the eastern provinces. "
                        "Chapter 3: The siege of the river fortress begins."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "timeline"},
            ),
            Case(
                name="timeline-single-event",
                inputs=PlanningStructureInput(
                    agent_type="timeline",
                    prompt_text="Chapter 9: The bargain with the river witch is struck.",
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "timeline"},
            ),
            Case(
                name="timeline-with-conflict",
                inputs=PlanningStructureInput(
                    agent_type="timeline",
                    prompt_text=(
                        "Chapter 1: The king dies at dawn. "
                        "Chapter 2: The king is seen alive at the market — an inconsistency. "
                        "Chapter 3: The succession conflict erupts."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "timeline"},
            ),
            # --- WorldbuildingAgent cases ---
            Case(
                name="worldbuilding-gaps-and-connections",
                inputs=PlanningStructureInput(
                    agent_type="worldbuilding",
                    prompt_text=(
                        "character: Lyra Silvermoon\nplace: Alderaan\nfaction: The Iron Guild"
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "worldbuilding"},
            ),
            Case(
                name="worldbuilding-no-entities-edge",
                inputs=PlanningStructureInput(
                    agent_type="worldbuilding",
                    prompt_text="No structured entities are provided in this brief.",
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "worldbuilding"},
            ),
        ],
        evaluators=[
            IsInstance(type_name="PlanningStructureResult"),
            OutlineSchemaValidator(),
            CharacterArcSchemaValidator(),
            TimelineSchemaValidator(),
            WorldbuildingSchemaValidator(),
        ],
    )
