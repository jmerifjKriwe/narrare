"""Dataset registry for Pydantic Evals suites."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic_evals import Dataset

from evals.datasets.analysis_feedback import build_dataset as build_analysis_feedback_dataset
from evals.datasets.analysis_metrics import build_dataset as build_analysis_metrics_dataset
from evals.datasets.chat_generation import build_dataset as build_chat_generation_dataset
from evals.datasets.consistency_staged import build_dataset as build_consistency_staged_dataset
from evals.datasets.dialogue_coach import build_dataset as build_dialogue_coach_dataset
from evals.datasets.kb_extraction import build_dataset as build_kb_extraction_dataset
from evals.datasets.kb_operations import build_dataset as build_kb_operations_dataset
from evals.datasets.names import build_dataset as build_names_dataset
from evals.datasets.planning_structure import build_dataset as build_planning_structure_dataset
from evals.datasets.preference_analysis import build_dataset as build_preference_analysis_dataset
from evals.datasets.rewrite_selection import build_dataset as build_rewrite_selection_dataset
from evals.datasets.writing_prose import build_dataset as build_writing_prose_dataset

DatasetFactory = Callable[[], Dataset[Any, Any, dict[str, Any]]]

DATASET_FACTORIES: dict[str, DatasetFactory] = {
    "analysis_feedback": build_analysis_feedback_dataset,
    "analysis_metrics": build_analysis_metrics_dataset,
    "chat_generation": build_chat_generation_dataset,
    "consistency_staged": build_consistency_staged_dataset,
    "dialogue_coach": build_dialogue_coach_dataset,
    "kb_extraction": build_kb_extraction_dataset,
    "kb_operations": build_kb_operations_dataset,
    "names": build_names_dataset,
    "planning_structure": build_planning_structure_dataset,
    "preference_analysis": build_preference_analysis_dataset,
    "rewrite_selection": build_rewrite_selection_dataset,
    "writing_prose": build_writing_prose_dataset,
}


def available_suites() -> list[str]:
    """Return suite names in stable CLI order."""

    return sorted(DATASET_FACTORIES)
