"""Generation-category mode definitions for invocation probes.

One tuple per mode: (feature_id, mode, intent, dynamic_inputs).
Split from mode_data.py for RULE-04 compliance (file-size limit).

RULE-06: One responsibility — generation mode definitions only.
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent

#: Generation modes with their required dynamic inputs.
GENERATION_MODES: list[tuple[str, str, LLMIntent, dict[str, str]]] = [
    (
        "generation",
        "names",
        LLMIntent.NAME_GENERATE,
        {
            "name_type": "character",
            "count": "5",
            "writing_language": "en",
        },
    ),
]
