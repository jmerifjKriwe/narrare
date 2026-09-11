"""Embedding dependency injection factories + ownership route gate.

RULE-19: Uses SessionDep, not bare AsyncSession.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for FastAPI DI resolution

from narrare._app.dependencies import (  # noqa: TC001 - needed at runtime for FastAPI DI
    CurrentUserIdDep,
    SessionDep,
)
from narrare.embeddings.repository import EmbeddingRepository
from narrare.embeddings.service import EmbeddingService
from narrare.novels.ownership import require_owned_novel


def get_embedding_repository(session: SessionDep) -> EmbeddingRepository:
    """Create an EmbeddingRepository with the given session."""
    return EmbeddingRepository(session)


def get_embedding_service(session: SessionDep) -> EmbeddingService:
    """Create an EmbeddingService with injected dependencies."""
    repo = EmbeddingRepository(session)
    return EmbeddingService(repo)


async def verify_novel_owned(
    novel_id: uuid.UUID,
    session: SessionDep,
    user_id: CurrentUserIdDep,
) -> None:
    """Route gate for the novel-scoped embedding admin routes (plan S13, D3:a).

    ``GET/POST /admin/embeddings/{status,reprocess}/{novel_id}`` address
    the victim's novel, so they get the same ownership gate as every
    other novel-scoped surface — even though both are inert today (no
    source ids are wired through the router): a future wiring change
    inherits the gate instead of re-opening the IDOR.

    A missing and a not-owned novel are indistinguishable
    (anti-enumeration): both raise ``NotFoundError`` → HTTP 404. A 403
    is never used here — it stays reserved for the series-module
    semantics (plan constraint). Precedent:
    ``settings/dependencies.py::verify_novel_owned`` (plan S11a); the
    canonical lookup lives in ``narrare.novels.ownership`` (W3).
    """
    await require_owned_novel(session, user_id, novel_id)
