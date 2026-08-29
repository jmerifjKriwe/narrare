"""Embedding admin routes — thin delegation to EmbeddingService.

Provides admin API endpoints for embedding management:
status, reprocessing, and model info.

Ownership stance (IDOR remediation S13, PO decision D3:a):

- ``status/{novel_id}`` and ``reprocess/{novel_id}`` address a specific
  novel → gated by ``verify_novel_owned`` (foreign/unknown → 404). Both
  are inert today (the router passes no source ids), but the gate runs
  first so a future wiring change inherits it.
- ``model`` is global-inert (returns the active embedding model — no
  per-user or per-novel data) → minimal gate: any authenticated user
  (``CurrentUserIdDep``); 401 without a token.

RULE-06: Router only delegates — no business logic.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep
from narrare.embeddings.dependencies import get_embedding_service, verify_novel_owned
from narrare.embeddings.schemas import (
    EmbeddingStatsResponse,
    ModelInfoResponse,
    ReprocessRequest,
    ReprocessResponse,
)
from narrare.embeddings.service import EmbeddingService

router = APIRouter(tags=["embeddings"])


@router.get(
    "/api/v1/admin/embeddings/status/{novel_id}",
    response_model=EmbeddingStatsResponse,
)
async def get_embedding_status(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: EmbeddingService = Depends(get_embedding_service),
    _: None = Depends(verify_novel_owned),
) -> EmbeddingStatsResponse:
    """Return embedding statistics for a novel (owner-only, IDOR S13)."""
    stats = await service.get_status(novel_id)
    return EmbeddingStatsResponse(
        total=stats.total,
        embedded=stats.embedded,
        pending=stats.pending,
        failed=stats.failed,
        coverage_percentage=stats.coverage_percentage,
    )


@router.post(
    "/api/v1/admin/embeddings/reprocess/{novel_id}",
    response_model=ReprocessResponse,
)
async def reprocess_embeddings(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    request: ReprocessRequest | None = None,
    service: EmbeddingService = Depends(get_embedding_service),
    _: None = Depends(verify_novel_owned),
) -> ReprocessResponse:
    """Trigger re-embedding for all content in a novel (owner-only, IDOR S13)."""
    queued = await service.reprocess(
        novel_id,
        model=request.model if request else None,
    )
    return ReprocessResponse(
        queued=queued,
        message=f"Queued {queued} items for reprocessing",
    )


@router.get(
    "/api/v1/admin/embeddings/model",
    response_model=ModelInfoResponse,
)
async def get_model_info(
    user_id: CurrentUserIdDep,
    service: EmbeddingService = Depends(get_embedding_service),
) -> ModelInfoResponse:
    """Return the currently active embedding model and dimension.

    Global-inert resource (D3:a): the minimal gate is authenticated-user
    existence — no per-novel ownership applies.
    """
    return ModelInfoResponse(
        model=service.model,
        dimension=service.dimension,
        provider=service.provider,
    )
