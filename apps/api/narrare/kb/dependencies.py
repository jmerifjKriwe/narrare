"""KB dependency injection factories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.relationship_service import RelationshipService
    from narrare.kb.repository import KBRepository
    from narrare.kb.service import KBService


def get_kb_repository(session: SessionDep) -> KBRepository:
    """Create a KBRepository with the given session."""
    from narrare.kb.repository import KBRepository

    return KBRepository(session)


def get_kb_service(session: SessionDep) -> KBService:
    """Create a KBService with injected dependencies."""
    from narrare.kb.repository import KBRepository
    from narrare.kb.service import KBService
    from narrare.novels.repository import NovelRepository

    return KBService(
        repo=KBRepository(session),
        novel_repo=NovelRepository(session),
    )


def get_rel_repository(
    session: SessionDep,
) -> RelationshipRepository:
    """Create a RelationshipRepository with the given session."""
    from narrare.kb.relationship_repository import RelationshipRepository

    return RelationshipRepository(session)


def get_rel_service(session: SessionDep) -> RelationshipService:
    """Create a RelationshipService with injected dependencies."""
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.relationship_service import RelationshipService
    from narrare.kb.repository import KBRepository

    return RelationshipService(
        rel_repo=RelationshipRepository(session),
        entry_repo=KBRepository(session),
    )
