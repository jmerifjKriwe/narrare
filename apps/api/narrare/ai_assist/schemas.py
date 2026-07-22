"""Pydantic schemas for the dialogue-coach REST API (ADR-069 D17).

- DialogueCoachRequest: body for POST /ai-assist/dialogue-coach/{chapter_id}.
- DialogueCoachResponse: non-streaming response (run()).
- DialogueCoachStreamEvent: one event in the SSE stream (stream()).

Mirrors the established analysis SSE event pattern (event type field
discriminates progress / result / done / error), matching
CoreferenceStreamEvent and CharacterVoiceStreamEvent.

See:
    ADR-069 Decision 8 (single endpoint + mode param),
    ADR-069 Decision 9 (before/after blocks, not char-level diff),
    CONSTRAINTS.md RULE-03, RULE-04, RULE-13.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DialogueCoachMode = Literal["analyze", "improve"]


class DialogueCoachRequest(BaseModel):
    """Body for POST /ai-assist/dialogue-coach/{chapter_id}.

    Attributes:
        selection_text: The user-selected dialogue passage from the editor.
            Must be non-empty (the coach cannot analyse nothing — RULE-11
            graceful degradation returns a "nothing to analyse" result
            rather than crashing, but the request itself rejects empty).
        mode: "analyze" (issues only) or "improve" (issues + alternatives).
    """

    model_config = ConfigDict(extra="forbid")

    selection_text: str = Field(min_length=1)
    mode: DialogueCoachMode = "analyze"


class DialogueAlternativeResponse(BaseModel):
    """One proposed rewrite (mirrors Core DialogueAlternative)."""

    model_config = ConfigDict(frozen=True)

    rewrite: str
    explanation: str = ""


class DialogueIssueResponse(BaseModel):
    """One diagnosed issue (mirrors Core DialogueIssue)."""

    model_config = ConfigDict(frozen=True)

    issue_type: str
    speaker: str = ""
    original_quote: str
    diagnosis: str
    severity: str = "low"
    alternatives: list[DialogueAlternativeResponse] | None = None


class DialogueCoachResponse(BaseModel):
    """Non-streaming response from DialogueCoachService.run()."""

    model_config = ConfigDict(frozen=True)

    chapter_id: str
    mode: DialogueCoachMode
    issues: list[DialogueIssueResponse]
    adaptive_summary: str = ""


class DialogueCoachStreamEvent(BaseModel):
    """One event in the dialogue-coach SSE stream.

    Event types match the established analysis SSE pattern
    (CoreferenceStreamEvent, CharacterVoiceStreamEvent):
    - "progress" — status update.
    - "result" — carries the full DialogueCoachResponse.
    - "done" — terminal success (is_final=True).
    - "error" — terminal error (is_final=True).
    """

    event: str = Field(
        default="result",
        description="Event type: progress, result, done, or error",
    )
    result: DialogueCoachResponse | None = Field(default=None)
    progress: str | None = Field(default=None)
    error: str | None = Field(default=None)
    is_final: bool = Field(default=False)
