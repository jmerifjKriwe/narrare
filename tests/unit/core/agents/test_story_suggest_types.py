"""Tests for StorySuggestAgent output models and deps.

Split from test_story_suggest_agent.py per RULE-04 (file size limit).

See WRITE-009 (Writer's Unblock Tools).
"""

from __future__ import annotations

from narrare_core.agents.story_suggest_types import (
    StorySuggestDeps,
    StorySuggestion,
    StorySuggestionType,
    StorySuggestOutput,
)

# ---------------------------------------------------------------------------
# A. StorySuggestDeps
# ---------------------------------------------------------------------------


class TestStorySuggestDeps:
    """StorySuggestDeps creates correctly with defaults and custom values."""

    def test_deps_defaults(self) -> None:
        """Default deps have empty project_title/genre and 'en' language."""
        deps = StorySuggestDeps()
        assert deps.project_title == ""
        assert deps.genre == ""
        assert deps.writing_language == "en"

    def test_deps_custom_values(self) -> None:
        """All fields can be set at construction."""
        deps = StorySuggestDeps(
            project_title="The Last Kingdom",
            genre="Fantasy",
            writing_language="de",
        )
        assert deps.project_title == "The Last Kingdom"
        assert deps.genre == "Fantasy"
        assert deps.writing_language == "de"


# ---------------------------------------------------------------------------
# B. Output models
# ---------------------------------------------------------------------------


class TestStorySuggestOutput:
    """StorySuggestOutput and StorySuggestion validate correctly."""

    def test_output_defaults(self) -> None:
        """Default output has an empty suggestions list."""
        output = StorySuggestOutput()
        assert output.suggestions == []

    def test_suggestion_with_all_fields(self) -> None:
        """A fully-populated suggestion validates."""
        suggestion = StorySuggestion(
            type=StorySuggestionType.PLOT_DEVELOPMENT,
            title="The Hidden Heir",
            description="A long-lost letter reveals the protagonist's royal lineage.",
            connection="Resolves the mystery of the sealed chamber from Chapter 3.",
        )
        assert suggestion.type == StorySuggestionType.PLOT_DEVELOPMENT
        assert suggestion.title == "The Hidden Heir"
        assert "royal lineage" in suggestion.description
        assert "Chapter 3" in suggestion.connection

    def test_suggestion_type_values(self) -> None:
        """All five suggestion types have correct string values."""
        assert StorySuggestionType.PLOT_DEVELOPMENT == "plot_development"
        assert StorySuggestionType.CHARACTER_MOMENT == "character_moment"
        assert StorySuggestionType.DIALOGUE_OPTION == "dialogue_option"
        assert StorySuggestionType.WORLD_DETAIL == "world_detail"
        assert StorySuggestionType.STYLISTIC_ALTERNATIVE == "stylistic_alternative"

    def test_output_serialization(self) -> None:
        """Output serializes to dict with suggestions list."""
        output = StorySuggestOutput(
            suggestions=[
                StorySuggestion(
                    type=StorySuggestionType.DIALOGUE_OPTION,
                    title="A Sharp Reply",
                    description="The mentor challenges the hero's resolve.",
                    connection="Echoes the mentor's warning from Chapter 1.",
                ),
            ],
        )
        data = output.model_dump()
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["type"] == "dialogue_option"
