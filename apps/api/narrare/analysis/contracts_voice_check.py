"""WRITE-010 Voice Check service contract — CharacterVoiceCheckerServiceProtocol.

Split into a focused file per RULE-04 (file-size limit). The voice-check
service orchestrates the ADR-057 hybrid checking pipeline over a single
chapter's dialogue:

- ``DialogueParser`` → attributed utterances (reused Foundation).
- ``VoiceMetricsAnalyzer`` → current per-character deterministic metrics
  (reused Foundation, ADR-021).
- ``VoiceProfileConsumer.assemble_for_checking()`` → stored profiles incl.
  ``voice_metrics`` (ADR-050 consumer contract, enriched ADR-057 D1).
- ``voice_check_scoring`` → deterministic metric-delta per character
  (Layer 2a) + the final blended score (Layer 2a).
- ``CharacterVoiceCheckerAgent`` → qualitative judgment + flagged lines,
  one LLM call for all checkable characters (Layer 2b).

The service is **read-only** (it checks; it does not profile, does not
write to KB). It **flags + scores**; it does not produce rewrites
(ADR-057 Decision 5).

Prompt resolution is Mode 1 (composer-driven, ADR-054): the service
resolves its system prompt via :class:`PromptComposer` and the governed
``voice_check`` template (``LLMIntent.VOICE`` + ``context_mode="voice_check"``),
then passes it to the :class:`CharacterVoiceCheckerAgent` constructor
(pydantic-ai binds ``system_prompt`` at construction, not at run-time).
No inline f-string feature prompt is assembled in the service (RULE-02 /
RULE-02b). The chapter dialogue + stored descriptive profile + metric-delta
flow as runtime data in the agent run prompt (user channel, RULE-02a
category 3).

See:
    :mod:`narrare.analysis.voice_check_service` — implementation.
    :mod:`narrare.analysis.schemas_voice_check` — SSE event + response models.
    ADR-057 — Voice-check checking-path contract (Decisions 1, 2, 3, 5).
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.analysis.schemas_voice_check import VoiceCheckStreamEvent


@runtime_checkable
class CharacterVoiceCheckerServiceProtocol(Protocol):
    """Protocol for the WRITE-010 voice-consistency checker service.

    Delegates to the Core-layer :class:`CharacterVoiceCheckerAgent`
    (pydantic-ai) which judges every checkable character in a single LLM
    call by interpreting their attributed chapter dialogue together with
    (a) the stored *descriptive* voice profile and (b) a deterministic
    metric-delta summary (computed by
    :mod:`narrare_core.analysis.voice_check_scoring` and supplied as runtime
    context — the agent never recomputes metrics, ADR-021).

    The checker is **read-only**: it never writes to the Knowledge Base
    (ADR-057 Decision 5 / Decision 1 producer side is ANAL-008, unchanged).

    Prompt resolution is Mode 1 (composer-driven, ADR-054): the service
    resolves its system prompt via :class:`PromptComposer` and the governed
    ``voice_check`` template (``LLMIntent.VOICE``), then passes it to the
    :class:`CharacterVoiceCheckerAgent` constructor.

    RULE-11 graceful degradation: a chapter with no attributed dialogue, or
    a speaking character with no stored profile, yields a graceful result
    (never a crash). A character with no stored profile is surfaced with
    ``has_profile=False``.
    """

    async def check(
        self,
        chapter_id: UUID,
        user_id: UUID,
    ) -> AsyncIterator[VoiceCheckStreamEvent]:
        """Check a chapter's dialogue against stored voice profiles, streaming SSE.

        Runs the ADR-057 hybrid checking pipeline over the chapter's
        attributed dialogue and yields per-character ``"result"`` events
        followed by a terminal ``"done"`` event. The pipeline is read-only:
        no KB mutation occurs (profiles are read via
        :meth:`VoiceProfileConsumer.assemble_for_checking`).

        The attributed dialogue + stored descriptive profile + metric-delta
        flow as runtime data in the agent run prompt (user channel,
        RULE-02a category 3); the governed system prompt flows through
        :class:`PromptComposer` (Mode 1).

        Args:
            chapter_id: The chapter whose dialogue is checked.
            user_id: The user requesting the check (resolved against the
                chapter's novel for access control).

        Yields:
            :class:`VoiceCheckStreamEvent` instances: a ``"progress"``
            event, one ``"result"`` event per speaking character, then a
            terminal ``"done"`` event (``is_final=True``).

        Raises:
            narrare_core.shared.errors.NotFoundError: If the chapter or its
                novel does not exist or is not accessible, or no model
                config is configured.
            narrare_core.shared.errors.ConfigurationError: If no
                ``PromptComposer`` is configured.
        """
        ...
