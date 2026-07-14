"""Dismissed finding service dependency factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 — runtime DI

if TYPE_CHECKING:
    from narrare.kb.dismissed_service import DismissedFindingService


def get_dismissed_service(session: SessionDep) -> DismissedFindingService:
    """Create a DismissedFindingService with an injected repository.

    No LLM or cache dependencies — this is pure persistence CRUD.
    """
    from narrare.kb.dismissed_repository import DismissedFindingRepository
    from narrare.kb.dismissed_service import DismissedFindingService

    return DismissedFindingService(DismissedFindingRepository(session))
