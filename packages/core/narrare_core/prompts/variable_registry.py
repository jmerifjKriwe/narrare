"""Prompt variable provenance registry.

Every bundled template variable must appear in exactly one registry so prompt
governance can distinguish direct user content from trusted system data and
feature-specific runtime data (INFRA-012 / RULE-22).
"""

from __future__ import annotations

USER_CONTENT_VARS: frozenset[str] = frozenset(
    {
        "existing_content",
        "chapter_text",
        "chapter_texts",
        "entry_content",
        "selection_text",
        "context_before",
        "context_after",
        "text_before",
        "text_after",
        "existing_answers",
        "author_instructions",
        "conversation_history",
        "entity_name",
        "entity_current_content",
        "entity_body",
    }
)

SYSTEM_VARS: frozenset[str] = frozenset(
    {
        "recent_chapters",
        "chapter_content",
        "chapter_outline",
        "chapter_context",
        "chapter_summaries",
        "kb_characters",
        "kb_locations",
        "kb_factions",
        "kb_relationships",
        "kb_entities",
        "kb_suggested",
        "existing_names",
        "existing_relationships",
        "existing_entity_names",
        "existing_events",
        "existing_plot_points",
        "user_preferences",
        "avoidance_patterns",
        "style_constraints",
        "style_profile",
        "character_voice_profiles",
        "character_name",
        "character_current_state",
        "character_goal_state",
        "feedback_text",
        "template_structure",
        "template_structures",
        "world_context",
        "entity_type",
        "entity_summaries",
        "entity_details",
        "entity_metadata",
        "entities_in_chapter",
        "target_field",
        "target_field_description",
        "project_title",
        "genre",
        "language",
        "writing_language",
        "tone",
        "tone_instructions",
        "story_structure",
        "author_name",
        "culture_guidelines",
        "novel_synopsis",
        "word_target",
        "word_count",
        "extend_length",
        "chapter_title",
        "chapter_titles",
        "count",
        "event_count",
        "event_context",
        "focus_categories",
        "check_types",
        "co_author_focus_instructions",
        "rewrite_mode_instructions",
        "deepdive_category",
        "phase1_strengths_summary",
        "phase1_feedback_summary",
        "category_focus_instructions",
        "available_rel_types",
        "gender",
        "known_characters",
        "name_type",
        "pov_type_hint",
        "previous_summaries",
        "structure_type",
        "summary",
        "mode",
    }
)

FEATURE_DYNAMIC_VARS: frozenset[str] = frozenset(
    {
        "candidate_pairs",
        "entity_events",
        "explanation_language",
        "relationships",
        "timeline_position",
        "variant_count",
    }
)
