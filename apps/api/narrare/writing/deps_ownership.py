"""Writing ownership gates (IDOR remediation S13 + factory pre-gate).

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

``ensure_novel_owned`` (batch-review follow-up N1, 2026-08-29) is the
factory-entry variant of the same gate: the writing LLM factories call
it BEFORE model-routing / token-limit resolution, because both read
project-keyed settings through auto-creating repositories — an unknown
novel would surface as an FK IntegrityError (500, existence oracle)
and a foreign novel would materialize a transient settings row.

Since batch-review follow-up W3 the canonical implementations live in
``narrare.novels.ownership`` (the novels domain owns Novel ownership
semantics): the route dependency below delegates to
``require_owned_novel`` and ``ensure_novel_owned`` is re-exported so
the six factory import sites stay stable.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for FastAPI DI resolution

from narrare._app.dependencies import (  # noqa: TC001 - needed at runtime for FastAPI DI
    CurrentUserIdDep,
    SessionDep,
)
from narrare.novels.ownership import ensure_novel_owned, require_owned_novel

__all__ = ["ensure_novel_owned", "verify_novel_owned"]


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
    await require_owned_novel(session, user_id, novel_id)
