"""ANAL-008 Character Voice service contract — CharacterVoiceServiceProtocol.

Split from a monolithic contracts module for RULE-04 compliance. The
character-voice service orchestrates the ADR-055 hybrid pipeline
(deterministic :class:`DialogueParser` + :class:`VoiceMetricsAnalyzer` +
:class:`CharacterVoiceAgent`) over a novel's selected chapters, writes the
resulting :class:`VoiceAnalysis` to each character's KB
``metadata["speech"]["voice_analysis"]`` (bumping ``updated_at``), and
streams per-character results as SSE events so the frontend can render
progressively.

Prompt resolution is Mode 1 (composer-driven, ADR-054): the service resolves
its system prompt via :class:`PromptComposer` and the governed
``character_voice`` template (``LLMIntent.VOICE``), then passes it to the
:class:`CharacterVoiceAgent` constructor. No inline f-string feature prompt
is assembled in the service (RULE-02 / RULE-02b).

See:
    :mod:`narrare.analysis.character_voice_service` — implementation.
    :mod:`narrare.analysis.schemas_character_voice` — SSE event + response models.
    ADR-055 — Character voice storage contract (Decisions 1, 2, 3, 4).
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.analysis.schemas_character_voice import CharacterVoiceStreamEvent


@runtime_checkable
class CharacterVoiceServiceProtocol(Protocol):
    """Protocol for the ANAL-008 character-voice analysis service.

    Delegates to the Core-layer :class:`CharacterVoiceAgent` (pydantic-ai)
    which profiles every supplied character in a single LLM call by
    interpreting their attributed dialogue together with the deterministic
    :class:`VoiceMetrics` (computed by :class:`VoiceMetricsAnalyzer`).

    Prompt resolution is Mode 1 (composer-driven, ADR-054): the service
    resolves its system prompt via :class:`PromptComposer` and the governed
    ``character_voice`` template (``LLMIntent.VOICE``), then passes it to the
    :class:`CharacterVoiceAgent` constructor (pydantic-ai binds
    ``system_prompt`` at construction, not at run-time).
    """

    async def analyze(
        self,
        novel_id: UUID,
        chapter_ids: list[UUID] | None,
        user_id: UUID,
    ) -> AsyncIterator[CharacterVoiceStreamEvent]:
        """Analyse character voices across selected chapters, streaming SSE events.

        Runs the ADR-055 hybrid pipeline (deterministic metrics + LLM
        qualitative profile) over the selected chapters' dialogue, writes the
        resulting :class:`VoiceAnalysis` to each character's KB
        ``metadata["speech"]["voice_analysis"]`` (bumping ``updated_at`` so
        ``profiles/_freshness.py::is_stale()`` keeps working), and yields
        per-character ``"result"`` events followed by a terminal ``"done"``
        event.

        The attributed dialogue + per-character metrics flow as runtime data
        in the agent run prompt (user channel, RULE-02a category 3); the
        governed system prompt flows through :class:`PromptComposer` (Mode 1).

        Args:
            novel_id: The novel whose chapters are analysed.
            chapter_ids: Specific chapters to analyse, or ``None`` / empty to
                analyse every chapter in the novel.
            user_id: The user requesting analysis (for access control).

        Yields:
            :class:`CharacterVoiceStreamEvent` instances: a ``"progress"``
            event, one ``"result"`` event per profiled character, then a
            terminal ``"done"`` event (``is_final=True``).

        Raises:
            narrare_core.shared.errors.NotFoundError: If the novel or any
                selected chapter does not exist or is not accessible.
            narrare_core.shared.errors.ConfigurationError: If no
                ``PromptComposer`` is configured.
        """
        ...
