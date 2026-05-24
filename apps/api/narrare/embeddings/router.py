"""Embedding admin routes — thin delegation to EmbeddingService.

Provides admin API endpoints for embedding management:
status, reprocessing, and model info.

RULE-06: Router only delegates — no business logic.
"""

from __future__ import annotations

import uuid  # noqa: TC003

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep
from narrare.embeddings.dependencies import get_embedding_service
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
) -> EmbeddingStatsResponse:
    """Return embedding statistics for a novel."""
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
) -> ReprocessResponse:
    """Trigger re-embedding for all content in a novel."""
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
    """Return the currently active embedding model and dimension."""
    return ModelInfoResponse(
        model=service.model,
        dimension=service.dimension,
        provider=service.provider,
    )
