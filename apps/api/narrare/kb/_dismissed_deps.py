"""Dismissed finding service dependency factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 — runtime DI
from narrare.kb._feedback_memory_deps import (
    get_consistency_feedback_memory_instance,
)

if TYPE_CHECKING:
    from narrare.kb.dismissed_service import DismissedFindingService


def get_dismissed_service(session: SessionDep) -> DismissedFindingService:
    """Create a DismissedFindingService with an injected repository.

    Pure persistence CRUD plus an optional mem0 learning-layer forward
    (CR-AUFG-03-10). The feedback memory is a process-wide singleton that
    returns ``None`` when mem0 is unavailable (graceful degradation).
    NovelRepository backs the novel ownership gate (IDOR fix S10).
    """
    from narrare.kb.dismissed_repository import DismissedFindingRepository
    from narrare.kb.dismissed_service import DismissedFindingService
    from narrare.novels.repository import NovelRepository

    feedback_memory = get_consistency_feedback_memory_instance()
    return DismissedFindingService(
        DismissedFindingRepository(session),
        NovelRepository(session),
        feedback_memory=feedback_memory,
    )
