"""Draft accept/reject lifecycle — split from the writing facade (RULE-04).

Owns the terminal accept/reject seam of a generation request: ownership
validation, the M06 empty-draft accept guard, and feedback recording.
Stateless functions over the repository + feedback collector; the
:class:`~narrare.writing.service.WritingService` facade delegates here
(established sibling-module pattern, cf. ``_stream_service.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.writing._helpers import get_validated_request, record_feedback
from narrare.writing.schemas import AcceptResponse, RejectResponse
from narrare_core.shared.errors import ValidationError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.writing.repository import GenerationRepository
    from narrare_core.memory.protocols import FeedbackCollector

logger = structlog.get_logger(__name__)


async def accept_draft_request(
    repo: GenerationRepository,
    feedback: FeedbackCollector | None,
    request_id: UUID,
    user_id: str,
    modified_text: str | None = None,
) -> AcceptResponse:
    """Accept a generated draft (optionally with user edits).

    Args:
        repo: Generation request repository (ownership + row access).
        feedback: Optional feedback collector (None → no feedback event).
        request_id: Generation request to accept.
        user_id: Owning user (validated in ``get_validated_request``).
        modified_text: Optional hand-edited draft text from the request body.

    Returns:
        Populated ``AcceptResponse`` for the accepted request.

    Raises:
        ValidationError: code ``EMPTY_DRAFT`` when the request row never
            received generated text (``word_count == 0``) and no non-blank
            ``modified_text`` is supplied (audit M06: an accept must not
            be recorded for a draft that does not exist).
    """
    request_model = await get_validated_request(repo, request_id, user_id)
    if request_model.word_count == 0 and not (modified_text or "").strip():
        raise ValidationError(
            "Cannot accept a draft with no generated text",
            code="EMPTY_DRAFT",
        )
    await record_feedback(feedback, request_model, "accept", modified_text=modified_text)
    logger.info("draft_accepted", request_id=str(request_id))
    return AcceptResponse(
        request_id=request_id,
        chapter_id=request_model.chapter_id,
        word_count=request_model.word_count,
    )


async def reject_draft_request(
    repo: GenerationRepository,
    feedback: FeedbackCollector | None,
    request_id: UUID,
    user_id: str,
) -> RejectResponse:
    """Reject a generated draft (same ownership validation as accept)."""
    request_model = await get_validated_request(repo, request_id, user_id)
    await record_feedback(feedback, request_model, "reject")
    logger.info("draft_rejected", request_id=str(request_id))
    return RejectResponse(request_id=request_id)
