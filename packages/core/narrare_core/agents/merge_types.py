"""Output types for KBMergeAgent.

See ADR-015 Phase 2.1 — Output Types.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MergeStrategy(BaseModel):
    """Strategy for a merge operation.

    Attributes:
        keep_name: Which name to retain.
        merge_fields: How to combine each field (field -> value mapping).
        preserve_aliases: Alternative names to keep as aliases.
        merge_relationships: Whether to merge relationship lists.
    """

    keep_name: str = ""
    merge_fields: dict[str, str] = {}
    preserve_aliases: list[str] = []
    merge_relationships: bool = True


class MergeDecision(BaseModel):
    """A single merge decision for a candidate pair.

    Attributes:
        pair_id: Identifier for the candidate pair.
        decision: One of merge, distinct, uncertain.
        confidence: Confidence score between 0.0 and 1.0.
        reasoning: Explanation of the decision.
        merge_strategy: Strategy for merging (only when decision is merge).
    """

    pair_id: str = ""
    decision: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    merge_strategy: MergeStrategy | None = None


class MergeOutput(BaseModel):
    """Structured output of a KBMergeAgent run.

    Attributes:
        merge_decisions: List of decisions for each candidate pair.
        overall_notes: Summary of the merge analysis.
        metadata: Additional metadata (model info, tokens, etc.).
    """

    merge_decisions: list[MergeDecision] = []
    overall_notes: str = ""
    metadata: dict[str, Any] = {}
