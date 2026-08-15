"""KB-category mode definitions for invocation probes.

One tuple per mode: (feature_id, mode, intent, dynamic_inputs).
Split from mode_data.py for RULE-04 compliance (file-size limit).

RULE-06: One responsibility — KB mode definitions only.
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent

#: KB modes with their required dynamic inputs.
KB_MODES: list[tuple[str, str, LLMIntent, dict[str, str]]] = [
    (
        "kb",
        "consistency",
        LLMIntent.KB_CONSISTENCY,
        {
            "entity_type": "character",
            "entry_content": "A brave hero.",
        },
    ),
    (
        "kb",
        "worldbuilding/phase1",
        LLMIntent.KB_WORLDBUILD,
        {
            "entity_summaries": "Summary of entities.",
        },
    ),
    (
        "kb",
        "worldbuilding/phase2",
        LLMIntent.KB_WORLDBUILD,
        {
            "entity_details": "Details of entity pairs.",
        },
    ),
    (
        "kb",
        "improve",
        LLMIntent.KB_IMPROVE,
        {
            "entity_type": "character",
            "entry_content": "A brave hero.",
        },
    ),
    (
        "kb",
        "suggest",
        LLMIntent.KB_SUGGEST,
        {
            "template_structure": "name, description",
            "target_field": "description",
            "existing_answers": '{"name": "Mirkwood"}',
        },
    ),
    (
        "kb",
        "interview",
        LLMIntent.KB_INTERVIEW,
        {
            "template_structure": "name, description",
            "existing_answers": '{"name": "Mirkwood"}',
        },
    ),
    (
        "kb",
        "extract",
        LLMIntent.KB_EXTRACT,
        {
            "chapter_text": "Extract entities from this text.",
        },
    ),
    (
        "kb",
        "enhance",
        LLMIntent.KB_ENHANCE,
        {
            "entity_type": "character",
            "template_structure": "name, description",
            "existing_answers": '{"name": "Mirkwood"}',
        },
    ),
    (
        "kb",
        "merge",
        LLMIntent.KB_CONSISTENCY,
        {
            "entity_type": "character",
            "candidate_pairs": (
                '[{"id_A": "h", "id_B": "p", "name_A": "Hero", "name_B": "Protagonist"}]'
            ),
            "world_context": "A fantasy novel about a hero's journey.",
        },
    ),
]
