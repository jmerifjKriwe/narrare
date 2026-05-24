"""Embedding dependency injection factories.

RULE-19: Uses SessionDep, not bare AsyncSession.
"""

from __future__ import annotations

from narrare._app.dependencies import SessionDep  # noqa: TC001
from narrare.embeddings.repository import EmbeddingRepository
from narrare.embeddings.service import EmbeddingService


def get_embedding_repository(session: SessionDep) -> EmbeddingRepository:
    """Create an EmbeddingRepository with the given session."""
    return EmbeddingRepository(session)


def get_embedding_service(session: SessionDep) -> EmbeddingService:
    """Create an EmbeddingService with injected dependencies."""
    repo = EmbeddingRepository(session)
    return EmbeddingService(repo)
