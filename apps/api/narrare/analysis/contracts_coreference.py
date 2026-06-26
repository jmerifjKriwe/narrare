"""ANAL-005 Coreference service contract — CoreferenceServiceProtocol.

Split from contracts.py for RULE-04 compliance (< 200 lines).

The coreference service resolves pronoun references to character names,
tracks character mentions, and scores referential clarity via the
``CoreferenceAgent`` (Core layer). Results are streamed as SSE events
so the frontend can render progressively.

See:
    :mod:`narrare.analysis.coreference_service` — implementation.
    :mod:`narrare.analysis.schemas_coreference` — SSE event + response models.
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.analysis.schemas_coreference import CoreferenceStreamEvent


@runtime_checkable
class CoreferenceServiceProtocol(Protocol):
    """Protocol for the ANAL-005 coreference analysis service.

    Delegates to ``CoreferenceAgent`` (pydantic-ai) which performs full
    coreference resolution: pronoun-to-referent mapping, ambiguity
    detection, character-mention tracking, and clarity scoring.

    Prompt resolution is Mode 1 (composer-driven, ADR-054): the service
    resolves its system prompt via ``PromptComposer`` and the
    ``coreference`` governed template, then passes it to the
    ``CoreferenceAgent`` constructor.
    """

    async def analyze(
        self,
        chapter_id: UUID,
        user_id: UUID,
    ) -> AsyncIterator[CoreferenceStreamEvent]:
        """Analyse coreference for a single chapter, streaming SSE events.

        The chapter text flows as runtime data in the agent run prompt
        (user channel, RULE-02a category 3); the governed system prompt
        flows through ``PromptComposer`` (Mode 1).

        Args:
            chapter_id: The chapter to analyse.
            user_id: The user requesting analysis (for access control
                — resolved against the chapter's novel).

        Yields:
            :class:`CoreferenceStreamEvent` instances: a ``"result"``
            event carrying the full analysis, then a terminal ``"done"``
            event (``is_final=True``).

        Raises:
            narrare_core.shared.errors.NotFoundError: If the chapter or
                its novel does not exist or is not accessible.
            narrare_core.shared.errors.ConfigurationError: If no model
                config or ``PromptComposer`` is configured.
        """
        ...
