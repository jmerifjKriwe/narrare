"""ANAL-009 Voice Drift schemas — request/response + SSE events.

Mirrors the established analysis SSE event pattern
(``VoiceCheckStreamEvent``, ``CharacterVoiceStreamEvent``): a
type-discriminated ``event`` field separates per-character result payloads,
the graceful ``no_profile`` skip, progress, the terminal ``"done"`` event,
and in-band ``"error"`` events. The router serialises each event and appends
a ``data: [DONE]`` sentinel.

Split into a focused file per RULE-04 (file-size limit). The drift analysis
is **read-only** (ADR-073 Decision 5): nothing here is persisted. The
per-character ``trend`` / ``jumps`` / ``overall_match_score`` /
``overall_band`` are display-only report artifacts; ``drift`` mirrors the
agent's :class:`VoiceDriftResult` verbatim (RULE-17 — field names match the
frontend TypeScript types).

The Core value types (:class:`TrendPoint`, :class:`JumpPoint`,
:class:`VoiceDriftResult`) are reused directly as field types (no
duplication, RULE-22) — the sibling ``schemas_character_voice`` imports
``VoiceAnalysis`` from core the same way.

See:
    :mod:`narrare.analysis.voice_drift_service` — the service that yields
        these events.
    :mod:`narrare_core.analysis.voice_drift_scoring_types` —
        :class:`TrendPoint` / :class:`JumpPoint` (signal i + iii outputs).
    :mod:`narrare_core.agents.character_voice_drift_types` —
        :class:`VoiceDriftResult` (the agent output mirrored on ``drift``).
    ADR-073 — Character Voice Drift (Decisions 2, 4, 5).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Runtime imports (not TYPE_CHECKING): these are Pydantic field types —
# Pydantic resolves field annotations at class-definition time via
# typing.get_type_hints(), so the symbols MUST be importable at runtime
# (mirrors schemas_character_voice importing VoiceAnalysis). noqa: TC001.
from narrare_core.agents.character_voice_drift_types import (
    VoiceDriftResult,
)
from narrare_core.analysis.voice_drift_scoring_types import (  # noqa: TC001
    JumpPoint,
    TrendPoint,
)


class VoiceDriftRequest(BaseModel):
    """Request body for ``POST /analysis/voice-drift/{novel_id}``.

    The novel id is carried by the URL path parameter (mirrors
    ``CharacterVoiceRequest`` — novel-scoped endpoint). The body carries
    optional filters:

    Attributes:
        character_id: Scope the analysis to a single character by their
            stored profile ``character_id`` (the KB entity UUID string).
            ``None`` means "analyse every profiled character" (the default).
        chapter_ids: Specific chapter ids to analyse (UUID strings). ``None``
            or an empty list means "analyse every chapter in the novel"
            (the service resolves the full chapter list via the novel
            repository). Mirrors ``CharacterVoiceRequest.chapter_ids``.
    """

    character_id: str | None = Field(
        default=None,
        description="Scope to one character by profile.character_id, or null for all.",
    )
    chapter_ids: list[str] | None = Field(
        default=None,
        description="Specific chapter IDs to analyse, or null/empty for all chapters.",
    )


class VoiceDriftNoProfile(BaseModel):
    """Graceful "not analysable for drift" signal for one character (RULE-11).

    Emitted for a character that cannot be drift-analysed. The ``reason``
    disambiguates the three graceful cases (ADR-073 Decision 5):

    Attributes:
        character_id: The character's stored profile ``character_id`` (the KB
            entity UUID string), or ``""`` when the character has no stored
            profile at all (a speaker with no KB voice entry).
        character_name: The character's canonical name (as attributed in the
            chapter dialogue), or ``""`` when unknown.
        reason: Why the character was skipped — ``"no_stored_profile"``
            (speaks but has no KB voice profile), ``"no_voice_metrics"``
            (has a profile but no stored ``voice_metrics``), or
            ``"no_dialogue_in_selected_chapters"`` (has a profile +
            ``voice_metrics`` but does not speak in any selected chapter).
    """

    character_id: str = ""
    character_name: str = ""
    reason: str = ""


class VoiceDriftCharacterResult(BaseModel):
    """Per-character longitudinal drift result (display-only — never persisted).

    Carries the deterministic per-chapter match trend (signal i) + the
    adjacent-chapter jump points (signal iii) + the aggregate match score +
    the agent's qualitative :class:`VoiceDriftResult` classification.

    Attributes:
        character_id: The character's stored profile ``character_id`` (the KB
            entity UUID string).
        character_name: The character's canonical name (as attributed in the
            chapter dialogue).
        trend: The per-chapter match trend (signal i) — one
            :class:`TrendPoint` per chapter where the character speaks. The
            always-visible sparkline / heatmap row.
        jumps: The adjacent-chapter jump points (signal iii) — localise where
            drift began. Empty when no metric shifted beyond the threshold.
        overall_match_score: The mean of the per-chapter ``match_subscore``
            values in ``trend`` (a single [0, 100] summary of the whole
            trend). ``None`` when ``trend`` is empty.
        overall_band: The drift-facing severity label for
            ``overall_match_score`` (``"stable"`` / ``"minor"`` /
            ``"moderate"`` / ``"major"``), derived from ``band_for_score``
            (identical thresholds to WRITE-010, ADR-073 D4). ``None`` when
            ``overall_match_score`` is ``None``.
        drift: The agent's qualitative longitudinal classification
            (:class:`VoiceDriftResult` — ``drift_type``, ``confidence``,
            ``longitudinal_reasons``, ``per_chapter_notes``,
            ``suggested_attention``).
    """

    character_id: str = ""
    character_name: str = ""
    # Mirrors CharacterVoiceCheckerEntry.flagged_lines — ``= []`` keeps pyright
    # strict happy (Field(default_factory=list) would surface as list[Unknown]
    # for a custom-element list).
    trend: list[TrendPoint] = []
    jumps: list[JumpPoint] = []
    overall_match_score: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Mean per-chapter match sub-score [0, 100], or None when trend is empty.",
    )
    overall_band: str | None = Field(
        default=None,
        description="Drift severity label: stable | minor | moderate | major.",
    )
    drift: VoiceDriftResult = Field(default_factory=VoiceDriftResult)


class VoiceDriftResponse(BaseModel):
    """Complete non-streaming voice-drift response for one novel.

    Attributes:
        novel_id: The novel that was analysed.
        results: Per-character drift results for analysable characters
            (profile + ``voice_metrics`` + speaks in ≥1 selected chapter).
        no_profile: Characters that could not be analysed (graceful
            ``no_profile`` entries with a reason).
    """

    novel_id: str = ""
    results: list[VoiceDriftCharacterResult] = []
    no_profile: list[VoiceDriftNoProfile] = []


class VoiceDriftEvent(BaseModel):
    """One event in a voice-drift SSE stream.

    Follows the established analysis SSE event pattern (``event`` field
    discriminates progress, per-character result, graceful no-profile skip,
    completion, and error), matching :class:`VoiceCheckStreamEvent` /
    :class:`CharacterVoiceStreamEvent`.

    Event types:
        - ``"progress"`` — pipeline status update.
        - ``"character_result"`` — carries one character's drift result in
          ``result``.
        - ``"no_profile"`` — graceful skip for a character that cannot be
          analysed (RULE-11); carries the skip detail in ``no_profile``.
        - ``"done"`` — terminal success event (``is_final=True``).
        - ``"error"`` — terminal error event (``is_final=True``, ``error``
          carries the message).

    Attributes:
        event: Event type — ``"progress"``, ``"character_result"``,
            ``"no_profile"``, ``"done"``, or ``"error"``.
        result: One character's drift result (present on
            ``"character_result"`` events, ``None`` otherwise).
        no_profile: The graceful skip detail (present on ``"no_profile"``
            events, ``None`` otherwise).
        progress: Progress message (present on ``"progress"`` events).
        error: Error message (present on ``"error"`` events).
        is_final: ``True`` on the terminal event (``"done"`` or ``"error"``).
    """

    event: str = Field(
        default="progress",
        description="Event type: progress, character_result, no_profile, done, or error",
    )
    result: VoiceDriftCharacterResult | None = Field(
        default=None,
        description="Per-character drift result (present on 'character_result' events)",
    )
    no_profile: VoiceDriftNoProfile | None = Field(
        default=None,
        description="Graceful skip detail (present on 'no_profile' events)",
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
