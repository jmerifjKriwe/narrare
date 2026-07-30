"""Unit tests for KBScopeService — the promote/demote scope-toggle logic.

Series Foundation Spec 1, Slice 3 Task 3.7.

Covers the thin :class:`KBScopeService` wrapper: delegation to the repository
scope methods, return-value pass-through, and translation of the repository's
invariant-violation ``ValueError`` into a domain ``ConflictError`` (the cause
of the HTTP 409 surfaced to clients). HTTP-level status codes are covered in
the sibling ``test_scope_endpoints.py`` (RULE-04 file-size split).
"""

from __future__ import annotations

import uuid

import pytest

from narrare.kb.scope_service import KBScopeService
from narrare_core.shared.errors import ConflictError

from ._scope_service_helpers import FakeKBRepo


@pytest.fixture
def fake_repo() -> FakeKBRepo:
    return FakeKBRepo()


@pytest.fixture
def service(fake_repo: FakeKBRepo) -> KBScopeService:
    return KBScopeService(fake_repo)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# promote_to_canon
# ---------------------------------------------------------------------------


class TestPromoteToCanon:
    async def test_delegates_to_repository_with_args(
        self, service: KBScopeService, fake_repo: FakeKBRepo
    ) -> None:
        """Promote forwards novel_id/entry_id to the repo and returns its result."""
        from ._scope_service_helpers import make_series_entry

        novel_id = uuid.uuid4()
        entry_id = uuid.uuid4()
        expected = make_series_entry(series_id=uuid.uuid4())
        fake_repo.set_promote_result(expected)

        result = await service.promote_to_canon(novel_id, entry_id)

        assert result is expected
        assert fake_repo.promote_calls == [(novel_id, entry_id)]

    async def test_translates_value_error_to_conflict(
        self, service: KBScopeService, fake_repo: FakeKBRepo
    ) -> None:
        """A repository invariant violation surfaces as a ConflictError (→ HTTP 409)."""
        fake_repo.set_promote_error(ValueError("Entry not found or not overlay"))

        with pytest.raises(ConflictError, match="not overlay"):
            await service.promote_to_canon(uuid.uuid4(), uuid.uuid4())

    async def test_preserves_cause(self, service: KBScopeService, fake_repo: FakeKBRepo) -> None:
        """The original ValueError is chained for diagnostics (RULE-11)."""
        original = ValueError("Novel not in a series")
        fake_repo.set_promote_error(original)

        with pytest.raises(ConflictError) as exc_info:
            await service.promote_to_canon(uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.__cause__ is original


# ---------------------------------------------------------------------------
# demote_to_overlay
# ---------------------------------------------------------------------------


class TestDemoteToOverlay:
    async def test_delegates_to_repository_with_args(
        self, service: KBScopeService, fake_repo: FakeKBRepo
    ) -> None:
        """Demote forwards series_id/entry_id/target_novel_id and returns its result."""
        from ._scope_service_helpers import make_novel_entry

        series_id = uuid.uuid4()
        entry_id = uuid.uuid4()
        target_novel_id = uuid.uuid4()
        expected = make_novel_entry(novel_id=target_novel_id)
        fake_repo.set_demote_result(expected)

        result = await service.demote_to_overlay(series_id, entry_id, target_novel_id)

        assert result is expected
        assert fake_repo.demote_calls == [(series_id, entry_id, target_novel_id)]

    async def test_translates_value_error_to_conflict(
        self, service: KBScopeService, fake_repo: FakeKBRepo
    ) -> None:
        """A repository invariant violation surfaces as a ConflictError (→ HTTP 409)."""
        fake_repo.set_demote_error(ValueError("Entry not canon of series"))

        with pytest.raises(ConflictError, match="not canon"):
            await service.demote_to_overlay(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

    async def test_preserves_cause(self, service: KBScopeService, fake_repo: FakeKBRepo) -> None:
        """The original ValueError is chained for diagnostics (RULE-11)."""
        original = ValueError("not canon")
        fake_repo.set_demote_error(original)

        with pytest.raises(ConflictError) as exc_info:
            await service.demote_to_overlay(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.__cause__ is original
