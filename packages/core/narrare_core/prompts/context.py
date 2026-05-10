"""
PromptContext — carries all variables needed to render any prompt.

Every LLM call in Narrare assembles a PromptContext first,
then passes it to the PromptComposer. No service builds prompts directly.

See CONSTRAINTS.md RULE-02.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class KBContextEntry:
    """A single KB entry included in context."""

    entity_type: str
    name: str
    content: str
    relevance_score: float = 1.0


@dataclass(slots=True)
class PromptContext:
    """
    All variables available for prompt rendering.

    Fields are optional — prompts declare which they require.
    Missing required variables raise PromptVariableError at compose time.
    """

    # --- Project metadata ---
    language: str = "en"
    project_title: str = ""
    genre: str = ""
    tone: str = ""
    story_structure: str = ""
    author_name: str = ""

    # --- Novel context ---
    novel_synopsis: str = ""
    style_profile: str = ""

    # --- Chapter context ---
    mode: str = ""  # writing mode: new_chapter, extend, etc.
    chapter_title: str = ""
    existing_content: str = ""  # for extend/rewrite operations
    author_instructions: str = ""  # explicit instructions from the writer
    previous_chapter_summary: str = ""
    next_chapter_hint: str = ""

    # --- KB context ---
    kb_context_entries: list[KBContextEntry] = field(default_factory=list)  # type: ignore[reportUnknownVariableType]
    kb_summary: str = ""  # compact list of all KB entities

    # --- Entity context (KB sessions) ---
    entity_type: str = ""
    entity_name: str = ""
    entity_current_content: str = ""
    entity_template: str = ""
    entity_focus_areas: str = ""

    # --- Analysis context ---
    text_to_analyse: str = ""
    analysis_focus: str = ""

    # --- Extra variables ---
    # For feature-specific variables not covered above.
    # Keys must be valid Python identifiers.
    extra: dict[str, Any] = field(default_factory=dict)  # type: ignore[reportUnknownVariableType]

    def as_variables(self) -> dict[str, str]:
        """
        Return all context fields as a flat string dict for variable substitution.

        Combines all dataclass fields with extra variables.
        Non-string values are converted to strings.
        """
        variables: dict[str, str] = {}

        for f_name in self.__dataclass_fields__:  # type: ignore[attr-defined]
            if f_name == "extra":
                continue
            value = getattr(self, f_name)
            if isinstance(value, list):
                # Format KB entries as readable text block
                if value and isinstance(value[0], KBContextEntry):
                    variables[f_name] = self._format_kb_entries(value)  # type: ignore[reportUnknownArgumentType]
                else:
                    variables[f_name] = "\n".join(str(v) for v in value)  # type: ignore[reportUnknownVariableType, reportUnknownArgumentType]
            else:
                variables[f_name] = str(value) if value is not None else ""

        # Extra variables override dataclass fields
        for key, value in self.extra.items():
            variables[key] = str(value) if value is not None else ""

        return variables

    @staticmethod
    def _format_kb_entries(entries: list[KBContextEntry]) -> str:
        """Format KB entries as a readable text block for injection."""
        if not entries:
            return ""
        parts: list[str] = []
        for entry in entries:
            parts.append(f"### {entry.entity_type.title()}: {entry.name}\n{entry.content}")  # type: ignore[reportUnknownMemberType]
        return "\n\n".join(parts)
