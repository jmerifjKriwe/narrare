"""KB consistency check routes — thin delegation to services (RULE-06).

Provides four endpoints:

- ``POST /novels/{novel_id}/kb/consistency-check`` — run consistency check
- ``POST /novels/{novel_id}/kb/consistency/dismiss`` — dismiss a finding
- ``GET /novels/{novel_id}/kb/consistency/dismissed`` — list dismissed
- ``DELETE /novels/{novel_id}/kb/consistency/dismissed/{fingerprint}`` — un-dismiss

Check results are cached with a 10-minute TTL.  Pass ``refresh=true`` in the
request body to bypass the cache.  Dismissed findings are persisted per-novel
(CR-AUFG-07-26).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep
from narrare.kb.consistency_contracts import (
    ConsistencyCheckRequest,
    ConsistencyCheckResponse,
    DismissedFindingsResponse,
    DismissFindingRequest,
)
from narrare.kb.consistency_service import KBConsistencyService
from narrare.kb.dependencies import get_consistency_service, get_dismissed_service
from narrare.kb.dismissed_service import DismissedFindingService

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
        user_id=user_id,
    )


# ---------------------------------------------------------------------------
# Dismissed findings (CR-AUFG-07-26)
# ---------------------------------------------------------------------------


@router.post(
    "/novels/{novel_id}/kb/consistency/dismiss",
    response_model=DismissedFindingsResponse,
    summary="Dismiss a consistency finding",
)
async def dismiss_finding(
    novel_id: uuid.UUID,
    request: DismissFindingRequest,
    user_id: CurrentUserIdDep,
    service: DismissedFindingService = Depends(get_dismissed_service),
) -> DismissedFindingsResponse:
    """Dismiss (ignore) a consistency finding by its stable fingerprint.

    Idempotent — dismissing the same fingerprint twice updates the reason
    rather than creating a duplicate.  Returns the full updated list of
    dismissed fingerprints for the novel.
    """
    return await service.dismiss_finding(
        novel_id=novel_id,
        request=request,
        user_id=user_id,
    )


@router.get(
    "/novels/{novel_id}/kb/consistency/dismissed",
    response_model=DismissedFindingsResponse,
    summary="List dismissed consistency findings",
)
async def list_dismissed(
    novel_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: DismissedFindingService = Depends(get_dismissed_service),
) -> DismissedFindingsResponse:
    """List all dismissed consistency finding fingerprints for a novel.

    The frontend uses this list to filter out dismissed issues from
    consistency check results.
    """
    return await service.list_dismissed(novel_id=novel_id)


@router.delete(
    "/novels/{novel_id}/kb/consistency/dismissed/{fingerprint}",
    response_model=DismissedFindingsResponse,
    summary="Un-dismiss a consistency finding",
)
async def undismiss_finding(
    novel_id: uuid.UUID,
    fingerprint: str,
    user_id: CurrentUserIdDep,
    service: DismissedFindingService = Depends(get_dismissed_service),
) -> DismissedFindingsResponse:
    """Re-enable a previously dismissed consistency finding.

    The ``fingerprint`` path parameter must be URL-encoded by the client.
    Returns the full updated list of dismissed fingerprints for the novel.
    """
    return await service.undismiss_finding(
        novel_id=novel_id,
        fingerprint=fingerprint,
    )
