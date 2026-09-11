"""Settings ownership dependencies (IDOR remediation, plan S11).

FastAPI dependency gates for the settings module's project-scoped
surfaces. Before S11 these routes read and wrote project-keyed rows
(``project_settings``, ``project_token_limits``) without any ownership
check — and the settings repositories AUTO-CREATE a row on first read,
so a foreign id even materialized a settings row for the victim.

The gate resolves the caller via ``CurrentUserIdDep`` and the novel via
the user-scoped ``NovelRepository.get_by_id``. A missing and a
not-owned novel are indistinguishable (anti-enumeration): both raise
``NotFoundError`` → HTTP 404. A 403 is never used here — it stays
reserved for the series-module semantics (plan constraint).

Precedent: ``series/dependencies.py::verify_novel_in_owned_series``
(same dependency shape; that one keeps the series module's 403 stance,
these use the plan's 404 stance for novel-scoped resources).

Since batch-review follow-up W3 the ownership lookup itself is
canonical in ``narrare.novels.ownership`` (shared across domains);
these wrappers keep their FastAPI signatures — path parameters are
resolved into dependency parameters BY NAME, which is why there are
two required-path variants (``{novel_id}`` vs ``{project_id}``
routes) plus one optional-query variant for the resolved-limits read
that only carries a project scope when requested.

Because these are dependencies, they run BEFORE the route handler —
i.e. before the auto-creating ``ProjectSettingsRepository.get`` /
``ProjectTokenLimitsRepository.get`` is ever constructed.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for FastAPI DI resolution

from narrare._app.dependencies import (  # noqa: TC001 - needed at runtime for FastAPI DI
    CurrentUserIdDep,
    SessionDep,
)
from narrare.novels.ownership import ensure_novel_owned, require_owned_novel


async def verify_novel_owned(
    novel_id: uuid.UUID,
    session: SessionDep,
    user_id: CurrentUserIdDep,
) -> None:
    """Route gate for ``{novel_id}``-keyed settings routes (plan S11a).

    Applies to GET/PATCH ``/settings/novels/{novel_id}`` — the project
    settings repository stays novel-keyed; THIS dependency is the gate.
    """
    await require_owned_novel(session, user_id, novel_id)


async def verify_project_owned(
    project_id: uuid.UUID,
    session: SessionDep,
    user_id: CurrentUserIdDep,
) -> None:
    """Route gate for ``{project_id}``-keyed token-limit routes (plan S11b).

    ``project_id`` IS the novel UUID on this surface (project ≡ novel).
    """
    await require_owned_novel(session, user_id, project_id)


async def verify_owned_project_scope(
    session: SessionDep,
    user_id: CurrentUserIdDep,
    project_id: uuid.UUID | None = None,
) -> None:
    """Scope gate for the optional ``?project_id=`` on the resolved read.

    GET ``/settings/token-limits/`` legitimately resolves user-level
    limits without a project scope — no gate in that case. When a
    project scope IS requested, the caller must own it (the project
    read would otherwise leak — and auto-create — the victim's row).
    """
    await ensure_novel_owned(session, user_id, project_id)
