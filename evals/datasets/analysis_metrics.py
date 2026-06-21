"""Analysis metrics Pydantic Evals dataset.

Covers three analysis-panel agents (Tier 2 of the eval-expansion plan):

- ReadabilityAgent     — sentence-level readability analysis
- POVDetectionAgent    — POV classification and violation detection
- ChapterSummaryAgent  — chapter summary and key-event extraction

Three cases per agent (9 total) covering happy path plus edge/range
behaviour. Metadata tags ``agent_type`` so the metadata-aware evaluators
select the right validator per case (mirrors the ``chat_generation`` and
``analysis_feedback`` suite pattern).
"""

from __future__ import annotations

from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance

from evals.evaluators import (
    ChapterSummarySchemaValidator,
    POVDetectionSchemaValidator,
    ReadabilitySchemaValidator,
)
from evals.models import AnalysisMetricsInput, AnalysisMetricsResult


def build_dataset() -> Dataset[AnalysisMetricsInput, AnalysisMetricsResult, dict[str, Any]]:
    """Build the analysis metrics eval dataset.

    Three cases per agent type (9 total) with realistic fantasy fiction text.
    Metadata tags the ``agent_type`` for evaluator filtering.
    """

    return Dataset(
        name="analysis_metrics",
        cases=[
            # --- ReadabilityAgent cases ---
            Case(
                name="readability-clean-passage",
                inputs=AnalysisMetricsInput(
                    agent_type="readability",
                    text_content=(
                        "The lighthouse keeper climbed the spiral stairs each morning. "
                        "She checked the lamp, wiped the lens, and watched the horizon. "
                        "The sea was calm. The gulls were loud."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "readability"},
            ),
            Case(
                name="readability-dense-prose",
                inputs=AnalysisMetricsInput(
                    agent_type="readability",
                    text_content=(
                        "Notwithstanding the extemporaneous and arguably superfluous "
                        "perambulations of the aforementioned protagonist through the "
                        "labyrinthine and suffocatingly baroque subterranean "
                        "concordance of interlocking passageways, it was nevertheless "
                        "observed that the inexorable progression of the narrative "
                        "continued unabated, propelled by forces neither fully "
                        "comprehended nor adequately elucidated by those present."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "readability"},
            ),
            Case(
                name="readability-passive-voice",
                inputs=AnalysisMetricsInput(
                    agent_type="readability",
                    text_content=(
                        "The door was opened by Mara. The letter was read aloud. "
                        "A decision was made by the council that the prisoner would "
                        "be released at dawn, and the news was delivered by a runner."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "readability"},
            ),
            # --- POVDetectionAgent cases ---
            Case(
                name="pov-third-limited-single-scene",
                inputs=AnalysisMetricsInput(
                    agent_type="pov",
                    text_content=(
                        "Elara pressed her back against the cold stone wall and held "
                        "her breath. The guards' torchlight swept past the alcove. She "
                        "felt her heart hammering against her ribs. If they found her "
                        "now, everything she had planned would be over."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "pov"},
            ),
            Case(
                name="pov-head-hop-multi-scene",
                inputs=AnalysisMetricsInput(
                    agent_type="pov",
                    text_content=(
                        "Kael studied the map, certain the pass lay to the east.\n\n"
                        "From across the tent, Mira watched him and wondered why he "
                        "looked so troubled, though she could not know about the "
                        "letter hidden in his coat.\n\n"
                        "Soren paced outside, sure that both of them were hiding "
                        "something from him."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "pov"},
            ),
            Case(
                name="pov-first-person-narration",
                inputs=AnalysisMetricsInput(
                    agent_type="pov",
                    text_content=(
                        "I had not expected the old woman to recognize me. When she "
                        "called me by my true name, I felt the blood drain from my "
                        "face. I smiled anyway and paid for the herbs, pretending I "
                        "did not understand."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "pov"},
            ),
            # --- ChapterSummaryAgent cases ---
            Case(
                name="summary-standard-chapter",
                inputs=AnalysisMetricsInput(
                    agent_type="summary",
                    text_content=(
                        "Chapter 9 — The Bargain\n\n"
                        "Rynne meets the river witch at midnight to trade her mother's "
                        "ring for passage across the flooded delta. The witch demands "
                        "an additional price: a memory Rynne must surrender. Rynne "
                        "chooses the memory of her brother's laughter. At dawn the "
                        "waters part long enough for a single crossing. Rynne steps "
                        "through and does not look back, though something tugs at her, "
                        "a grief whose cause she can no longer name."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "summary"},
            ),
            Case(
                name="summary-short-scene",
                inputs=AnalysisMetricsInput(
                    agent_type="summary",
                    text_content=(
                        "The blacksmith's apprentice forged a nail. It was crooked. He tried again."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "summary"},
            ),
            Case(
                name="summary-multi-event-chapter",
                inputs=AnalysisMetricsInput(
                    agent_type="summary",
                    text_content=(
                        "Chapter 14 — Reckonings\n\n"
                        "Dax exposes the traitor at the council meeting. The fleet "
                        "sets sail before the storm breaks. Mira discovers the cipher "
                        "in the captain's logs. A fire breaks out in the lower hold. "
                        "The prisoner escapes during the confusion. Two ships are lost "
                        "to the reef. Dax and Mira reconcile on the foredeck at dusk."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "summary"},
            ),
        ],
        evaluators=[
            IsInstance(type_name="AnalysisMetricsResult"),
            ReadabilitySchemaValidator(),
            POVDetectionSchemaValidator(),
            ChapterSummarySchemaValidator(),
        ],
    )
