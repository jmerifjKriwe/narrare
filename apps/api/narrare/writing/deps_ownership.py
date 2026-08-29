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
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from narrare._app.dependencies import (  # noqa: TC001 - needed at runtime for FastAPI DI
    CurrentUserIdDep,
    SessionDep,
)
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def _require_owned_novel(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> None:
    """Raise ``NotFoundError`` unless ``user_id`` owns ``novel_id``.

    Shared core of the gates in this module — the ownership lookup
    itself (mirrors ``settings/dependencies.py``).

    ``NovelRepository`` is imported at CALL time so hermetic unit tests
    that patch ``narrare.novels.repository.NovelRepository`` (the
    established factory-test patch point) intercept this lookup too —
    a module-level reference would bypass the patch and drive the real
    repository over a mock session.
    """
    from narrare.novels.repository import NovelRepository

    novel = await NovelRepository(session).get_by_id(novel_id, uuid.UUID(user_id))
    if novel is None:
        raise NotFoundError("Novel", identifier=str(novel_id))


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
    await _require_owned_novel(session, user_id, novel_id)


async def ensure_novel_owned(
    session: AsyncSession,
    user_id: str,
    project_id: uuid.UUID | None,
) -> None:
    """Factory-entry ownership gate for the writing LLM service factories.

    Batch-review follow-up N1: the five writing factories
    (writing/extend/rewrite/coauthor/style-variants) resolve model
    routing and token limits BEFORE the service-layer ownership gate.
    Both resolutions read project-keyed settings through auto-creating
    repositories (``ProjectAiSettingsRepository.get`` /
    ``ProjectTokenLimitsRepository.get`` flush a new row on first read),
    so an unknown ``project_id`` surfaced as an FK ``IntegrityError``
    (HTTP 500 — a novel-existence oracle) and a foreign ``project_id``
    materialized a transient settings row for the victim.

    This gate runs at factory entry, BEFORE any resolver/limits call
    (the committed pattern from ``generation/router.py``, plan S12b):
    missing and foreign novels are indistinguishable
    (``NotFoundError`` → 404). ``project_id=None`` (user-scope only) is
    legitimate and passes without a query.
    """
    if project_id is None:
        return
    await _require_owned_novel(session, user_id, project_id)
