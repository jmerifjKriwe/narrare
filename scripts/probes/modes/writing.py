"""Writing-category mode definitions for invocation probes.

One tuple per mode: (feature_id, mode, intent, dynamic_inputs).
Split from mode_data.py for RULE-04 compliance (file-size limit).

RULE-06: One responsibility — writing mode definitions only.
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent

#: Writing modes with their required dynamic inputs.
WRITING_MODES: list[tuple[str, str, LLMIntent, dict[str, str]]] = [
    (
        "writing",
        "chat",
        LLMIntent.CHAT,
        {
            "conversation_history": "",
            "user_message": "Tell me about my story",
        },
    ),
    (
        "writing",
        "new_chapter",
        LLMIntent.WRITE,
        {
            "chapter_title": "The Beginning",
            "outline": "Story outline",
        },
    ),
    (
        "writing",
        "extend_chapter",
        LLMIntent.EXTEND,
        {
            "existing_content": "The hero arrived at the gate.",
        },
    ),
    (
        "writing",
        "rewrite_selection",
        LLMIntent.REWRITE,
        {
            "selection_text": "The dialogue felt flat.",
            "rewrite_mode_instructions": "Make it more dramatic.",
        },
    ),
    (
        "writing",
        "story_suggest",
        LLMIntent.SUGGEST,
        {
            "story_context": "A dark forest",
        },
    ),
    (
        "writing",
        "interactive_session",
        LLMIntent.CHAT,
        {
            "conversation_history": "",
            "user_message": "Continue the scene",
        },
    ),
    (
        "writing",
        "interview",
        LLMIntent.CHAT,
        {
            "conversation_history": "",
            "user_message": "Tell me about the protagonist",
        },
    ),
    (
        "writing",
        "scene_by_scene",
        LLMIntent.WRITE,
        {
            "chapter_title": "Chapter 3",
            "outline": "Scene breakdown",
        },
    ),
    (
        "writing",
        "inline_suggest",
        LLMIntent.SUGGEST,
        {
            "text_before": "The hero ",
            "text_after": " walked forward.",
        },
    ),
    (
        "writing",
        "co_author",
        LLMIntent.CO_AUTHOR,
        {
            "selection_text": "The dialogue felt flat.",
            "focus": "dialogue",
        },
    ),
]
