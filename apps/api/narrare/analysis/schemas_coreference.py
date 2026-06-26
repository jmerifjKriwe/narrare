"""ANAL-005 Coreference analysis schemas — response + SSE event models.

Mirrors the writing module's SSE event pattern (``StorySuggestStreamEvent``):
a type-discriminated ``event`` field separates the result payload, the
terminal ``"done"`` event, and in-band ``"error"`` events. The router
serialises each event and appends a ``data: [DONE]`` sentinel.

Split from schemas.py per RULE-04 (file-size limit).

See:
    :mod:`narrare.analysis.coreference_service` — the service that yields
        these events.
    :mod:`narrare_core.agents.coreference_types` — the core output types
        these response models mirror.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PronounResolutionResponse(BaseModel):
    """A single pronoun resolved to its referent.

    Mirrors :class:`narrare_core.agents.coreference_types.PronounResolution`.

    Attributes:
        pronoun: The pronoun token as it appears in the text
            (e.g. ``"he"``, ``"she"``, ``"their"``).
        position: Character offset of the pronoun within the analysed text.
        referent: The character name the pronoun refers to, or ``""`` when
            unresolved / ambiguous.
        confidence: Resolution confidence (0.0-1.0).
        is_ambiguous: ``True`` when multiple referents are plausible.
    """

    pronoun: str = ""
    position: int = 0
    referent: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_ambiguous: bool = False


class CharacterMentionResponse(BaseModel):
    """A character and the positions where it is mentioned.

    Mirrors :class:`narrare_core.agents.coreference_types.CharacterMention`.

    Attributes:
        character_name: The character's name (or most common reference form).
        mentions: Character offsets within the analysed text where the
            character is referred to by name or pronoun.
        is_pov: ``True`` when this character appears to be the POV
            character for the analysed passage.
    """

    character_name: str = ""
    mentions: list[int] = []
    is_pov: bool = False


class CoreferenceResponse(BaseModel):
    """Full coreference analysis for a chapter.

    Attributes:
        chapter_id: The chapter that was analysed.
        clarity_score: Overall referential clarity of the passage (0-100).
            Higher is clearer; ambiguous pronouns and unresolved
            references lower the score.
        summary: A brief free-text assessment of referential clarity
            (1-3 sentences).
        resolutions: Per-pronoun resolutions to their referents.
        character_mentions: Per-character mention tracking.
    """

    chapter_id: str = ""
    clarity_score: float = Field(default=0.0, ge=0.0, le=100.0)
    summary: str = ""
    resolutions: list[PronounResolutionResponse] = []
    character_mentions: list[CharacterMentionResponse] = []


class CoreferenceStreamEvent(BaseModel):
    """One event in a coreference SSE stream.

    Follows the writing module's SSE event pattern (``event`` field
    discriminates result data, completion, and error), matching
    :class:`StorySuggestStreamEvent`.

    Event types:
        - ``"result"`` — carries the full analysis in ``result``.
        - ``"done"`` — terminal success event (``is_final=True``).
        - ``"error"`` — terminal error event (``is_final=True``,
          ``error`` carries the message).

    Attributes:
        event: Event type — ``"result"``, ``"done"``, or ``"error"``.
        result: The full coreference analysis (present on ``"result"``
            events, ``None`` otherwise).
        error: Error message (present on ``"error"`` events, ``None``
            otherwise).
        is_final: ``True`` on the terminal event (``"done"`` or
            ``"error"``).
    """

    event: str = Field(
        default="result",
        description="Event type: result, done, or error",
    )
    result: CoreferenceResponse | None = Field(
        default=None,
        description="Coreference analysis (present on 'result' events)",
    )
    error: str | None = Field(
        default=None,
        description="Error message (present on 'error' events)",
    )
    is_final: bool = Field(
        default=False,
        description="True on the terminal event (done or error)",
    )
