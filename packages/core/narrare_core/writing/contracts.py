"""Protocol contracts for the writing subsystem.

Defines the interfaces that writing adapters must implement.
All implementations are injected via constructor (DI pattern).

RULE-03: These protocols exist *before* any implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare_core.llm.result import StreamChunk
    from narrare_core.writing._enums import GenerationMode
    from narrare_core.writing.models import (
        GenerationRequest,
        SessionState,
        WritingContext,
    )


class WritingPipelineProtocol(Protocol):
    """Orchestrates the writing generation pipeline in 4 modes.

    The pipeline delegates to a :class:`ContextAssemblerProtocol` for
    context assembly and streams text chunks back to the caller.
    """

    async def generate(
        self,
        request: GenerationRequest,
        *,
        custom_tone_instructions: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream generated text chunks for the given request.

        Yields ``StreamChunk`` instances containing text fragments.
        The final chunk has ``is_final=True`` and includes token usage.

        Args:
            request: The generation request with mode, tone, etc.
            custom_tone_instructions: User-defined tone instructions
                to override bundled tones.
        """
        ...

    async def stop(self, request_id: UUID) -> None:
        """Stop an in-progress generation.

        No-op if the request has already completed or does not exist.
        """
        ...


class ContextAssemblerProtocol(Protocol):
    """Assembles writing context from 5 tiers of information.

    The assembler collects chapter content, recent history, KB entities,
    pinned items, and user memory into a single :class:`WritingContext`
    ready for prompt injection.
    """

    async def assemble(
        self,
        chapter_id: UUID,
        project_id: UUID,
        *,
        mode: GenerationMode,
        outline: str | None = None,
        prompt: str | None = None,
        auto_continue: bool = False,
    ) -> WritingContext:
        """Assemble the full writing context for a chapter.

        Keyword arguments override outline / prompt derived from the
        chapter itself.  ``auto_continue`` hints that context should be
        optimised for continuation rather than fresh generation.
        """
        ...


class DraftProcessorProtocol(Protocol):
    """Post-processes generated text.

    Handles cleanup, normalisation, and word-target enforcement so
    that raw LLM output becomes clean, consistent prose.
    """

    def process(
        self,
        text: str,
        *,
        word_target: int | None = None,
        is_partial: bool = False,
    ) -> str:
        """Clean and normalise generated text.

        Parameters
        ----------
        text:
            Raw LLM output to process.
        word_target:
            If set, attempt to trim or pad to roughly this word count.
        is_partial:
            ``True`` when the text is a mid-stream fragment (e.g. for
            real-time preview).  Disables trailing-punctuation fixes.
        """
        ...


class SessionManagerProtocol(Protocol):
    """Manages interactive writing session state.

    A session represents one ``interactive_session`` or
    ``interview_assisted`` writing flow for a single chapter.  It tracks
    conversation history and accumulates accepted prose in a buffer.
    """

    async def create_session(
        self,
        chapter_id: UUID,
        project_id: UUID,
        user_id: UUID,
    ) -> UUID:
        """Create a new interactive session, return session ID."""
        ...

    async def add_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
    ) -> None:
        """Add a message to session history.

        ``role`` is typically ``"user"``, ``"assistant"``, or
        ``"system"``.
        """
        ...

    async def get_session(self, session_id: UUID) -> SessionState | None:
        """Retrieve current session state.

        Returns ``None`` if the session does not exist or has ended.
        """
        ...

    async def append_prose(
        self,
        session_id: UUID,
        text: str,
    ) -> None:
        """Append accepted text to the prose buffer."""
        ...

    async def save_to_chapter(self, session_id: UUID) -> str:
        """Save prose buffer as chapter draft, return content.

        The prose buffer is preserved — call :meth:`end_session` to
        clear it.
        """
        ...

    async def end_session(self, session_id: UUID) -> None:
        """End session and clean up.

        Marks the session as inactive and releases any held resources.
        """
        ...
