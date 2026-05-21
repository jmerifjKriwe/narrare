"""Memory API service contracts — written before implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.memory.schemas import (
        AnalyzeResponse,
        FeedbackRequest,
        FeedbackResponse,
        PreferenceResponse,
        ResetResponse,
    )


@runtime_checkable
class FeedbackServiceProtocol(Protocol):
    async def record_feedback(
        self, request: FeedbackRequest, user_id: uuid.UUID
    ) -> FeedbackResponse: ...


@runtime_checkable
class PreferenceServiceProtocol(Protocol):
    async def get_preferences(
        self, user_id: uuid.UUID, project_id: uuid.UUID
    ) -> PreferenceResponse: ...

    async def reset_preferences(
        self, user_id: uuid.UUID, project_id: uuid.UUID
    ) -> ResetResponse: ...


@runtime_checkable
class PreferenceAnalysisServiceProtocol(Protocol):
    async def analyze(self, user_id: uuid.UUID, project_id: uuid.UUID) -> AnalyzeResponse: ...
