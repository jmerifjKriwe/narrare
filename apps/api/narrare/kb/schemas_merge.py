"""KB merge / deduplication schemas — extracted from schemas.py per RULE-04.

Contains request/response models for the KB entity merge analysis endpoint.
See KB-009-kb-merge.md for the full feature spec.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MergeStrategyRequest(BaseModel):
    """Strategy for a merge operation."""

    keep_name: str = ""
    merge_fields: dict[str, str] = {}
    preserve_aliases: list[str] = []
    merge_relationships: bool = True


class MergeDecisionResponse(BaseModel):
    """A single merge decision."""

    pair_id: str = ""
    decision: str = ""  # merge|distinct|uncertain
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = ""
    merge_strategy: MergeStrategyRequest | None = None


class MergeRequest(BaseModel):
    """Request to analyze merge candidates."""

    entity_type: str = Field(min_length=1, max_length=50)
    candidate_pairs: list[dict[str, object]] = []


class MergeResponse(BaseModel):
    """Response with merge analysis."""

    merge_decisions: list[MergeDecisionResponse] = []
    overall_notes: str = ""
