"""Analysis feedback Pydantic Evals dataset."""

from __future__ import annotations

from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance

from evals.evaluators import AnalysisFeedbackContent, AnalysisFeedbackValidator
from evals.models import AnalysisFeedbackInput, AnalysisFeedbackResult


def build_dataset() -> Dataset[AnalysisFeedbackInput, AnalysisFeedbackResult, dict[str, Any]]:
    """Build the analysis feedback eval dataset.

    Two cases per agent type (6 total) with realistic chapter text for analysis.
    Metadata tags the ``agent_type`` for evaluator filtering.
    """

    return Dataset(
        name="analysis_feedback",
        cases=[
            # --- BetaReaderAgent cases ---
            Case(
                name="beta-reader-character-intro",
                inputs=AnalysisFeedbackInput(
                    agent_type="beta_reader",
                    text_content=(
                        "Chapter 7 — The Crimson Tide\n\n"
                        "Elara stood at the prow of the Dawn Chaser, her knuckles white "
                        "against the rail. The sea below churned with a phosphorescent "
                        "glow that the sailors called the Crimson Tide — though it ran "
                        "more amber than red. She had heard stories: fleets swallowed "
                        "whole, cities drowned in a single night. First Mate Orin "
                        "claimed it was the breath of a sleeping god. Elara suspected "
                        "it was something far older, and far more awake.\n\n"
                        '"We should turn back," she said, not turning around.\n\n'
                        'Orin laughed, a harsh sound like grinding stones. "Turn back '
                        "to what? The King's noose?\"\n\n"
                        "The wind shifted, and the Tide beneath them began to pulse."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "beta_reader"},
            ),
            Case(
                name="beta-reader-climax-scene",
                inputs=AnalysisFeedbackInput(
                    agent_type="beta_reader",
                    text_content=(
                        "Chapter 24 — The Glass Throne\n\n"
                        "The hall was silent save for the drip of water through cracked "
                        "masonry. Hundreds of glass statues lined the walls — frozen "
                        "figures in poses of terror, their faces twisted mid-scream. "
                        "At the far end, on a throne of fused silica, sat the Sorcerer-"
                        "King, motionless as his subjects.\n\n"
                        "Rynn stepped forward, her boots crunching on a carpet of "
                        'shattered crystal. "Is he dead?"\n\n'
                        "The Sorcerer-King opened his eyes.\n\n"
                        '"Not quite," he said, and the glass statues began to weep.'
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "beta_reader"},
            ),
            # --- ReviewAgent cases ---
            Case(
                name="review-rough-draft",
                inputs=AnalysisFeedbackInput(
                    agent_type="review",
                    text_content=(
                        "And so the hero finally reached the castle. It was big and "
                        "scary. He was very scared but he knew he had to go inside. "
                        "The door creaked and he walked in. Inside it was dark. Really "
                        "dark. He could barely see anything. There was a dragon but "
                        "it was sleeping. He snuck past it but then he stepped on a "
                        "twig and it woke up. Oh no, thought the hero."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "review"},
            ),
            Case(
                name="review-polished-chapter",
                inputs=AnalysisFeedbackInput(
                    agent_type="review",
                    text_content=(
                        "The library of Thornwood Abbey held seventeen thousand "
                        "volumes, and Sister Margarethe had read every one. She ran "
                        'her finger along a spine gilded with faded letters — "On '
                        'the Properties of Dragonbone," by M. Caldheart — and '
                        "pulled it from the shelf. The binding cracked. No one had "
                        "opened this book in decades.\n\n"
                        '"Find what you need?" asked Brother Tomas from the doorway.\n\n'
                        'Margarethe did not look up. "I need to know how to kill '
                        'something that cannot die."\n\n'
                        "Tomas crossed himself. Outside, the sky had turned the "
                        "colour of spoiled milk."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "review"},
            ),
            # --- ConsistencyAgent cases ---
            Case(
                name="consistency-character-contradiction",
                inputs=AnalysisFeedbackInput(
                    agent_type="consistency",
                    text_content=(
                        "In Chapter 3, Marcus is described as deathly afraid of "
                        "heights — he cannot climb the tower stairs without breaking "
                        "into a cold sweat. Yet in Chapter 7, he casually rappels "
                        "down a cliff face to rescue a fallen comrade, showing no "
                        "sign of vertigo. Earlier the text notes he is an only child, "
                        "but in the flashback scene an older brother named Theron is "
                        "mentioned as having taught him to fight."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "consistency"},
            ),
            Case(
                name="consistency-world-facts",
                inputs=AnalysisFeedbackInput(
                    agent_type="consistency",
                    text_content=(
                        "The magic system states that only those born under the "
                        "Blood Moon can wield shadow magic. Kael is established as "
                        "a shadow mage. However, Chapter 12 reveals Kael was born "
                        "during the Harvest Moon. Additionally, the eastern desert "
                        "is described as impassable in Chapter 4, yet in Chapter 14 "
                        "a trade caravan crosses it in three days without difficulty."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "consistency"},
            ),
        ],
        evaluators=[
            IsInstance(type_name="AnalysisFeedbackResult"),
            AnalysisFeedbackValidator(),
            AnalysisFeedbackContent(),
        ],
    )
