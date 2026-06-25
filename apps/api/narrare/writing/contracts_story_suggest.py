"""Story suggest service contract — written before implementation.

Follows the same Protocol-first pattern as ``contracts_rewrite.py`` and
``contracts_coauthor.py`` (RULE-03: Contract before implementation).

Split from ``contracts.py`` per RULE-04 (file-size limit).

See WRITE-009 (Writer's Unblock Tools).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.writing.schemas_story_suggest import (
        StorySuggestRequest,
        StorySuggestStreamEvent,
    )


@runtime_checkable
class StorySuggestServiceProtocol(Protocol):
    """Protocol for the story suggestion service (Writer's Unblock).

    Generates 3-5 story direction suggestions to help writers who are
    stuck.  The service runs the :class:`StorySuggestAgent` and yields
    SSE events carrying the structured suggestions.

    Unlike the streaming-text services (rewrite, co-author, inline
    suggest), this service produces structured output — the agent
    returns a :class:`StorySuggestOutput` with a list of suggestions
    rather than incremental text chunks.  The SSE stream therefore
    emits a single ``"suggestions"`` event with the full list, followed
    by a ``"done"`` termination event.
    """

    async def suggest(
        self,
        novel_id: UUID,
        user_id: UUID,
        request: StorySuggestRequest,
    ) -> AsyncIterator[StorySuggestStreamEvent]:
        """Generate story direction suggestions for a novel.

        Runs the :class:`StorySuggestAgent` with project context (title,
        genre, story structure, chapter outline) and the writer's
        optional ``author_instructions``.  Yields SSE events: a
        ``"suggestions"`` event with the full suggestion list, followed
        by a ``"done"`` event.

        Args:
            novel_id: Novel to generate suggestions for.
            user_id: Authenticated user identifier.
            request: Story suggest request with optional ``chapter_id``
                and ``author_instructions``.

        Yields:
            :class:`StorySuggestStreamEvent` instances.  The final
            event has ``is_final=True``.

        Raises:
            NotFoundError: If the novel does not exist.
            ConfigurationError: If no model config or PromptComposer
                is configured.
        """
        ...
