"""Planning-category mode definitions for invocation probes.

One tuple per mode: (feature_id, mode, intent, dynamic_inputs).
Split from mode_data.py for RULE-04 compliance (file-size limit).

RULE-06: One responsibility — planning mode definitions only.
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent

#: Planning modes with their required dynamic inputs.
PLANNING_MODES: list[tuple[str, str, LLMIntent, dict[str, str]]] = [
    (
        "planning",
        "outline",
        LLMIntent.PLAN,
        {
            "project_title": "Test Story",
            "genre": "Fantasy",
            "tone": "dark",
        },
    ),
    (
        "planning",
        "temporal_consistency",
        LLMIntent.PLAN,
        {
            "chapter_texts": "Chapter 1: dawn. Chapter 2: noon.",
        },
    ),
    (
        "planning",
        "character_arc",
        LLMIntent.PLAN,
        {
            "project_title": "Test Story",
            "genre": "Fantasy",
            "character_name": "Hero",
        },
    ),
    (
        "planning",
        "timeline_extraction",
        LLMIntent.PLAN,
        {
            "project_title": "Test Story",
            "genre": "Fantasy",
        },
    ),
    (
        "planning",
        "timeline",
        LLMIntent.PLAN,
        {
            "project_title": "Test Story",
            "genre": "Fantasy",
        },
    ),
]
