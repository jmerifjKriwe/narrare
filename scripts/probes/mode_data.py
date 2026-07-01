"""Shared mode data for invocation probes.

Centralizes the per-mode (feature_id, mode, intent, inputs) tuples
used by preference enrichment and other probes. Single source of truth
for which modes exist and what inputs they need.

RULE-06: One responsibility — mode definitions only.
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent

#: All modes across all categories with their required dynamic inputs.
#: SSOT for which modes need probe coverage (preference_enrichment, etc.).
#: When adding new modes with ``requires_runtime_evidence: true`` in the
#: adoption registry, add them here AND in validation_budget_probes.py.
ALL_MODES: list[tuple[str, str, LLMIntent, dict[str, str]]] = [
    # ── Writing modes ──────────────────────────────────────────────
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
    # ── Analysis modes ─────────────────────────────────────────────
    (
        "analysis",
        "beta_reader",
        LLMIntent.BETA_READ,
        {
            "chapter_text": "The chapter needed work.",
        },
    ),
    (
        "analysis",
        "beta_reader_deepdive",
        LLMIntent.BETA_READ,
        {
            "chapter_text": "Deep dive analysis text.",
        },
    ),
    (
        "analysis",
        "review",
        LLMIntent.ANALYSE,
        {
            "chapter_text": "The chapter needed work.",
        },
    ),
    (
        "analysis",
        "preferences",
        LLMIntent.VOICE,
        {
            "chapter_text": "Voice analysis sample text.",
        },
    ),
    (
        "analysis",
        "character_voice",
        LLMIntent.VOICE,
        {
            "chapter_text": "Character voice analysis sample text.",
        },
    ),
    # ADR-057 D3 / WRITE-010: voice_check is the second VOICE context_mode
    # (a flag+score checker, distinct from the character_voice profiler). It
    # shares LLMIntent.VOICE; the runtime path resolves the governed
    # analysis/voice_check template via Mode 1 + CharacterVoiceCheckerAgent.
    (
        "analysis",
        "voice_check",
        LLMIntent.VOICE,
        {
            "chapter_text": "Voice check dialogue sample text.",
        },
    ),
    (
        "analysis",
        "summarize",
        LLMIntent.SUMMARIZE,
        {
            "chapter_text": "Summary sample text.",
        },
    ),
    (
        "analysis",
        "remap",
        LLMIntent.ANALYSE,
        {
            "chapter_text": "Remap analysis text.",
        },
    ),
    (
        "analysis",
        "consistency",
        LLMIntent.CONSISTENCY,
        {
            "chapter_text": "Consistency check text.",
        },
    ),
    (
        "analysis",
        "fact_extraction",
        LLMIntent.FACT_EXTRACT,
        {
            "chapter_text": "Fact extraction sample text.",
        },
    ),
    (
        "analysis",
        "readability",
        LLMIntent.ANALYSE,
        {
            "chapter_text": "Readability analysis sample passage with complex sentence structures.",
        },
    ),
    (
        "analysis",
        "pov",
        LLMIntent.ANALYSE,
        {
            "chapter_text": "POV detection analysis sample passage.",
        },
    ),
    (
        "analysis",
        "coreference",
        LLMIntent.ANALYSE,
        {
            "chapter_text": "Coreference resolution sample passage with pronouns.",
        },
    ),
    # ── KB modes ───────────────────────────────────────────────────
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
    # ── Planning modes ─────────────────────────────────────────────
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
    # ── Generation modes ───────────────────────────────────────────
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
