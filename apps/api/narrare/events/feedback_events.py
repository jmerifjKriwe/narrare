"""Feedback domain events — dataclass definitions for async processing.

These events are published by the memory service when feedback is recorded
or when preference analysis should be triggered. In-process handlers
(ADR-080) subscribe to these events for async processing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class FeedbackRecorded:
    """Published when a feedback event is successfully recorded.

    Attributes:
        user_id: The user who provided feedback.
        project_id: The project the feedback belongs to.
        event_id: The ID of the recorded FeedbackEvent.
    """

    user_id: UUID
    project_id: UUID
    event_id: UUID


@dataclass(frozen=True, slots=True)
class PreferenceAnalysisTriggered:
    """Published when a preference analysis run should be triggered.

    Attributes:
        user_id: The user whose preferences should be analyzed.
        project_id: The project to analyze.
        event_count: Total number of feedback events at trigger time.
    """

    user_id: UUID
    project_id: UUID
    event_count: int
