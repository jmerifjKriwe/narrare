"""Project Writing Profile — single source of truth for project metadata.

Every AI feature that needs project-level context (genre, tone, synopsis,
style) consumes this profile instead of reading individual fields from
different sources.

Loaded once per request from the Novel DB model and passed through
the layer stack as a single immutable object (FIND-007).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProjectWritingProfile:
    """Project-level writing profile — consumed by ALL AI features.

    This is the single source of truth for project metadata that
    influences LLM behavior. Every PromptContext that represents
    a project context SHOULD be built from this profile.

    Loaded once per request from the Novel DB model and passed
    through the layer stack as a single object.

    Fields are optional (default "") so partially-configured projects
    degrade gracefully.
    """

    # --- Core fields (from Novel model) ---
    project_title: str = ""
    author_name: str = ""
    genre: str = ""
    tone: str = ""
    story_structure: str = ""
    writing_language: str = ""  # output language (freetext, e.g. "Schweizerdeutsch")
    language: str = "en"  # prompt file selection (en/de/fr)

    # --- Extended writing guidance ---
    novel_synopsis: str = ""
    style_profile: str = ""

    # --- Project metadata ---
    logline: str = ""

    def to_prompt_variables(self) -> dict[str, str]:
        """Export profile fields as flat string dict for PromptContext.

        Only non-empty fields are included to avoid overwriting
        request-level overrides.
        """
        variables: dict[str, str] = {}
        for field_name in (
            "project_title",
            "author_name",
            "genre",
            "tone",
            "story_structure",
            "writing_language",
            "language",
            "novel_synopsis",
            "style_profile",
            "logline",
        ):
            value = getattr(self, field_name)
            if value:
                variables[field_name] = value
        return variables
