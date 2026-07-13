"""Variable metadata registry for prompt templates.

Maps variable names to human-readable descriptions and types,
used by the prompt management UI to display available variables.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VariableMeta:
    """Metadata for a prompt template variable."""

    name: str
    description: str
    variable_type: str  # "text", "list", "number"
    required: bool = False
    default: str = ""


# All known variables across prompt categories.
# Mirrors fields from PromptContext plus generation-specific variables.
VARIABLE_REGISTRY: dict[str, VariableMeta] = {
    # --- Project metadata ---
    "language": VariableMeta(
        "language",
        "ISO language code (en, de, fr)",
        "text",
        required=True,
    ),
    "project_title": VariableMeta(
        "project_title",
        "Title of the project/novel",
        "text",
    ),
    "genre": VariableMeta(
        "genre",
        "Genre of the work",
        "text",
    ),
    "tone": VariableMeta(
        "tone",
        "Desired tone of the writing",
        "text",
    ),
    "story_structure": VariableMeta(
        "story_structure",
        "Story structure model (three-act, hero's journey, etc.)",
        "text",
    ),
    "author_name": VariableMeta(
        "author_name",
        "Author's name",
        "text",
    ),
    # --- Novel context ---
    "novel_synopsis": VariableMeta(
        "novel_synopsis",
        "Synopsis or summary of the novel",
        "text",
    ),
    "style_profile": VariableMeta(
        "style_profile",
        "Established style characteristics",
        "text",
    ),
    # --- Chapter context ---
    "mode": VariableMeta(
        "mode",
        "Writing mode (new_chapter, extend, rewrite, etc.)",
        "text",
    ),
    "chapter_title": VariableMeta(
        "chapter_title",
        "Title of the current chapter",
        "text",
    ),
    "existing_content": VariableMeta(
        "existing_content",
        "Existing content for extend/rewrite operations",
        "text",
    ),
    "author_instructions": VariableMeta(
        "author_instructions",
        "Explicit instructions from the writer",
        "text",
    ),
    "previous_chapter_summary": VariableMeta(
        "previous_chapter_summary",
        "Summary of the preceding chapter",
        "text",
    ),
    "next_chapter_hint": VariableMeta(
        "next_chapter_hint",
        "Hint about what comes in the next chapter",
        "text",
    ),
    # --- KB context ---
    "kb_context_entries": VariableMeta(
        "kb_context_entries",
        "Relevant KB entries included in context",
        "list",
    ),
    "kb_summary": VariableMeta(
        "kb_summary",
        "Compact summary of all KB entities",
        "text",
    ),
    # --- Entity context ---
    "entity_type": VariableMeta(
        "entity_type",
        "Type of KB entity (character, location, etc.)",
        "text",
    ),
    "entity_name": VariableMeta(
        "entity_name",
        "Name of the KB entity",
        "text",
    ),
    "entity_current_content": VariableMeta(
        "entity_current_content",
        "Current content of the KB entity",
        "text",
    ),
    "entity_template": VariableMeta(
        "entity_template",
        "Template for the KB entity",
        "text",
    ),
    "entity_focus_areas": VariableMeta(
        "entity_focus_areas",
        "Areas to focus on for the entity",
        "text",
    ),
    # --- Analysis context ---
    "text_to_analyse": VariableMeta(
        "text_to_analyse",
        "Text to be analysed",
        "text",
    ),
    "analysis_focus": VariableMeta(
        "analysis_focus",
        "Focus area for the analysis",
        "text",
    ),
    # --- Generation-specific ---
    "name_type": VariableMeta(
        "name_type",
        "Type of names to generate (character, place, etc.)",
        "text",
    ),
    "count": VariableMeta(
        "count",
        "Number of items to generate",
        "number",
    ),
    "gender": VariableMeta(
        "gender",
        "Gender filter for name generation",
        "text",
    ),
    "existing_names": VariableMeta(
        "existing_names",
        "Names already in the project (avoid duplicates)",
        "text",
    ),
    "culture_guidelines": VariableMeta(
        "culture_guidelines",
        "Name-style-specific naming conventions (auto-injected)",
        "text",
    ),
    "name_style": VariableMeta(
        "name_style",
        "Name style for character/place name generation (freetext)",
        "text",
    ),
    "writing_language": VariableMeta(
        "writing_language",
        "Output language for writing generation (freetext, e.g. 'Schweizerdeutsch')",
        "text",
    ),
    "explanation_language": VariableMeta(
        "explanation_language",
        "Language for name meaning explanations (en/de/fr)",
        "text",
    ),
    # --- Memory / Preference context ---
    "user_preferences": VariableMeta(
        "user_preferences",
        "User's style preferences from feedback",
        "text",
    ),
    "avoidance_patterns": VariableMeta(
        "avoidance_patterns",
        "Patterns the user wants to avoid",
        "text",
    ),
    "style_constraints": VariableMeta(
        "style_constraints",
        "Derived style constraints",
        "text",
    ),
    "cross_session_context": VariableMeta(
        "cross_session_context",
        "Cross-session writing memories from mem0 (past observations about this project)",
        "text",
    ),
}


def get_variable_info(name: str) -> VariableMeta | None:
    """Look up variable metadata by name."""
    return VARIABLE_REGISTRY.get(name)


def get_variables_for_names(names: list[str]) -> list[VariableMeta]:
    """Get metadata for a list of variable names."""
    return [VARIABLE_REGISTRY[n] for n in names if n in VARIABLE_REGISTRY]
