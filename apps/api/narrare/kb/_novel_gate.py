"""Shared novel-ownership gate for KB read services (IDOR remediation S9).

Single responsibility (RULE-06): raise ``NotFoundError`` unless the caller
owns the novel — BEFORE any data load, cache probe, or LLM enrichment.
Foreign and unknown novels are indistinguishable (anti-enumeration): both
are a 404. A 403 is never used here — it stays reserved for the existing
series-module semantics (plan constraint, IDOR remediation S9).

Mirrors the S5 precedent ``narrare.writing._helpers.verify_chapter_access``:
a pure composition of the existing ``NovelRepository.get_by_id`` — not a
service method, so no new Protocol is required (RULE-03). Distinct from
``kb.service._verify_novel_ownership``, which leaks ownership via
``ForbiddenError`` (403) and is deliberately NOT reused.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.novels.contracts import NovelRepositoryProtocol


async def verify_novel_owned(
    novel_repo: NovelRepositoryProtocol,
    novel_id: UUID,
    user_id: UUID,
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
