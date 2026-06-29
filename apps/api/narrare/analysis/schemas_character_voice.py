"""ANAL-008 Character Voice analysis schemas — request/response + SSE events.

Mirrors the established analysis SSE event pattern (``CoreferenceStreamEvent``,
``StorySuggestStreamEvent``): a type-discriminated ``event`` field separates
per-character result payloads, progress, the terminal ``"done"`` event, and
in-band ``"error"`` events. The router serialises each event and appends a
``data: [DONE]`` sentinel.

Split into a focused file per RULE-04 (file-size limit). The persisted
``VoiceAnalysis`` (Layer-0 storage type) is mirrored read-only on the
response; the per-run ``distinctiveness_notes`` comparison artifact is
surfaced display-only and is NOT persisted (ADR-055 Decision 1 persistence
scope).

See:
    :mod:`narrare.analysis.character_voice_service` — the service that yields
        these events.
    :mod:`narrare_core.kb.schemas.character` — the Layer-0 ``VoiceAnalysis``
        / ``VoiceMetrics`` storage types these response models mirror.
    ADR-055 — Character voice storage contract (Decision 1 persistence scope).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from narrare_core.kb.schemas.character import (
    VoiceAnalysis,  # noqa: TC001 — Pydantic field type needed at runtime
)


class CharacterVoiceRequest(BaseModel):
    """Request body for ``POST /analysis/character-voice/{novel_id}``.

    Attributes:
        chapter_ids: Specific chapters to analyse. ``None`` or an empty list
            means "analyse every chapter in the novel" (the service resolves
            the full chapter list via the novel repository).
    """

    chapter_ids: list[str] | None = Field(
        default=None,
        description="Specific chapter IDs to analyse, or null/empty for all chapters.",
    )


class CharacterVoiceResult(BaseModel):
    """Per-character voice profiling result.

    Carries the persisted :class:`VoiceAnalysis` (the descriptive + metric
    summary written to ``metadata["speech"]["voice_analysis"]``) plus the
    display-only ``distinctiveness_notes`` — a per-run comparison artifact
    that is surfaced to the UI panel as a review aid but is NOT persisted on
    the character profile (ADR-055 Decision 1).

    Attributes:
        character_name: The character's canonical name (matched to a KB
            character entry when one exists).
        voice_analysis: The persisted voice-analysis summary (descriptive +
            metric). ``None`` when no KB entry was found to persist onto
            (the result is still surfaced to the UI).
        distinctiveness_notes: Relative, per-run comparison vs the *other*
            characters analysed in the same invocation. Display-only.
        kb_entry_id: The KB entry id the analysis was persisted onto, or
            ``None`` when no matching character KB entry exists.
    """

    character_name: str = ""
    voice_analysis: VoiceAnalysis | None = None
    distinctiveness_notes: str | None = None
    kb_entry_id: str | None = None


class CharacterVoiceStreamEvent(BaseModel):
    """One event in a character-voice SSE stream.

    Follows the established analysis SSE event pattern (``event`` field
    discriminates progress, per-character result, completion, and error),
    matching :class:`CoreferenceStreamEvent`.

    Event types:
        - ``"progress"`` — pipeline status update (e.g. "found N characters").
        - ``"result"`` — carries one character's result in ``result``.
        - ``"done"`` — terminal success event (``is_final=True``).
        - ``"error"`` — terminal error event (``is_final=True``, ``error``
          carries the message).

    Attributes:
        event: Event type — ``"progress"``, ``"result"``, ``"done"``, or
            ``"error"``.
        result: One character's voice result (present on ``"result"``
            events, ``None`` otherwise).
        progress: Progress message (present on ``"progress"`` events,
            ``None`` otherwise).
        error: Error message (present on ``"error"`` events, ``None``
            otherwise).
        is_final: ``True`` on the terminal event (``"done"`` or ``"error"``).
    """

    event: str = Field(
        default="result",
        description="Event type: progress, result, done, or error",
    )
    result: CharacterVoiceResult | None = Field(
        default=None,
        description="Per-character voice result (present on 'result' events)",
    )
    progress: str | None = Field(
        default=None,
        description="Progress message (present on 'progress' events)",
    )
    error: str | None = Field(
        default=None,
        description="Error message (present on 'error' events)",
    )
    is_final: bool = Field(
        default=False,
        description="True on the terminal event (done or error)",
    )
