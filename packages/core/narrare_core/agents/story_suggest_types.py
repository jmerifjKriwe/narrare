"""Dependency and output types for StorySuggestAgent.

Generates 3-5 story direction suggestions (plot developments, character
moments, dialogue options, world details, stylistic alternatives) to help
writers who are stuck — the "Writer's Unblock" feature.

See WRITE-009 (Writer's Unblock Tools). The output schema mirrors the JSON
format declared in the ``story_suggest`` bundled template.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class StorySuggestionType(StrEnum):
    """Category of story suggestion.

    Attributes:
        PLOT_DEVELOPMENT: A new plot direction or twist.
        CHARACTER_MOMENT: A character-focused scene or revelation.
        DIALOGUE_OPTION: A suggested dialogue exchange or line.
        WORLD_DETAIL: A world-building detail that enriches the setting.
        STYLISTIC_ALTERNATIVE: An alternative prose style or narrative approach.
    """

    PLOT_DEVELOPMENT = "plot_development"
    CHARACTER_MOMENT = "character_moment"
    DIALOGUE_OPTION = "dialogue_option"
    WORLD_DETAIL = "world_detail"
    STYLISTIC_ALTERNATIVE = "stylistic_alternative"


class StorySuggestion(BaseModel):
    """A single story direction suggestion.

    Attributes:
        type: The suggestion category.
        title: A brief descriptive title.
        description: A one-paragraph description of the suggestion.
        connection: How this connects to established plot threads.
    """

    type: StorySuggestionType
    title: str
    description: str
    connection: str


class StorySuggestOutput(BaseModel):
    """Structured output from StorySuggestAgent.

    Attributes:
        suggestions: 3-5 distinct story direction suggestions.
    """

    suggestions: list[StorySuggestion] = []


class StorySuggestDeps(BaseModel):
    """Dependencies for StorySuggestAgent — minimal runtime data.

    The full story context (KB, chapter outline, story structure, etc.) is
    assembled by the service layer into the system prompt via PromptComposer.
    These deps carry only the essential project-level fields the agent needs
    at runtime.

    Attributes:
        project_title: The project's title.
        genre: The project's genre (e.g. "Fantasy", "Sci-Fi").
        writing_language: The language to write suggestions in.
    """

    project_title: str = ""
    genre: str = ""
    writing_language: str = "en"
