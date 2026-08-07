"""KB Series-Canon CRUD routes — thin delegation to KBCanonService (RULE-06).

Series Foundation Spec 1, Slice 3 Task 3.8.

Exposes the Canon half of the ``kb_entries`` scope split under
``/api/v1/series/{series_id}/kb``. The router only delegates to
:class:`KBCanonService` — no business logic lives here (RULE-06). Domain
errors (:class:`NotFoundError`, :class:`ForbiddenError`, :class:`ConflictError`)
raised by the service are mapped to HTTP (404 / 403 / 409) by the global
``NarrareError`` handler in ``_app/main.py``, so the router carries no
error-translation code.

Extracted into its own module to respect the RULE-04 150-line router file-size
limit. The router is included by ``router.py`` so the endpoints live under the
same ``/api/v1`` prefix and ``kb`` tag as the rest of the KB surface.
"""

import uuid

from fastapi import APIRouter, Depends, status

from narrare._app.dependencies import CurrentUserIdDep
from narrare.kb.canon_service import KBCanonService
from narrare.kb.dependencies import get_kb_canon_service
from narrare.kb.schemas import KBEntryCreate, KBEntryUpdate
from narrare_core.kb.schemas.entry import SeriesKBEntry

router = APIRouter(tags=["kb"])


@router.get(
    "/series/{series_id}/kb",
    response_model=list[SeriesKBEntry],
)
async def list_canon_entries(
    series_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: KBCanonService = Depends(get_kb_canon_service),
) -> list[SeriesKBEntry]:
    """List all Series-Canon KB entries for a series."""
    return await service.list_canon(series_id, uuid.UUID(user_id))


@router.post(
    "/series/{series_id}/kb",
    response_model=SeriesKBEntry,
    status_code=status.HTTP_201_CREATED,
)
async def create_canon_entry(
    series_id: uuid.UUID,
    request: KBEntryCreate,
    user_id: CurrentUserIdDep,
    service: KBCanonService = Depends(get_kb_canon_service),
) -> SeriesKBEntry:
    """Create a new Series-Canon KB entry (shared across all novels of the series)."""
    return await service.create_canon(series_id, uuid.UUID(user_id), request)


@router.get(
    "/series/{series_id}/kb/{entry_id}",
    response_model=SeriesKBEntry,
)
async def get_canon_entry(
    series_id: uuid.UUID,
    entry_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: KBCanonService = Depends(get_kb_canon_service),
) -> SeriesKBEntry:
    """Get a single Series-Canon KB entry."""
    return await service.get_canon(series_id, entry_id, uuid.UUID(user_id))


@router.patch(
    "/series/{series_id}/kb/{entry_id}",
    response_model=SeriesKBEntry,
)
async def update_canon_entry(
    series_id: uuid.UUID,
    entry_id: uuid.UUID,
    request: KBEntryUpdate,
    user_id: CurrentUserIdDep,
    service: KBCanonService = Depends(get_kb_canon_service),
) -> SeriesKBEntry:
    """Update a Series-Canon KB entry."""
    return await service.update_canon(series_id, entry_id, uuid.UUID(user_id), request)


@router.delete(
    "/series/{series_id}/kb/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_canon_entry(
    series_id: uuid.UUID,
    entry_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    service: KBCanonService = Depends(get_kb_canon_service),
) -> None:
    """Delete a Series-Canon KB entry."""
    await service.delete_canon(series_id, entry_id, uuid.UUID(user_id))
