"""ANAL-009 Voice Drift service contract — CharacterVoiceDriftServiceProtocol.

Split into a focused file per RULE-04 (file-size limit). The voice-drift
service orchestrates the ADR-073 longitudinal drift pipeline over a novel's
chapters:

- ``VoiceProfileConsumer.assemble_for_checking()`` → stored profiles incl.
  ``voice_metrics`` (ADR-050 consumer contract — the longitudinal consumer
  is just another caller of the existing contract, no SSOT bypass).
- ``compute_per_chapter_metrics`` → deterministic per-chapter metrics per
  character (reused Foundation: ``DialogueParser`` + ``VoiceMetricsAnalyzer``,
  ADR-021).
- ``trend_against_profile`` → per-chapter match trend (signal i, reuses the
  WRITE-010 ``voice_metric_distances`` primitive — ADR-057 Risk #3).
- ``detect_adjacent_jumps`` → adjacent-chapter jump points (signal iii).
- ``CharacterVoiceDriftAgent`` → qualitative longitudinal classification,
  one LLM call **per character** (ADR-073 Decision 3/5).

The service is **read-only** (ADR-073 Decision 5 — it analyses; it does not
profile, does not write to KB, does not suggest rewrites).

Prompt resolution is Mode 1 (composer-driven, ADR-054): the service resolves
its system prompt via :class:`PromptComposer` and the governed ``voice_drift``
template (``LLMIntent.VOICE`` + ``context_mode="voice_drift"``), then passes
it to the :class:`CharacterVoiceDriftAgent` constructor. No inline f-string
feature prompt is assembled in the service (RULE-02 / RULE-02b). The
precomputed trend + jumps + stored descriptive profile + chapter metadata
flow as runtime data in the agent run prompt (user channel, RULE-02a
category 3).

RULE-13 (ADR-065): the service exposes both ``run()`` (non-streaming,
returns the aggregated response) and ``run_stream()`` (an
``AsyncIterator`` of SSE events). The router uses ``run_stream()`` for the
SSE endpoint; ``run()`` is provided for non-streaming callers + tests.

RULE-11 graceful degradation: a character without a stored profile, without
``voice_metrics``, or silent in every selected chapter yields a graceful
``no_profile`` event (never a crash). A project with no profiled characters
yields an empty result, not an error.

See:
    :mod:`narrare.analysis.voice_drift_service` — implementation.
    :mod:`narrare.analysis.schemas_voice_drift` — SSE event + response models.
    ADR-073 — Character Voice Drift (Decisions 2, 3, 5).
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    ADR-065 — RULE-13 two-method run/stream.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.analysis.schemas_voice_drift import (
        VoiceDriftEvent,
        VoiceDriftRequest,
        VoiceDriftResponse,
    )


@runtime_checkable
class CharacterVoiceDriftServiceProtocol(Protocol):
    """Protocol for the ANAL-009 character-voice-drift analysis service.

    Delegates to the Core-layer :class:`CharacterVoiceDriftAgent`
    (pydantic-ai) which classifies the longitudinal drift of ONE character
    per LLM call by interpreting (a) the stored *descriptive* voice profile,
    (b) a precomputed per-chapter match trend (signal i), and (c) detected
    adjacent-chapter jump points (signal iii) — all supplied as runtime
    context. The agent never recomputes metrics (ADR-021/ADR-073 Decision 2).

    The service is **read-only**: it never writes to the Knowledge Base
    (ADR-073 Decision 5). Profiles are read via
    :meth:`VoiceProfileConsumer.assemble_for_checking` (ADR-050 — no SSOT
    bypass).

    Prompt resolution is Mode 1 (composer-driven, ADR-054): the service
    resolves its system prompt via :class:`PromptComposer` and the governed
    ``voice_drift`` template (``LLMIntent.VOICE`` +
    ``context_mode="voice_drift"``), then passes it to the
    :class:`CharacterVoiceDriftAgent` constructor.

    RULE-11 graceful degradation: a character without a stored profile,
    without ``voice_metrics``, or silent in every selected chapter yields a
    graceful ``no_profile`` event (never a crash).
    """

    async def run(
        self,
        novel_id: UUID,
        user_id: UUID,
        request: VoiceDriftRequest,
    ) -> VoiceDriftResponse:
        """Analyse longitudinal voice drift for a novel's characters.

        Non-streaming aggregate of :meth:`run_stream`: collects every
        ``character_result`` and ``no_profile`` event into a single
        :class:`VoiceDriftResponse`.

        Args:
            novel_id: The novel whose chapters are analysed.
            user_id: The user requesting the analysis (access control).
            request: Optional filters (``character_id`` to scope to one
                character; ``chapter_ids`` to scope to specific chapters).

        Returns:
            The aggregated :class:`VoiceDriftResponse` with per-character
            drift results + the list of characters that could not be
            analysed (``no_profile``).

        Raises:
            narrare_core.shared.errors.NotFoundError: If the novel does not
                exist or is not accessible.
            narrare_core.shared.errors.ConfigurationError: If no
                ``PromptComposer`` is configured.
        """
        ...

    async def run_stream(
        self,
        novel_id: UUID,
        user_id: UUID,
        request: VoiceDriftRequest,
    ) -> AsyncIterator[VoiceDriftEvent]:
        """Analyse longitudinal voice drift, streaming SSE events.

        Runs the ADR-073 longitudinal pipeline and yields a ``"progress"``
        event, one ``"character_result"`` event per analysable character
        (profile + ``voice_metrics`` + speaks in ≥1 selected chapter), one
        ``"no_profile"`` event per character that cannot be analysed, then a
        terminal ``"done"`` event. The pipeline is read-only: no KB mutation
        occurs (profiles are read via
        :meth:`VoiceProfileConsumer.assemble_for_checking`).

        The precomputed trend + jumps + stored descriptive profile + chapter
        metadata flow as runtime data in the agent run prompt (user channel,
        RULE-02a category 3); the governed system prompt flows through
        :class:`PromptComposer` (Mode 1).

        Args:
            novel_id: The novel whose chapters are analysed.
            user_id: The user requesting the analysis (access control).
            request: Optional filters (``character_id`` to scope to one
                character; ``chapter_ids`` to scope to specific chapters).

        Yields:
            :class:`VoiceDriftEvent` instances: a ``"progress"`` event, one
            ``"character_result"`` or ``"no_profile"`` event per character,
            then a terminal ``"done"`` event (``is_final=True``).

        Raises:
            narrare_core.shared.errors.NotFoundError: If the novel does not
                exist or is not accessible.
            narrare_core.shared.errors.ConfigurationError: If no
                ``PromptComposer`` is configured.
        """
        ...
