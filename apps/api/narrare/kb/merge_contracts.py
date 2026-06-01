"""KB merge service contract — Protocol definition.

Contracts are written before implementation (RULE-03).
Per-feature contract extracted from a hypothetical shared contract file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.kb.schemas_merge import MergeRequest, MergeResponse


@runtime_checkable
class KBMergeServiceProtocol(Protocol):
    """Protocol for KB merge analysis service.

    Evaluates candidate entity pairs and recommends merge strategies,
    deciding whether two entities should be merged, kept distinct,
    or flagged as uncertain for human review.
    """

    async def analyze_merge_candidates(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: MergeRequest,
    ) -> MergeResponse: ...
