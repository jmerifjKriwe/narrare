"""WRITE-010 Voice Check schemas — per-character result + SSE events.

Mirrors the established analysis SSE event pattern
(``CharacterVoiceStreamEvent``, ``CoreferenceStreamEvent``): a
type-discriminated ``event`` field separates per-character result payloads,
progress, the terminal ``"done"`` event, and in-band ``"error"`` events.
The router serialises each event and appends a ``data: [DONE]`` sentinel.

Split into a focused file per RULE-04 (file-size limit). The checker is
read-only: nothing here is persisted. ``match_judgment`` /
``qualitative_sub_score`` / ``flagged_lines`` are display-only report
artifacts (ADR-057 Decision 5 — flag+score only).

See:
    :mod:`narrare.analysis.voice_check_service` — the service that yields
        these events.
    :mod:`narrare_core.agents.character_voice_checker_types` — the agent
        output types these response models mirror.
    :mod:`narrare_core.analysis.voice_check_scoring` —
        :class:`VoiceCheckScore` / :class:`VoiceCheckBand` mirrored here.
    ADR-057 — Voice-check checking-path contract (Decisions 2 and 5).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class VoiceCheckRequest(BaseModel):
    """Request body for ``POST /analysis/voice-check/{chapter_id}``.

    The initial WRITE-010 slice is chapter-scoped and has no request options:
    the path parameter identifies the chapter, and the checker evaluates all
    speaking characters in that chapter. A typed empty request keeps the API
    contract explicit without inventing unsupported filters.
    """


class FlaggedLineResponse(BaseModel):
    """A single dialogue line flagged as inconsistent with the stored profile.

    Mirrors :class:`narrare_core.agents.character_voice_checker_types.FlaggedLine`
    (display-only — never persisted; the checker is read-only).

    Attributes:
        quote: A verbatim excerpt of the character's dialogue that reads as
            inconsistent with the stored profile.
        reason: Concise, profile-grounded explanation of the divergence.
    """

    quote: str = ""
    reason: str = ""


class VoiceCheckResult(BaseModel):
    """Per-character voice-check result (display-only — never persisted).

    Carries the blended match score (from
    :class:`narrare_core.analysis.voice_check_scoring.VoiceCheckScorer`) plus
    the agent's qualitative judgment and flagged lines.

    Attributes:
        character_name: The character's canonical name (as attributed in the
            chapter dialogue).
        match_score: Overall blended match score [0, 100]. ``None`` when the
            character has no stored profile, or neither sub-score is
            available.
        band: Severity band of *match_score* (``"green"`` / ``"yellow"`` /
            ``"fair"`` / ``"red"``). ``None`` when *match_score* is ``None``.
        match_judgment: The agent's qualitative reading (``"consistent"`` /
            ``"mostly_consistent"`` / ``"notable_drift"`` / ``"off"``).
            ``None`` for characters not judged by the agent (no profile).
        qualitative_sub_score: The qualitative half of the match score
            [0, 100] from the agent, or ``None``.
        metric_delta_subscore: The deterministic metric-delta sub-score
            [0, 100], or ``None`` when no metric is comparable.
        flagged_lines: The specific dialogue lines flagged as inconsistent,
            each with a profile-grounded reason.
        has_profile: ``False`` iff the character has no stored voice profile
            — the graceful "no profile" signal (RULE-11). ``True`` otherwise.
        n_comparable_metrics: Number of metrics that contributed to the delta.
    """

    character_name: str = ""
    match_score: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Overall blended match score [0, 100], or None when unscorable.",
    )
    band: str | None = Field(
        default=None,
        description="Severity band: green | yellow | fair | red (None when unscorable).",
    )
    match_judgment: str | None = Field(
        default=None,
        description="Agent qualitative judgment (None for characters with no profile).",
    )
    qualitative_sub_score: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Agent qualitative sub-score [0, 100], or None.",
    )
    metric_delta_subscore: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Deterministic metric-delta sub-score [0, 100], or None.",
    )
    # Mirrors CharacterVoiceCheckerEntry.flagged_lines (list of a custom
    # BaseModel) — ``= []`` keeps pyright strict happy (Field(default_factory=list)
    # would surface as list[Unknown] for a custom-element list).
    flagged_lines: list[FlaggedLineResponse] = []
    has_profile: bool = Field(
        default=True,
        description="False iff the character has no stored voice profile (RULE-11).",
    )
    n_comparable_metrics: int = Field(
        default=0,
        ge=0,
        description="Number of metrics that contributed to the delta.",
    )


class VoiceCheckResponse(BaseModel):
    """Complete non-streaming voice-check response for one chapter.

    Attributes:
        chapter_id: The chapter that was checked.
        results: Per-character voice-check results for speaking characters.
    """

    chapter_id: str = ""
    results: list[VoiceCheckResult] = []


class VoiceCheckStreamEvent(BaseModel):
    """One event in a voice-check SSE stream.

    Follows the established analysis SSE event pattern (``event`` field
    discriminates progress, per-character result, completion, and error),
    matching :class:`CharacterVoiceStreamEvent` / :class:`CoreferenceStreamEvent`.

    Event types:
        - ``"progress"`` — pipeline status update.
        - ``"result"`` — carries one character's result in ``result``.
        - ``"done"`` — terminal success event (``is_final=True``).
        - ``"error"`` — terminal error event (``is_final=True``, ``error``
          carries the message).

    Attributes:
        event: Event type — ``"progress"``, ``"result"``, ``"done"``, or
            ``"error"``.
        result: One character's voice-check result (present on ``"result"``
            events, ``None`` otherwise).
        progress: Progress message (present on ``"progress"`` events).
        error: Error message (present on ``"error"`` events).
        is_final: ``True`` on the terminal event (``"done"`` or ``"error"``).
    """

    event: str = Field(
        default="result",
        description="Event type: progress, result, done, or error",
    )
    result: VoiceCheckResult | None = Field(
        default=None,
        description="Per-character voice-check result (present on 'result' events)",
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
