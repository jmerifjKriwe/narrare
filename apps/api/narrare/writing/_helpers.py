"""Shared helpers for the writing module — extracted per RULE-04.

Contains validation and feedback helpers used across writing sub-services.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare.writing.models import GenerationRequest
    from narrare.writing.schemas import GenerateRequest
    from narrare.writing.schemas_coauthor import ChangeFeedback
    from narrare_core.memory.protocols import FeedbackCollector

from narrare_core.memory.models import FeedbackAction, FeedbackEvent
from narrare_core.shared.errors import ValidationError


async def record_batch_feedback(
    feedback_service: FeedbackCollector | None,
    request_model: GenerationRequest,
    feedback: list[ChangeFeedback],
) -> None:
    """Record batch per-change feedback for co-author (LEARN-001).

    Args:
        feedback_service: Optional feedback collector (no-op if None).
        request_model: The generation request these changes belong to.
        feedback: Per-change feedback items with action and metadata.
    """
    if feedback_service is None:
        return

    for fb in feedback:
        event = FeedbackEvent(
            user_id=request_model.user_id,
            project_id=request_model.novel_id,
            suggestion_id=request_model.id,
            action=FeedbackAction(fb.action),
            intent="write",
            suggestion_text=fb.original,
            context={
                "change_id": fb.change_id,
                "focus": fb.focus,
                "revised": fb.revised,
            },
        )
        await feedback_service.record(event)


def validate_generation_input(request: GenerateRequest) -> None:
    """Ensure at least one of prompt, outline, or auto_continue is set.

    Args:
        request: The generation request to validate.

    Raises:
        ValidationError: If no input source is provided.
    """
    if not request.prompt and not request.outline and not request.auto_continue:
        raise ValidationError(
            "At least one of prompt, outline, or auto_continue must be provided",
            code="MISSING_INPUT",
        )


async def record_feedback(
    feedback_service: FeedbackCollector | None,
    request_model: GenerationRequest,
    action: str,
    *,
    modified_text: str | None = None,
) -> None:
    """Record feedback via FeedbackCollector if available.

    Args:
        feedback_service: Optional feedback collector service.
        request_model: The generation request that generated the feedback.
        action: Feedback action ("accept" or "reject").
        modified_text: Optional user-modified text override.
    """
    if feedback_service is None:
        return
    from narrare_core.memory.models import FeedbackAction, FeedbackEvent

    event = FeedbackEvent(
        user_id=request_model.user_id,
        project_id=request_model.novel_id,
        suggestion_id=request_model.id,
        action=FeedbackAction(action),
        intent="write",
        suggestion_text=modified_text or "",
    )
    await feedback_service.record(event)
