"""Story suggest schemas — request/response models for Writer's Unblock.

Follows the SSE event pattern used in the writing module: the
``is_final`` flag from :class:`InlineSuggestResponse` and the
type-discriminated event field from the co-author SSE stream
(``{"type": "context_meta"}``).

Split from ``schemas.py`` per RULE-04 (file-size limit).

See WRITE-009 (Writer's Unblock Tools).
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Pydantic model resolution

from pydantic import BaseModel, Field


class StorySuggestRequest(BaseModel):
    """Request for story direction suggestions (Writer's Unblock).

    The writer asks for 3-5 story suggestions to get unstuck.  An
    optional ``chapter_id`` scopes the suggestions to a specific point
    in the narrative, and ``author_instructions`` carry any specific
    direction the writer wants explored.

    Attributes:
        novel_id: Novel to generate suggestions for.
        chapter_id: Optional chapter to scope suggestions to a
            narrative point.
        author_instructions: Optional direction the writer wants
            explored (max 2000 characters).
    """

    novel_id: uuid.UUID = Field(..., description="Novel to generate suggestions for")
    chapter_id: uuid.UUID | None = Field(
        default=None,
        description="Optional chapter to scope suggestions to a narrative point",
    )
    author_instructions: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional direction the writer wants explored",
    )


class StorySuggestionResponse(BaseModel):
    """A single story direction suggestion in the API response.

    Mirrors :class:`narrare_core.agents.story_suggest_types.StorySuggestion`
    but uses plain ``str`` for the ``type`` field (the serialized enum
    value, e.g. ``"plot_development"``).

    Attributes:
        type: Suggestion category — one of ``plot_development``,
            ``character_moment``, ``dialogue_option``, ``world_detail``,
            ``stylistic_alternative``.
        title: A brief descriptive title.
        description: A one-paragraph description of the suggestion.
        connection: How this connects to established plot threads.
    """

    type: str = Field(
        ...,
        description="Suggestion category (plot_development, character_moment, etc.)",
    )
    title: str = Field(..., description="Brief descriptive title")
    description: str = Field(..., description="One-paragraph description of the suggestion")
    connection: str = Field(..., description="How this connects to established plot threads")


class StorySuggestResponse(BaseModel):
    """Non-streaming response with the full suggestion list.

    Used when the caller wants all suggestions at once rather than via
    SSE.  The SSE stream uses :class:`StorySuggestStreamEvent` instead.

    Attributes:
        suggestions: 3-5 distinct story direction suggestions.
    """

    suggestions: list[StorySuggestionResponse] = Field(
        default_factory=lambda: [],
        description="3-5 distinct story direction suggestions",
    )


class StorySuggestStreamEvent(BaseModel):
    """One event in a story-suggest SSE stream.

    Follows the writing module's SSE event pattern: the ``is_final``
    flag from :class:`InlineSuggestResponse` and the type-discriminated
    ``event`` field from the co-author SSE stream.  The ``event`` field
    discriminates between suggestion data, completion, and error
    events.

    Event types:
        - ``"suggestions"`` — carries the full suggestion list in
          ``suggestions``.
        - ``"done"`` — terminal success event (``is_final=True``).
        - ``"error"`` — terminal error event (``is_final=True``,
          ``error`` carries the message).

    Attributes:
        event: Event type — ``"suggestions"``, ``"done"``, or
            ``"error"``.
        suggestions: The full suggestion list (present on
            ``"suggestions"`` events, ``None`` otherwise).
        error: Error message (present on ``"error"`` events,
            ``None`` otherwise).
        is_final: ``True`` on the terminal event (``"done"`` or
            ``"error"``).
    """

    event: str = Field(
        default="suggestions",
        description="Event type: suggestions, done, or error",
    )
    suggestions: list[StorySuggestionResponse] | None = Field(
        default=None,
        description="Story suggestions (present on 'suggestions' events)",
    )
    error: str | None = Field(
        default=None,
        description="Error message (present on 'error' events)",
    )
    is_final: bool = Field(
        default=False,
        description="True on the terminal event (done or error)",
    )
