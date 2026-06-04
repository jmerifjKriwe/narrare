"""Memory API service contracts — written before implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.memory.models import FeedbackEventModel, PreferenceProfileModel
    from narrare.memory.schemas import (
        AnalyzeResponse,
        FeedbackRequest,
        FeedbackResponse,
        PreferenceResponse,
        ResetResponse,
    )


# ---------------------------------------------------------------------------
# Repository Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class FeedbackRepositoryProtocol(Protocol):
    """Protocol for FeedbackRepository — defines the DB query interface."""

    async def create(self, event: FeedbackEventModel) -> FeedbackEventModel: ...

    async def get_event_count(self, user_id: uuid.UUID, project_id: uuid.UUID) -> int: ...

    async def get_events_batch(
        self, user_id: uuid.UUID, project_id: uuid.UUID, *, limit: int = 50
    ) -> list[FeedbackEventModel]: ...

    async def list_by_user_project(
        self, user_id: uuid.UUID, project_id: uuid.UUID, *, limit: int = 100
    ) -> list[FeedbackEventModel]: ...

    async def delete_by_user_project(self, user_id: uuid.UUID, project_id: uuid.UUID) -> int: ...


@runtime_checkable
class PreferenceProfileRepositoryProtocol(Protocol):
    """Protocol for PreferenceProfileRepository — defines the DB query interface."""

    async def upsert(self, profile: PreferenceProfileModel) -> PreferenceProfileModel: ...

    async def get(
        self, user_id: uuid.UUID, project_id: uuid.UUID
    ) -> PreferenceProfileModel | None: ...


# ---------------------------------------------------------------------------
# Service Protocols
# ---------------------------------------------------------------------------


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
