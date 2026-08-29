"""Writing ownership route gate (IDOR remediation S13).

FastAPI dependency gate for the writing module's novel-scoped read
surfaces. ``GET /writing/novels/{novel_id}/stats`` delegated to
``WritingService.get_stats`` which accepted ``user_id`` but ignored it
— any authenticated caller could aggregate another user's generation
statistics by novel id.

The gate resolves the caller via ``CurrentUserIdDep`` and the novel via
the user-scoped ``NovelRepository.get_by_id``. A missing and a
not-owned novel are indistinguishable (anti-enumeration): both raise
``NotFoundError`` → HTTP 404. A 403 is never used here — it stays
reserved for the series-module semantics (plan constraint).

Precedent: ``settings/dependencies.py::verify_novel_owned`` (plan S11a —
same dependency shape). The gate lands at the ROUTE level rather than
the plan's original service-level one-liner because
``writing/service.py`` sits exactly at the RULE-04 hard limit (300
lines); ``get_stats`` has no non-HTTP callers, so the route gate covers
the full attack surface.
"""

from __future__ import annotations

import uuid

from narrare._app.dependencies import (  # noqa: TC001 - needed at runtime for FastAPI DI
    CurrentUserIdDep,
    SessionDep,
)
from narrare.novels.repository import NovelRepository
from narrare_core.shared.errors import NotFoundError


async def verify_novel_owned(
    novel_id: uuid.UUID,
    session: SessionDep,
    user_id: CurrentUserIdDep,
) -> None:
    """Route gate for ``{novel_id}``-keyed writing routes (plan S13).

    Raises ``NotFoundError`` unless ``user_id`` owns ``novel_id`` —
    before the handler (and therefore before any writing-service
    construction or stats aggregation) runs.
    """
    novel = await NovelRepository(session).get_by_id(novel_id, uuid.UUID(user_id))
    if novel is None:
        raise NotFoundError("Novel", identifier=str(novel_id))
