"""Embedding dependency injection factories + ownership route gate.

RULE-19: Uses SessionDep, not bare AsyncSession.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for FastAPI DI resolution
from typing import TYPE_CHECKING

import structlog

from narrare._app.dependencies import (  # noqa: TC001 - needed at runtime for FastAPI DI
    CurrentUserIdDep,
    SessionDep,
)
from narrare.embeddings.repository import EmbeddingRepository
from narrare.embeddings.service import EmbeddingService
from narrare.kb.repository import KBRepository
from narrare.novels.ownership import require_owned_novel
from narrare_core.embeddings.rerank import MultiVectorReranker, is_rerank_available
from narrare_core.settings import get_core_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

    from narrare.embeddings.contracts import TextFetcher
    from narrare_core.embeddings.rerank import Reranker

logger = structlog.get_logger(__name__)


def get_embedding_repository(session: SessionDep) -> EmbeddingRepository:
    """Create an EmbeddingRepository with the given session."""
    return EmbeddingRepository(session)


def _make_kb_text_fetcher(session: SessionDep) -> TextFetcher:
    """Close over the KB repository for candidate-text supply (ADR-090 D4).

    Search rows carry no text; the fetcher batch-loads the embedded body
    text (one SELECT via ``KBRepository.get_bodies_by_ids``) so the Core
    reranker receives fully materialized candidates and stays I/O-free
    (RULE-07). Ids without a body are absent from the mapping — the rerank
    stage keeps those candidates in their first-stage position.
    """
    kb_repo = KBRepository(session)

    async def fetch(source_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
        return await kb_repo.get_bodies_by_ids(source_ids)

    return fetch


def build_rerank_components(session: SessionDep) -> tuple[Reranker | None, TextFetcher | None]:
    """Resolve the opt-in rerank stage wiring (ADR-090 Decisions 5-6).

    - Flag off (shipped default): no components — the service keeps the
      byte-identical pre-rerank search path.
    - Flag on, ``embeddings`` extra absent: ONE structured warning
      (``embedding_rerank_unavailable``, ``reason="extra_missing"``) and no
      components - the stage stays inert, search returns the pre-rerank
      order (RULE-11: degradation is loud, search never breaks).
    - Flag on, extra present: a ``MultiVectorReranker`` on the pinned
      settings checkpoint (``embedding_rerank_model``, ADR-090 D5) plus the
      KB text fetcher.
    """
    settings = get_core_settings()
    if not settings.embedding_rerank_enabled:
        return None, None
    if not is_rerank_available():
        logger.warning("embedding_rerank_unavailable", reason="extra_missing")
        return None, None
    return MultiVectorReranker(settings.embedding_rerank_model), _make_kb_text_fetcher(session)


def get_embedding_service(session: SessionDep) -> EmbeddingService:
    """Create an EmbeddingService with injected dependencies."""
    repo = EmbeddingRepository(session)
    reranker, text_fetcher = build_rerank_components(session)
    return EmbeddingService(repo, reranker=reranker, text_fetcher=text_fetcher)


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
