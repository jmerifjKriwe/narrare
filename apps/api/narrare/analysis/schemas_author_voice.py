"""ANAL-007 Author Voice analysis schemas — request/response + SSE events.

Mirrors the established analysis SSE event pattern
(:class:`CharacterVoiceStreamEvent`, :class:`CoreferenceStreamEvent`): a
type-discriminated ``event`` field separates the result payload, progress,
the terminal ``"done"`` event, and in-band ``"error"`` events. The router
serialises each event and appends a ``data: [DONE]`` sentinel.

The persisted :class:`AuthorVoiceProfile` (Core type — descriptive + metric
groups, ADR-074) is mirrored read-only on the response. The
descriptive/metric boundary (ADR-055/057/074) is preserved at the consumer
contract (the Core
:func:`narrare_core.profiles.author_voice.render_author_voice_for_generation`
renderer), NOT at the wire schema: the SSE ``result`` carries the FULL
profile (descriptive + metrics) so the panel can display the composition
metrics (Phase 2B drift comparison aid). The GENERATION consumer (Task 5)
renders descriptive-only via the Core renderer.

See:
    :mod:`narrare.analysis.author_voice_service` — the service that yields
        these events.
    :mod:`narrare_core.profiles.author_voice` — the Core ``AuthorVoiceProfile``
        type these response models mirror (and the descriptive-only renderer
        that enforces the boundary for generation).
    ADR-074 — Author Voice Storage Contract (data shape).
    ADR-055 — Character voice contract (the structural parallel).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Runtime import (not TYPE_CHECKING): AuthorVoiceProfile is a Pydantic field
# type on AuthorVoiceResult and must resolve at class-definition time. noqa:
# TC001 — pyright/pylno noise on a Pydantic field type.
from narrare_core.profiles.author_voice import AuthorVoiceProfile  # noqa: TC001


class AuthorVoiceRequest(BaseModel):
    """Request body for ``POST /analysis/author-voice/{novel_id}``.

    Attributes:
        chapter_ids: Specific chapters to analyse. ``None`` or an empty list
            means "analyse every chapter in the novel" (the service resolves
            the full chapter list via the chapter repository). 3+ chapters
            recommended for a meaningful profile (the service surfaces a soft
            warning below the threshold but does not block).
    """

    chapter_ids: list[str] | None = Field(
        default=None,
        description="Specific chapter IDs to analyse, or null/empty for all chapters.",
    )


class AuthorVoiceResult(BaseModel):
    """Author-voice profiling result (one profile per novel).

    Carries the persisted :class:`AuthorVoiceProfile` (descriptive + metric
    groups, ADR-074). The wire schema deliberately carries BOTH groups so the
    panel can display the composition metrics; the GENERATION consumer (Task
    5) renders descriptive-only via the Core
    :func:`render_author_voice_for_generation` (the descriptive/metric
    boundary is enforced at the consumer contract, not the wire schema).

    Attributes:
        novel_id: The novel the profile belongs to (str for JSON safety).
        profile: The assembled + persisted author-voice profile (descriptive
            + metric groups). ``None`` only on the empty-chapters graceful
            path (no profile built).
    """

    novel_id: str = ""
    profile: AuthorVoiceProfile | None = None


class AuthorVoiceStreamEvent(BaseModel):
    """One event in an author-voice SSE stream.

    Follows the established analysis SSE event pattern (``event`` field
    discriminates progress, result, completion, and error), matching
    :class:`CharacterVoiceStreamEvent`.

    Event types:
        - ``"progress"`` — pipeline status update (e.g. "analysing N
          chapters").
        - ``"result"`` — carries the assembled profile in ``result``
          (single event: author voice is one profile per novel, not
          per-character).
        - ``"done"`` — terminal success event (``is_final=True``).
        - ``"error"`` — terminal error event (``is_final=True``, ``error``
          carries the message).

    Attributes:
        event: Event type — ``"progress"``, ``"result"``, ``"done"``, or
            ``"error"``.
        result: The author-voice result (present on ``"result"`` events,
            ``None`` otherwise).
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
    result: AuthorVoiceResult | None = Field(
        default=None,
        description="Author-voice result (present on 'result' events)",
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
