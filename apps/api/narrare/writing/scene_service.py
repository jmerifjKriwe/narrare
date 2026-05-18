"""Scene-by-scene generation sub-service.

Handles ``next_scene`` and ``accept_scene`` operations for the
scene-by-scene writing mode.  Extracted from ``service.py`` for
RULE-04 compliance (max 300 lines per file).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.writing.schemas import AcceptResponse, SceneNextResponse

if TYPE_CHECKING:
    from narrare.writing.models import GenerationRequest
    from narrare.writing.repository import GenerationRepository
    from narrare_core.memory.protocols import FeedbackCollector

logger = structlog.get_logger(__name__)


class SceneService:
    """Scene-by-scene generation logic.

    Dependencies are injected via constructor (DI pattern).
    """

    def __init__(
        self,
        repo: GenerationRepository,
        feedback_service: FeedbackCollector | None = None,
    ) -> None:
        self._repo = repo
        self._feedback = feedback_service

    async def next_scene(
        self,
        request_model: GenerationRequest,
    ) -> SceneNextResponse:
        """Request the next scene in scene-by-scene mode.

        Currently returns the current scene state.  Full scene streaming
        follows the same pattern as ``WritingService.stream_generation``.
        """
        return SceneNextResponse(
            request_id=request_model.id,
            scene_number=1,
            status=request_model.status,
        )

    async def accept_scene(
        self,
        request_model: GenerationRequest,
        scene_number: int,
    ) -> AcceptResponse:
        """Accept a specific scene in scene-by-scene mode."""
        await self._record_feedback(request_model, "accept")

        return AcceptResponse(
            request_id=request_model.id,
            chapter_id=request_model.chapter_id,
            word_count=request_model.word_count,
        )

    async def _record_feedback(
        self,
        request_model: GenerationRequest,
        action: str,
    ) -> None:
        """Record feedback via FeedbackCollector if available."""
        if self._feedback is None:
            return

        from narrare_core.memory.models import FeedbackAction, FeedbackEvent

        feedback_action = FeedbackAction(action)
        event = FeedbackEvent(
            user_id=request_model.user_id,
            project_id=request_model.novel_id,
            suggestion_id=request_model.id,
            action=feedback_action,
            intent="write",
            suggestion_text="",
        )
        await self._feedback.record(event)
