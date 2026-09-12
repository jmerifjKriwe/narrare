"""Prompt variable provenance registry.

Every bundled template variable must appear in exactly one registry so prompt
governance can distinguish direct user content from trusted system data and
feature-specific runtime data (INFRA-012 / RULE-22).

Variable Naming Convention:
- ``explanation_language`` — separate variable for name meaning explanations
  (distinct from writing_language)
"""

from __future__ import annotations

from narrare_core.prompts.variable_taxonomy import (
    VariableClassification,
    VariableProvenance,
    VariableSecurity,
    build_variable_classifications,
)

__all__ = [
    "FEATURE_DYNAMIC_VARS",
    "SYSTEM_VARS",
    "USER_CONTENT_VARS",
    "VARIABLE_CLASSIFICATIONS",
    "VariableClassification",
    "VariableProvenance",
    "VariableSecurity",
    "get_variable_classification",
    "is_registered_variable",
]


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
        "candidate_pairs",
        "conversation_history",
        "entity_name",
        "entity_current_content",
        "entity_body",
        # ADR-069: user-authored dialogue selection for DIALOGUE_COACH.
        # Must be XML-tag-wrapped in the Phase 4 template per RULE-22 §6.
        "text_to_analyze",
    }
)

SYSTEM_VARS: frozenset[str] = frozenset(
    {
        "recent_chapters",
        "chapter_outline",
        "chapter_context",
        "chapter_summaries",
        "kb_characters",
        "kb_locations",
        "kb_factions",
        "kb_relationships",
        "kb_entities",
        "kb_suggested",
        # ADR-050 P1-D: kb_pinned / kb_timelines / kb_systems are
        # produced by WritingContext.to_prompt_variables() but were
        # absent from the registry, leaving the ratcheted baseline
        # with an undocumented gap. Registered here so future
        # templates that reference them resolve cleanly.
        "kb_pinned",
        "kb_timelines",
        "kb_systems",
        # CR-AUFG-04-04: catch-all bucket for unclassified entity types,
        # produced by WritingContext.to_prompt_variables(). Registered so
        # templates referencing {{kb_other}} resolve without PromptVariableError.
        "kb_other",
        # CR-AUFG-04-06: orphan-reference warnings promoted into the prompt so
        # dangling frontmatter references are surfaced to the LLM instead of
        # silently dropped. Produced by WritingContext.to_prompt_variables();
        # empty string when there are no warnings. System-generated diagnostic.
        "kb_context_warnings",
        "existing_names",
        "existing_relationships",
        "existing_entity_names",
        "existing_events",
        "existing_plot_points",
        "user_preferences",
        "avoidance_patterns",
        "style_constraints",
        "cross_session_context",
        "style_profile",
        "character_voice_profiles",
        # ADR-074 / ANAL-007 Q3 decision: {{author_voice}} is the
        # author-voice analogue of {{character_voice_profiles}}. System-
        # attributed descriptive text rendered from a machine-derived stored
        # profile (the AuthorVoiceConsumer curates it from the author's prose)
        # — NOT user-authored prompt content, so no XML-wrapping is required
        # (RULE-22 §6 does not apply). Mirrors {{character_voice_profiles}}.
        "author_voice",
        # Spec 2 / SERIES-002: series-history context block (BandSummary
        # recency-window text), assembled by SeriesHistoryTier in the Backend
        # and injected at generation time. System-generated narrative context
        # (not user-authored) — empty for standalone novels (RULE-11 graceful).
        "series_history",
        # ADR-069: system-attributed speaker list for DIALOGUE_COACH.
        # Produced by DialogueParser-backed attribution (ADR-055 D3).
        "characters",
        "character_name",
        "character_current_state",
        "character_goal_state",
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
        "writing_language",
        "tone",
        "tone_instructions",
        "story_structure",
        "author_name",
        "culture_guidelines",
        "novel_synopsis",
        "word_target",
        # Item-3 (2026-09-10): scene-position metadata for the WRITE
        # context-mode scene_by_scene. Supplied per scene by
        # stream_scene_by_scene (pipeline_scene.py) via extra_overrides
        # and rendered by the scene_by_scene template numbering line.
        "scene_number",
        "total_scenes",
        # R2 beta_reader slice (2026-09-12): word_count / chapter_titles /
        # focus_categories / previous_summaries were used exclusively by the
        # beta_reader system template's context blocks, deleted as dead
        # duplicates of the user channel (build_budgeted_prompt) — pruned
        # together with those blocks. No other bundled template references
        # them.
        "extend_length",
        "chapter_title",
        "count",
        "event_count",
        "check_types",
        "co_author_focus_instructions",
        "rewrite_mode_instructions",
        # CR-AUFG-07-22: style-variant creative-direction text injected into
        # the rewrite_selection template. System-injected (not user content,
        # not feature-dynamic) — analogous to rewrite_mode_instructions.
        "style_variant_instructions",
        # R2 beta_reader_deepdive slice (2026-09-12): deepdive_category /
        # phase1_strengths_summary / phase1_feedback_summary were used
        # exclusively by the beta_reader_deepdive system template's context
        # blocks, deleted as dead duplicates of the user channel
        # (build_deepdive_prompt via deep_dive_deps); category_focus_instructions
        # had no runtime supplier at all. Pruned together with those blocks —
        # the BetaReaderDeps fields remain user-channel data, outside this
        # registry. chapter_text stays in USER_CONTENT_VARS (RULE-22
        # user-content hygiene, not a usage-ledger entry).
        "available_rel_types",
        "gender",
        "name_type",
        "structure_type",
        "summary",
        "mode",
    }
)

FEATURE_DYNAMIC_VARS: frozenset[str] = frozenset(
    {
        "entity_events",
        "explanation_language",
        "extracted_facts",
        "relationships",
        "timeline_events",
        "timeline_position",
        "variant_count",
    }
)

VARIABLE_CLASSIFICATIONS: dict[str, VariableClassification] = build_variable_classifications(
    USER_CONTENT_VARS,
    SYSTEM_VARS,
    FEATURE_DYNAMIC_VARS,
)


def get_variable_classification(name: str) -> VariableClassification | None:
    """Return provenance/security metadata for a prompt variable."""
    return VARIABLE_CLASSIFICATIONS.get(name)


def is_registered_variable(name: str) -> bool:
    """Return whether a prompt variable is in the governed taxonomy."""
    return name in VARIABLE_CLASSIFICATIONS
