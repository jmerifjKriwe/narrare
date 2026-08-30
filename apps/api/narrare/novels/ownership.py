"""Canonical novel-ownership gates (IDOR remediation; consolidated W3).

The novels domain owns Novel ownership semantics, so the ONE canonical
implementation of the ownership gate lives here. Before W3 the same
gate existed in five divergent copies (kb service gate, settings /
writing / embeddings route gates, plus inline factory gates in
generation and story-suggest); W3 consolidated them with ZERO behavior
change — every IDOR matrix pins these semantics.

Two KINDS exist deliberately and are NOT merged:

1. Service-level pure gate — :func:`verify_novel_owned`: takes an
   injected ``NovelRepositoryProtocol`` + typed UUIDs. A pure
   composition of the user-scoped ``get_by_id`` — not a service method,
   so no new Protocol is required (RULE-03; mirrors the S5 precedent
   ``narrare.writing._helpers.verify_chapter_access``).
2. Session-level core — :func:`require_owned_novel` and
   :func:`ensure_novel_owned`: take the ``AsyncSession`` + the route
   layer's ``str`` user id, construct the repository, and delegate to
   the pure gate. ``ensure_novel_owned`` adds the optional project
   scope (``None`` = user-scope only → no query).

FastAPI ``Depends`` wrappers (three in ``settings/dependencies.py``,
plus ``writing/deps_ownership.py`` and ``embeddings/dependencies.py``)
stay in their domain modules: their signatures ARE the route contract
(path parameters are resolved BY NAME), so they remain thin adapters
that delegate here instead of duplicating the lookup.

Semantics (pinned by the IDOR matrices — do not change):

- Raise ``NotFoundError`` unless the caller owns the novel — BEFORE any
  data load, cache probe, settings auto-creation, or LLM enrichment.
- Foreign ≡ unknown (anti-enumeration): both are a 404. A 403 is never
  used here — it stays reserved for the series-module semantics.
- Distinct from ``kb.service._verify_novel_ownership``, which leaks
  ownership via ``ForbiddenError`` (403) and is deliberately NOT
  consolidated into this module.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.novels.contracts import NovelRepositoryProtocol


async def verify_novel_owned(
    novel_repo: NovelRepositoryProtocol,
    novel_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Raise ``NotFoundError`` unless ``user_id`` owns ``novel_id``.

    Args:
        novel_repo: Novel repository — the ownership lookup.
        novel_id: The novel being accessed.
        user_id: The caller's identity (ownership gate input).

    Raises:
        NotFoundError: The novel is unknown or owned by another user —
            both cases are indistinguishable by design.
    """
    novel = await novel_repo.get_by_id(novel_id, user_id)
    if novel is None:
        raise NotFoundError("Novel", identifier=str(novel_id))


async def require_owned_novel(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> None:
    """Raise ``NotFoundError`` unless ``user_id`` (str) owns ``novel_id``.

    Session-level core shared by the FastAPI route-dep adapters in the
    settings / writing / embeddings domains: constructs the repository
    over ``session``, parses the route layer's string user id, and
    delegates to :func:`verify_novel_owned`.

    ``NovelRepository`` is imported at CALL time so hermetic unit tests
    that patch ``narrare.novels.repository.NovelRepository`` (the
    established factory-test patch point, e.g. the writing factory
    ownership gate matrix) intercept this lookup too — a module-level
    reference would bypass the patch and drive the real repository over
    a mock session.
    """
    from narrare.novels.repository import NovelRepository

    await verify_novel_owned(NovelRepository(session), novel_id, uuid.UUID(user_id))


async def ensure_novel_owned(
    session: AsyncSession,
    user_id: str,
    project_id: uuid.UUID | None,
) -> None:
    """Factory-entry ownership gate for optional project scopes.

    Used by service factories that resolve model routing / token limits
    from project-keyed settings BEFORE the service layer runs: an
    unknown ``project_id`` would surface as an FK ``IntegrityError``
    (HTTP 500 — a novel-existence oracle) and a foreign one would
    materialize a transient settings row via the auto-creating
    repositories. Both are gated here → ``NotFoundError`` → 404, before
    any resolver call.

    ``project_id=None`` (user-scope only) is legitimate and passes
    without a query.
    """
    if project_id is None:
        return
    await require_owned_novel(session, user_id, project_id)
