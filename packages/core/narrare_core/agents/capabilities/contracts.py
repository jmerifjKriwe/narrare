"""Contracts for prompt-related Capabilities.

Defines the PromptDeps and PromptContextDeps protocols that Deps types
should implement for Capabilities that inject prompt content.

See ADR-026 (Capability-Based Prompt Injection Pattern).
"""

from __future__ import annotations

from typing import Protocol


class PromptDeps(Protocol):
    """Protocol for Deps types that provide language context to Capabilities.

    This is the MINIMUM interface that ALL Capabilities need. Every Deps type
    that will be passed to a NarrareAgent should implement at least this protocol.

    Capabilities access additional fields via getattr() with fallbacks,
    following the pattern established by NarrareObservability. This avoids
    requiring all Deps types to implement a full protocol while still providing
    type-safe contracts for Capabilities that need them.

    Implementation example::

        class WritingDeps:
            # ... other fields ...

            @property
            def language(self) -> str:
                return self._language

    Or simply as a plain attribute::

        class SummaryDeps:
            def __init__(self, language: str = "en", ...):
                self.language = language
    """

    @property
    def language(self) -> str:
        """ISO 639-1 language code for the current request (e.g., 'en', 'de', 'fr').

        Used by Capabilities to select the correct language variant of
        prompt content (universal rules, meta-prompt, etc.).
        """
        ...


class PromptContextDeps(PromptDeps, Protocol):
    """Extended protocol for Deps types that provide richer prompt context.

    Capabilities that need genre, tone, or writing language information
    (e.g., NarrareMeta, NarrareUniversalRules with genre-specific rules)
    should use this protocol.

    Deps types that don't have these fields can still be used with
    Capabilities — the Capabilities will use getattr() with fallbacks
    for optional fields.

    Implementation example::

        class WritingDeps:
            # ... other fields ...

            @property
            def language(self) -> str:
                return self._language

            @property
            def writing_language(self) -> str:
                return self._writing_language

            @property
            def genre(self) -> str | None:
                return self._genre
    """

    @property
    def writing_language(self) -> str:
        """The language the output should be written in.

        May differ from `language` (e.g., language='en' but writing_language='de'
        for a German writing session with English UI).

        Falls back to `language` if not explicitly set.
        """
        ...

    @property
    def genre(self) -> str | None:
        """The genre of the current project (e.g., 'Fantasy', 'Thriller').

        None if not specified. Used by Capabilities that inject
        genre-specific prompt content.
        """
        ...
