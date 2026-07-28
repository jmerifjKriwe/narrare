"""ANAL-009 Phase 2B Author Voice Drift schemas — request/response + SSE events.

The author-voice analogue of Phase 1's :mod:`schemas_voice_drift`. Where Phase
1 carries PER-CHARACTER results (a list), author drift carries a SINGLE
narrator result (one author voice per novel) — so the wire schema is singular:
one ``"result"`` event OR one ``"no_profile"`` event per stream, never both,
never repeated.

Mirrors the established analysis SSE event pattern
(:class:`VoiceDriftEvent`, :class:`AuthorVoiceStreamEvent`): a type-
discriminated ``event`` field separates the result payload, the graceful
``no_profile`` skip, progress, the terminal ``"done"`` event, and in-band
``"error"`` events. The router serialises each event and appends a
``data: [DONE]`` sentinel.

The drift analysis is **read-only** (ADR-073 Decision 5): nothing here is
persisted. The per-narrator ``trend`` / ``jumps`` / ``overall_match_score`` /
``overall_band`` are display-only report artifacts; ``drift`` mirrors the
agent's :class:`VoiceDriftResult` verbatim (RULE-17 — field names match the
frontend TypeScript types; the OUTPUT shape is reused from Phase 1, ADR-073
D3 locked shape applied to ADR-074 author voice).

The Core value types (:class:`TrendPoint`, :class:`JumpPoint`,
:class:`VoiceDriftResult`) are reused directly as field types (no
duplication, RULE-22) — the sibling ``schemas_voice_drift`` imports them the
same way.

Split into a focused file per RULE-04 (file-size limit).

See:
    :mod:`narrare.analysis.author_voice_drift_service` — the service that
        yields these events.
    :mod:`narrare.analysis.schemas_voice_drift` — Phase 1 (per-character
        parallel; this file is its singular author-voice mirror).
    :mod:`narrare_core.analysis.voice_drift_scoring_types` —
        :class:`TrendPoint` / :class:`JumpPoint` (signal i + iii outputs).
    :mod:`narrare_core.agents.character_voice_drift_types` —
        :class:`VoiceDriftResult` (the reused agent output mirrored on
        ``drift``).
    ADR-074 — Author Voice Storage Contract.
    ADR-073 — Character Voice Drift (Decisions 2, 4, 5).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Runtime imports (not TYPE_CHECKING): these are Pydantic field types —
# Pydantic resolves field annotations at class-definition time via
# typing.get_type_hints(), so the symbols MUST be importable at runtime
# (mirrors schemas_voice_drift importing VoiceDriftResult). noqa: TC001.
from narrare_core.agents.character_voice_drift_types import (
    VoiceDriftResult,
)
from narrare_core.analysis.voice_drift_scoring_types import (  # noqa: TC001
    JumpPoint,
    TrendPoint,
)


class AuthorVoiceDriftRequest(BaseModel):
    """Request body for ``POST /analysis/author-voice-drift/{novel_id}``.

    The novel id is carried by the URL path parameter (mirrors
    :class:`AuthorVoiceRequest` / :class:`VoiceDriftRequest` — novel-scoped
    endpoints). The body carries the optional chapter filter (author voice is
    one narrator per novel, so there is no per-character filter):

    Attributes:
        chapter_ids: Specific chapter ids to analyse (UUID strings). ``None``
            or an empty list means "analyse every chapter in the novel" (the
            service resolves the full chapter list via the novel/chapter
            repositories). Mirrors ``AuthorVoiceRequest.chapter_ids``.
    """

    chapter_ids: list[str] | None = Field(
        default=None,
        description="Specific chapter IDs to analyse, or null/empty for all chapters.",
    )


class AuthorVoiceDriftNoProfile(BaseModel):
    """Graceful "narrator not analysable for drift" signal (RULE-11).

    Emitted when the stored author-voice profile cannot be drift-analysed.
    The ``reason`` disambiguates the graceful cases (mirrors Phase 1's
    :class:`VoiceDriftNoProfile`):

    Attributes:
        reason: Why the narrator was skipped — ``"no_stored_profile"`` (no
            :class:`AuthorVoiceProfile` stored yet), ``"no_profile_metrics"``
            (profile stored but missing the ``voice_metrics`` /
            ``author_metrics`` blocks the trend needs), or
            ``"no_chapters_with_prose"`` (profile + metrics exist but no
            selected chapter has prose to measure).
    """

    reason: str = ""


class AuthorVoiceDriftResult(BaseModel):
    """Longitudinal author-voice drift result (display-only — never persisted).

    Carries the deterministic per-chapter match trend (signal i, with author-
    metric deltas MERGED into each ``TrendPoint.per_metric_deltas``) + the
    adjacent-chapter jump points (signal iii) + the aggregate match score +
    the agent's qualitative :class:`VoiceDriftResult` classification. Singular
    (one narrator per novel — contrast Phase 1's per-character list).

    Attributes:
        novel_id: The novel analysed (str for JSON safety).
        trend: The per-chapter match trend (signal i) — one
            :class:`TrendPoint` per chapter with non-empty prose. The
            always-visible sparkline / heatmap row.
        jumps: The adjacent-chapter jump points (signal iii) — localise where
            drift began. Empty when no metric shifted beyond the threshold.
        overall_match_score: The mean of the per-chapter ``match_subscore``
            values in ``trend`` (a single [0, 100] summary of the whole
            trend). ``None`` when ``trend`` is empty.
        overall_band: The drift-facing severity label for
            ``overall_match_score`` (``"stable"`` / ``"minor"`` /
            ``"moderate"`` / ``"major"``), derived from ``band_for_score``
            (identical thresholds to WRITE-010 + Phase 1, ADR-073 D4).
            ``None`` when ``overall_match_score`` is ``None``.
        drift: The agent's qualitative longitudinal classification
            (:class:`VoiceDriftResult` — ``drift_type``, ``confidence``,
            ``longitudinal_reasons``, ``per_chapter_notes``,
            ``suggested_attention``). The OUTPUT shape is reused from Phase 1
            (ADR-073 D3 locked shape applied to the narrator trend).
    """

    novel_id: str = ""
    # Mirrors VoiceDriftCharacterResult.trend — ``= []`` keeps pyright strict
    # happy (Field(default_factory=list) would surface as list[Unknown] for a
    # custom-element list).
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


class AuthorVoiceDriftResponse(BaseModel):
    """Complete non-streaming author-voice-drift response for one novel.

    Author voice is one narrator per novel, so exactly one of ``result`` /
    ``no_profile`` is set (contrast Phase 1's per-character lists).

    Attributes:
        novel_id: The novel that was analysed.
        result: The narrator drift result (set when the narrator was
            analysable — profile + metrics + ≥1 chapter with prose).
        no_profile: The graceful skip detail (set when the narrator could not
            be analysed, RULE-11).
    """

    novel_id: str = ""
    result: AuthorVoiceDriftResult | None = None
    no_profile: AuthorVoiceDriftNoProfile | None = None


class AuthorVoiceDriftEvent(BaseModel):
    """One event in an author-voice-drift SSE stream.

    Follows the established analysis SSE event pattern (``event`` field
    discriminates progress, result, graceful no-profile skip, completion, and
    error), matching :class:`VoiceDriftEvent` / :class:`AuthorVoiceStreamEvent`.

    Event types:
        - ``"progress"`` — pipeline status update.
        - ``"result"`` — carries the narrator drift result in ``result``
          (single event: author voice is one narrator per novel).
        - ``"no_profile"`` — graceful skip when the narrator cannot be
          analysed (RULE-11); carries the skip detail in ``no_profile``.
        - ``"done"`` — terminal success event (``is_final=True``).
        - ``"error"`` — terminal error event (``is_final=True``, ``error``
          carries the message).

    Attributes:
        event: Event type — ``"progress"``, ``"result"``, ``"no_profile"``,
            ``"done"``, or ``"error"``.
        result: The narrator drift result (present on ``"result"`` events,
            ``None`` otherwise).
        no_profile: The graceful skip detail (present on ``"no_profile"``
            events, ``None`` otherwise).
        progress: Progress message (present on ``"progress"`` events).
        error: Error message (present on ``"error"`` events).
        is_final: ``True`` on the terminal event (``"done"`` or ``"error"``).
    """

    event: str = Field(
        default="progress",
        description="Event type: progress, result, no_profile, done, or error",
    )
    result: AuthorVoiceDriftResult | None = Field(
        default=None,
        description="Narrator drift result (present on 'result' events)",
    )
    no_profile: AuthorVoiceDriftNoProfile | None = Field(
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
