"""KB scope-toggle routes — promote/demote (Series Foundation Spec 1, Task 3.7).

Extracted from ``router.py`` into its own module to respect the RULE-04
150-line router file-size limit. Thin delegation to :class:`KBScopeService`
(RULE-06: routes only delegate; no business logic here). The router is
included by ``router.py`` so the endpoints live under the same ``/api/v1``
prefix and ``kb`` tag as the rest of the KB surface.
"""

import uuid

from fastapi import APIRouter, Depends

from narrare._app.dependencies import CurrentUserIdDep
from narrare.kb.dependencies import get_kb_scope_service
from narrare.kb.schemas import KBDemoteRequest
from narrare.kb.scope_service import KBScopeService
from narrare_core.kb.schemas.entry import NovelKBEntry, SeriesKBEntry

router = APIRouter(tags=["kb"])


@router.post(
    "/novels/{novel_id}/kb/{entry_id}/promote",
    response_model=SeriesKBEntry,
)
async def promote_entry_to_canon(
    novel_id: uuid.UUID,
    entry_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: KBScopeService = Depends(get_kb_scope_service),
) -> SeriesKBEntry:
    """Promote a Novel-Overlay KB entry to Series-Canon.

    Returns 409 Conflict if the entry is not an overlay of ``novel_id`` or the
    novel is not in a series (scope invariant violation).
    """
    return await service.promote_to_canon(novel_id, entry_id)


@router.post(
    "/novels/{novel_id}/kb/{entry_id}/demote",
    response_model=NovelKBEntry,
)
async def demote_entry_to_overlay(
    novel_id: uuid.UUID,
    entry_id: uuid.UUID,
    request: KBDemoteRequest,
    user_id: CurrentUserIdDep,
    service: KBScopeService = Depends(get_kb_scope_service),
) -> NovelKBEntry:
    """Demote a Series-Canon KB entry to a Novel-Overlay for the target novel.

    The path ``novel_id`` is the routing anchor; the authoritative target novel
    and series are taken from the request body. Returns 409 Conflict if the
    entry is not canon of the given series (scope invariant violation).
    """
    return await service.demote_to_overlay(
        series_id=request.series_id,
        entry_id=entry_id,
        target_novel_id=request.target_novel_id,
    )
