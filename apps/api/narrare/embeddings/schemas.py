"""Embedding admin API schemas — Pydantic request/response models.

Defines the request and response models for the embedding admin endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EmbeddingStatsResponse(BaseModel):
    """Response model for embedding status endpoint."""

    total: int = Field(description="Total number of embeddable entities")
    embedded: int = Field(description="Entities with up-to-date embeddings")
    pending: int = Field(description="Entities queued but not yet processed")
    failed: int = Field(description="Entities whose embedding generation failed")
    coverage_percentage: float = Field(description="Percentage of embedded entities (0-100)")


class ReprocessRequest(BaseModel):
    """Request model for reprocessing endpoint."""

    model: str | None = Field(
        default=None,
        description="Optional model override for reprocessing",
    )


class ReprocessResponse(BaseModel):
    """Response model for reprocessing endpoint."""

    queued: int = Field(description="Number of tasks queued")
    message: str = Field(description="Human-readable status message")


class ModelInfoResponse(BaseModel):
    """Response model for current embedding model info."""

    model: str = Field(description="Currently active embedding model")
    dimension: int = Field(description="Dimension of the embedding vectors")
    provider: str = Field(description="Embedding provider (e.g. 'openai')")
