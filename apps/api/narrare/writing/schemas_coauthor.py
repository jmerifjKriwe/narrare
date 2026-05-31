"""Writing co-author schemas — co-author revision request/response models.

Follows the same pattern as ``schemas_rewrite.py`` (RULE-04: split from
schemas.py for file size limits).  Implements the data models from ADR-023.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class CoAuthorFocus(StrEnum):
    """Supported co-author improvement focus areas.

    Each focus area targets a specific aspect of the writing:
    * ``WORD_CHOICE`` — Stronger verbs, more precise nouns, remove redundancies
    * ``SENTENCE`` — Vary structure, fix phrasing, improve rhythm
    * ``DIALOGUE`` — More natural speech, better character voice, subtext
    * ``DESCRIPTION`` — Sensory details, show don't tell, vivid imagery
    """

    WORD_CHOICE = "word_choice"
    SENTENCE = "sentence"
    DIALOGUE = "dialogue"
    DESCRIPTION = "description"


class CoAuthorRequest(BaseModel):
    """Request for co-author revision of a text selection.

    The frontend sends the selected passage with optional surrounding
    context and one or more improvement focus areas.  The backend streams
    the revised text through the pipeline, then computes a server-side
    diff and returns change metadata in the final SSE event.
    """

    selection_text: str = Field(
        ...,
        min_length=50,
        max_length=10000,  # Erhöht: Netz gegen absurd große Payloads
        description="Passage to improve (50-10000 characters)",
    )
    context_before: str | None = Field(
        default=None,
        max_length=500,
        description="Text immediately before the selection (up to 500 chars)",
    )
    context_after: str | None = Field(
        default=None,
        max_length=500,
        description="Text immediately after the selection (up to 500 chars)",
    )
    focus: list[CoAuthorFocus] = Field(
        ...,
        min_length=1,
        description="Improvement focus areas (at least one required)",
    )
    tone: str = Field(
        default="balanced",
        min_length=1,
        max_length=100,
        description="Tone preference for the revision",
    )
    language: str = Field(
        default="en",
        min_length=2,
        max_length=5,
        description="Output language code",
    )

    @model_validator(mode="after")
    def validate_focus_requirements(self) -> CoAuthorRequest:
        """Ensure focus list is non-empty (defensive — Field.min_length handles this).

        Additionally validates that each focus value is a valid
        :class:`CoAuthorFocus` member.
        """
        if not self.focus:
            raise ValueError("At least one focus area is required")
        for f in self.focus:
            if f not in CoAuthorFocus:
                msg = f"Invalid focus area: {f!r}. Valid: {[e.value for e in CoAuthorFocus]}"
                raise ValueError(msg)
        return self


class ChangeDetail(BaseModel):
    """A single change within a co-author revision.

    Represents one specific modification that the AI made to the original
    text, with enough information for the frontend to display a diff entry
    with accept/reject controls.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique change identifier")
    change_type: str = Field(
        ..., description="Type of change (word_choice, sentence, dialogue, description)"
    )
    original_text: str = Field(..., description="Original text before the change")
    revised_text: str = Field(..., description="Revised text after the change")
    index: int = Field(..., description="Position in the change sequence (0-based)")


class CoAuthorRevision(BaseModel):
    """Complete co-author revision result with change details.

    Returned to the frontend after streaming completes, containing the
    full revised text and a list of individual changes that can be
    accepted or rejected.
    """

    original: str = Field(..., description="The original selected text")
    revised: str = Field(..., description="The full revised text")
    changes: list[ChangeDetail] = Field(
        default_factory=lambda: [], description="Individual changes with diff details"
    )
    reasoning: str = Field(default="", description="AI reasoning for the suggested changes")


class TextChange(BaseModel):
    """Ein Textsegment-Change für zustandsloses Apply.

    Frontend sendet original+revised Textsegmente (keine Change-IDs),
    damit der Backend-Zustand irrelevant ist — nur original + accepted
    werden zur Rekonstruktion gebraucht.
    """

    original_text: str = Field(..., description="Original text segment")
    revised_text: str = Field(..., description="Revised text segment")


class ApplyChangesRequest(BaseModel):
    """Apply selected changes to chapter content.

    Frontend sendet die Textsegmente direkt (keine Change-IDs),
    damit der Backend-Zustand irrelevant ist — nur original + accepted
    werden zur Rekonstruktion gebraucht.
    """

    request_id: uuid.UUID = Field(..., description="Generation request ID for feedback tracking")
    original: str = Field(..., description="Full original selection text")
    accepted: list[TextChange] = Field(..., description="Accepted changes to apply")
    rejected: list[TextChange] = Field(default_factory=lambda: [], description="Rejected changes")


class ChangeFeedback(BaseModel):
    """Feedback for a single change."""

    change_id: str = Field(..., description="Client-side change identifier")
    action: str = Field(..., description="'accepted' or 'rejected'")
    focus: str = Field(default="word_choice", description="Change type / focus area")
    original: str = Field(..., description="Original text segment")
    revised: str = Field(..., description="Revised text segment (or empty for reject)")


class CoAuthorFeedbackRequest(BaseModel):
    """Batch feedback for co-author changes (LEARN-001)."""

    request_id: uuid.UUID = Field(..., description="Generation request ID")
    feedback: list[ChangeFeedback] = Field(..., description="Per-change feedback items")
