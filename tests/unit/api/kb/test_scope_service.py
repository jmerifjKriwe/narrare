"""Unit tests for KBScopeService — the promote/demote scope-toggle logic.

Series Foundation Spec 1, Slice 3 Task 3.7.

Covers the :class:`KBScopeService` layer: ownership verification (C1 —
``ForbiddenError`` 403 on a missing/not-owned novel or series), delegation to
the repository scope methods, return-value pass-through, and propagation of the
repository's ``ConflictError`` (scope invariant / Canon-integrity guard D4 →
HTTP 409). HTTP-level status codes are covered in the sibling
``test_scope_endpoints.py`` (RULE-04 file-size split).
"""

from __future__ import annotations

import uuid

import pytest

from narrare_core.kb.schemas.entry import SeriesKBEntry
from narrare_core.shared.errors import ConflictError, ForbiddenError

from ._scope_service_helpers import (
    build_scope_service,
    make_novel_entry,
    make_series_entry,
)

USER_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# promote_to_canon
# ---------------------------------------------------------------------------


class TestPromoteToCanon:
    async def test_delegates_to_repository_and_returns_result(self) -> None:
        """Promote verifies NOVEL ownership, forwards args, returns the result."""
        fx = build_scope_service(user_id=USER_ID)
        entry_id = uuid.uuid4()
        expected = make_series_entry(series_id=fx.series_id)
        fx.kb_repo.set_promote_result(expected)

        result = await fx.service.promote_to_canon(fx.novel_id, entry_id, USER_ID)

        assert result is expected
        assert fx.kb_repo.promote_calls == [(fx.novel_id, entry_id)]

    async def test_not_owned_novel_raises_forbidden(self) -> None:
        """A novel not owned by the caller → 403 (anti-enumeration), no promote."""
        fx = build_scope_service(user_id=USER_ID)

        with pytest.raises(ForbiddenError):
            await fx.service.promote_to_canon(uuid.uuid4(), uuid.uuid4(), USER_ID)

        assert fx.kb_repo.promote_calls == []

    async def test_repo_conflict_propagates(self) -> None:
        """A repository ConflictError (scope invariant) surfaces unchanged (409)."""
        fx = build_scope_service(user_id=USER_ID)
        fx.kb_repo.set_promote_error(ConflictError("Entry not an overlay"))

        with pytest.raises(ConflictError, match="not an overlay"):
            await fx.service.promote_to_canon(fx.novel_id, uuid.uuid4(), USER_ID)


# ---------------------------------------------------------------------------
# demote_to_overlay
# ---------------------------------------------------------------------------


class TestDemoteToOverlay:
    async def test_delegates_to_repository_and_returns_result(self) -> None:
        """Demote verifies SERIES + target-novel ownership, forwards, returns."""
        fx = build_scope_service(user_id=USER_ID)
        entry_id = uuid.uuid4()
        expected = make_novel_entry(novel_id=fx.target_novel_id)
        fx.kb_repo.set_demote_result(expected)

        result = await fx.service.demote_to_overlay(
            fx.series_id, entry_id, fx.target_novel_id, USER_ID
        )

        assert result is expected
        assert fx.kb_repo.demote_calls == [(fx.series_id, entry_id, fx.target_novel_id)]

    async def test_not_owned_series_raises_forbidden(self) -> None:
        fx = build_scope_service(user_id=USER_ID)

        with pytest.raises(ForbiddenError):
            await fx.service.demote_to_overlay(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), USER_ID)

        assert fx.kb_repo.demote_calls == []

    async def test_not_owned_target_novel_raises_forbidden(self) -> None:
        """Series owned but target novel not owned → 403."""
        fx = build_scope_service(user_id=USER_ID)

        with pytest.raises(ForbiddenError):
            await fx.service.demote_to_overlay(fx.series_id, uuid.uuid4(), uuid.uuid4(), USER_ID)

        assert fx.kb_repo.demote_calls == []

    async def test_repo_conflict_propagates(self) -> None:
        """A repository ConflictError (guard D4 / invariant) surfaces unchanged."""
        fx = build_scope_service(user_id=USER_ID)
        fx.kb_repo.set_demote_error(ConflictError("rely on it"))

        with pytest.raises(ConflictError, match="rely"):
            await fx.service.demote_to_overlay(
                fx.series_id, uuid.uuid4(), fx.target_novel_id, USER_ID
            )


# ---------------------------------------------------------------------------
# Sanity
# ---------------------------------------------------------------------------


def test_make_series_entry_is_series_scope() -> None:
    entry = make_series_entry()
    assert isinstance(entry, SeriesKBEntry)
    assert entry.novel_id is None
