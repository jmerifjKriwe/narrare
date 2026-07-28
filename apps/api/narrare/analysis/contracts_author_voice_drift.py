"""ANAL-009 Phase 2B Author Voice Drift service contract (ADR-074).

The author-voice analogue of Phase 1's
:class:`~narrare.analysis.contracts_voice_drift.CharacterVoiceDriftServiceProtocol`.
Where Phase 1 compares per-chapter :class:`VoiceMetrics` for ONE CHARACTER
against the stored :class:`CharacterVoiceProfile` (looping over many
characters), this service compares per-chapter **narrator** metrics — BOTH
:class:`VoiceMetrics` AND :class:`AuthorMetrics` — against the single stored
:class:`~narrare_core.profiles.author_voice.AuthorVoiceProfile` (one narrator
per novel). The deterministic trend (signal i) + jumps (signal iii) are
computed by :mod:`narrare_core.analysis.author_voice_drift_scoring`
(ADR-021); the governed :class:`AuthorVoiceDriftAgent` interprets them
qualitatively — **one LLM call per run** (ADR-074 / ADR-073 Decision 5).

The service is **read-only** (ADR-073 Decision 5 — it analyses; it does not
profile, does not write to ``ProjectSettings``, does not suggest rewrites).
The stored profile is read via
:class:`~narrare.analysis.author_voice_repository.AuthorVoiceRepository`
(ADR-074 no-direct-column binding — no SSOT bypass).

Prompt resolution is Mode 1 (composer-driven, ADR-054): the service resolves
its system prompt via :class:`PromptComposer` and the governed
``author_voice_drift`` template (``LLMIntent.VOICE`` +
``context_mode="author_voice_drift"``), then passes it to the
:class:`AuthorVoiceDriftAgent` constructor. No inline f-string feature prompt
is assembled in the service (RULE-02 / RULE-02b). The precomputed trend +
jumps + stored descriptive profile + chapter metadata flow as runtime data in
the agent run prompt (user channel, RULE-02a category 3).

RULE-13 (ADR-065): the service exposes both ``run()`` (non-streaming, returns
the aggregated response) and ``run_stream()`` (an ``AsyncIterator`` of SSE
events). The router uses ``run_stream()`` for the SSE endpoint; ``run()`` is
provided for non-streaming callers + tests.

RULE-11 graceful degradation: no stored profile, a profile missing the metric
blocks needed for the trend, or no chapter with prose yields a graceful
``no_profile`` event (never a crash). A novel with no chapters yields an
empty ``"progress"`` + ``"done"`` (no LLM call).

See:
    :mod:`narrare.analysis.author_voice_drift_service` — implementation.
    :mod:`narrare.analysis.schemas_author_voice_drift` — SSE event + response
        models.
    ADR-074 — Author Voice Storage Contract.
    ADR-073 — Character Voice Drift (the Phase 1 parallel mirrored here).
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    ADR-065 — RULE-13 two-method run/stream.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.analysis.schemas_author_voice_drift import (
        AuthorVoiceDriftEvent,
        AuthorVoiceDriftRequest,
        AuthorVoiceDriftResponse,
    )


@runtime_checkable
class AuthorVoiceDriftServiceProtocol(Protocol):
    """Protocol for the ANAL-009 Phase 2B author-voice-drift analysis service.

    Delegates to the Core-layer
    :class:`~narrare_core.agents.author_voice_drift_agent.AuthorVoiceDriftAgent`
    (pydantic-ai) which classifies the longitudinal drift of the NARRATOR's
    voice (one LLM call) by interpreting (a) the stored *descriptive*
    author-voice profile, (b) a precomputed per-chapter match trend (signal i)
    whose deltas MERGE voice-generic + author-specific metrics, and (c)
    detected adjacent-chapter jump points (signal iii) — all supplied as
    runtime context. The agent never recomputes metrics (ADR-021 / ADR-073
    Decision 2).

    The service is **read-only**: it never writes to
    ``ProjectSettings.author_voice`` (ADR-073 Decision 5). The stored profile
    is read via :class:`AuthorVoiceRepository` (ADR-074 — no direct column
    access).

    Prompt resolution is Mode 1 (composer-driven, ADR-054): the service
    resolves its system prompt via :class:`PromptComposer` and the governed
    ``author_voice_drift`` template (``LLMIntent.VOICE`` +
    ``context_mode="author_voice_drift"``), then passes it to the
    :class:`AuthorVoiceDriftAgent` constructor.

    RULE-11 graceful degradation: no stored profile, a profile missing the
    metric blocks, or no chapter with prose yields a graceful ``no_profile``
    event (never a crash).
    """

    async def run(
        self,
        novel_id: UUID,
        user_id: UUID,
        request: AuthorVoiceDriftRequest,
    ) -> AuthorVoiceDriftResponse:
        """Analyse longitudinal author-voice drift for a novel's narrator.

        Non-streaming aggregate of :meth:`run_stream`: collects the single
        ``"result"`` event (or the graceful ``"no_profile"`` event) into an
        :class:`AuthorVoiceDriftResponse`.

        Args:
            novel_id: The novel whose chapters are analysed.
            user_id: The user requesting the analysis (access control).
            request: Optional filter (``chapter_ids`` to scope to specific
                chapters; ``None`` / empty means all chapters).

        Returns:
            The aggregated :class:`AuthorVoiceDriftResponse` carrying either
            the narrator drift ``result`` or a ``no_profile`` skip detail
            (mutually exclusive — author voice is one narrator per novel).

        Raises:
            narrare_core.shared.errors.NotFoundError: If the novel does not
                exist or is not accessible, or no model config is configured.
            narrare_core.shared.errors.ConfigurationError: If no
                ``PromptComposer`` is configured.
        """
        ...

    async def run_stream(
        self,
        novel_id: UUID,
        user_id: UUID,
        request: AuthorVoiceDriftRequest,
    ) -> AsyncIterator[AuthorVoiceDriftEvent]:
        """Analyse longitudinal author-voice drift, streaming SSE events.

        Runs the ADR-074 author-drift pipeline and yields a ``"progress"``
        event, then EITHER one ``"result"`` event (carrying the narrator's
        trend + jumps + overall score/band + the agent classification) OR one
        ``"no_profile"`` event (when the narrator cannot be analysed — RULE-11
        graceful), then a terminal ``"done"`` event. The pipeline is
        read-only: no ``ProjectSettings`` mutation occurs.

        The precomputed trend + jumps + stored descriptive profile + chapter
        metadata flow as runtime data in the agent run prompt (user channel,
        RULE-02a category 3); the governed system prompt flows through
        :class:`PromptComposer` (Mode 1).

        Args:
            novel_id: The novel whose chapters are analysed.
            user_id: The user requesting the analysis (access control).
            request: Optional filter (``chapter_ids`` to scope to specific
                chapters).

        Yields:
            :class:`AuthorVoiceDriftEvent` instances: a ``"progress"`` event,
            then exactly one ``"result"`` or ``"no_profile"`` event, then a
            terminal ``"done"`` event (``is_final=True``).

        Raises:
            narrare_core.shared.errors.NotFoundError: If the novel does not
                exist or is not accessible, or no model config is configured.
            narrare_core.shared.errors.ConfigurationError: If no
                ``PromptComposer`` is configured.
        """
        ...
