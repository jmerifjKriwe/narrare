"""Preference analysis Pydantic Evals dataset."""

from __future__ import annotations

from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance

from evals.evaluators import PreferenceSignalCoverage
from evals.models import PreferenceAnalysisInput, PreferenceAnalysisResult


def build_dataset() -> Dataset[PreferenceAnalysisInput, PreferenceAnalysisResult, dict[str, Any]]:
    """Build the preference analysis eval dataset."""

    return Dataset(
        name="preference_analysis",
        cases=[
            Case(
                name="concise-dialogue",
                inputs=PreferenceAnalysisInput(
                    genre="Fantasy",
                    event_count=12,
                    feedback_text=(
                        "Accepted: shorter dialogue beats, direct conflict, brisk pacing. "
                        "Rejected: ornate exposition and long scenic description."
                    ),
                ),
                expected_output=None,
                metadata={
                    "style_keywords": ["concise", "brisk"],
                    "content_keywords": ["dialogue", "conflict"],
                    "avoidance_keywords": ["exposition", "description"],
                },
            ),
            Case(
                name="sensory-but-no-cliffhanger",
                inputs=PreferenceAnalysisInput(
                    genre="Mystery",
                    event_count=9,
                    feedback_text=(
                        "Accepted: sensory clues and emotional subtext. "
                        "Rejected: abrupt cliffhangers and sarcastic narrator asides."
                    ),
                ),
                expected_output=None,
                metadata={
                    "style_keywords": ["sensory", "subtext"],
                    "content_keywords": ["clues"],
                    "avoidance_keywords": ["cliffhangers", "sarcastic"],
                },
            ),
        ],
        evaluators=[IsInstance(type_name="PreferenceAnalysisResult"), PreferenceSignalCoverage()],
    )
