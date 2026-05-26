"""KB consistency check routes — thin delegation to KBConsistencyService (RULE-06).

Provides one endpoint:

- ``POST /novels/{novel_id}/kb/consistency-check`` — run consistency check

Results are cached with a 10-minute TTL.  Pass ``refresh=true`` in the
request body to bypass the cache.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for FastAPI path parameter resolution

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep
from narrare.kb.consistency_contracts import (
    ConsistencyCheckRequest,
    ConsistencyCheckResponse,
)
from narrare.kb.consistency_service import KBConsistencyService
from narrare.kb.dependencies import get_consistency_service

router = APIRouter(tags=["kb"])


@router.post(
    "/novels/{novel_id}/kb/consistency-check",
    response_model=ConsistencyCheckResponse,
    summary="Run a consistency check on the project's KB",
)
async def check_consistency(
    novel_id: uuid.UUID,
    request: ConsistencyCheckRequest,
    user_id: CurrentUserIdDep,
    service: KBConsistencyService = Depends(get_consistency_service),
) -> ConsistencyCheckResponse:
    """Run a consistency check on the project's KB.

    Combines three analysis sources into a single report:
    - Entry-internal: contradictions within a single entry's fields (LLM)
    - Relationship asymmetry: inconsistent reciprocal relationships (algorithmic)
    - Cross-entity: contradictions between entity pairs (LLM via worldbuilding)

    Results are cached (10min TTL).  Use ``refresh=true`` to force a fresh check.
    """
    return await service.check(
        novel_id=novel_id,
        request=request,
    )
