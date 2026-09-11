"""Unit tests for DismissedFindingService — uses an in-memory fake repository.

Tests that the service correctly delegates to the repository and returns
the expected response shapes.  No DB, no HTTP (ADR-030 fake-based
testing).  The novel ownership gate is permissive here (IDOR S10): the
ownership matrix lives in ``tests/unit/api/kb/
test_relationship_dismissed_extraction_ownership.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest

from narrare.kb.consistency_contracts import (
    DismissedFindingsResponse,
    DismissFindingRequest,
)
from narrare.kb.dismissed_service import DismissedFindingService

if TYPE_CHECKING:
    from narrare.novels.contracts import NovelRepositoryProtocol

# Every test here acts as the novel's owner (permissive gate, IDOR S10).
_USER_ID = str(uuid4())


# ---------------------------------------------------------------------------
# Fake repository — real in-memory behaviour (ADR-030)
# ---------------------------------------------------------------------------


class FakeDismissedFindingRepository:
    """In-memory fake matching the DismissedFindingRepository protocol."""

    def __init__(self) -> None:
        # (novel_id, fingerprint) → reason
        self._store: dict[tuple[UUID, str], str | None] = {}

    async def dismiss(
        self,
        novel_id: UUID,
        fingerprint: str,
        reason: str | None = None,
    ) -> None:
        self._store[(novel_id, fingerprint)] = reason

    async def list_dismissed(self, novel_id: UUID) -> list[str]:
        return [fp for (nid, fp) in self._store if nid == novel_id]

    async def undismiss(self, novel_id: UUID, fingerprint: str) -> bool:
        key = (novel_id, fingerprint)
        existed = key in self._store
        self._store.pop(key, None)
        return existed

    # -- Test inspection helpers (not part of the protocol) --

    def get_reason(self, novel_id: UUID, fingerprint: str) -> str | None:
        """Return the stored reason for a dismissed fingerprint (test-only)."""
        return self._store.get((novel_id, fingerprint))


class _FakeNovelRepo:
    """Permissive novel gate — every caller owns every novel (IDOR S10).

    Kept local because this suite lives outside the ``tests/unit/api/kb``
    package that hosts the shared ``FakeNovelRepo``.
    """

    async def get_by_id(self, novel_id: UUID, user_id: UUID) -> object | None:
        return object()  # the gate only checks existence


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_repo() -> FakeDismissedFindingRepository:
    return FakeDismissedFindingRepository()


@pytest.fixture
def service(fake_repo: FakeDismissedFindingRepository) -> DismissedFindingService:
    return DismissedFindingService(
        fake_repo,
        cast("NovelRepositoryProtocol", _FakeNovelRepo()),
    )


@pytest.fixture
def novel_id() -> UUID:
    return uuid4()


# ---------------------------------------------------------------------------
# Tests: dismiss_finding
# ---------------------------------------------------------------------------


class TestDismissFinding:
    """Test DismissedFindingService.dismiss_finding."""

    async def test_dismiss_finding_returns_response_with_fingerprint(
        self,
        service: DismissedFindingService,
        fake_repo: FakeDismissedFindingRepository,
        novel_id: UUID,
    ) -> None:
        """Dismissing a finding returns a response containing its fingerprint."""
        request = DismissFindingRequest(
            fingerprint="Ages conflict::Alice,Bob",
            reason="Accepted as intentional",
        )

        result = await service.dismiss_finding(novel_id=novel_id, request=request, user_id=_USER_ID)

        assert isinstance(result, DismissedFindingsResponse)
        assert "Ages conflict::Alice,Bob" in result.fingerprints

    async def test_dismiss_finding_persists_to_repository(
        self,
        service: DismissedFindingService,
        fake_repo: FakeDismissedFindingRepository,
        novel_id: UUID,
    ) -> None:
        """Dismiss delegates to the repository so the fingerprint is stored."""
        request = DismissFindingRequest(fingerprint="fp-1")

        await service.dismiss_finding(novel_id=novel_id, request=request, user_id=_USER_ID)

        stored = await fake_repo.list_dismissed(novel_id)
        assert "fp-1" in stored

    async def test_dismiss_finding_without_reason_stores_none(
        self,
        service: DismissedFindingService,
        fake_repo: FakeDismissedFindingRepository,
        novel_id: UUID,
    ) -> None:
        """Dismiss without a reason persists successfully (reason defaults None)."""
        request = DismissFindingRequest(fingerprint="fp-no-reason")

        await service.dismiss_finding(novel_id=novel_id, request=request, user_id=_USER_ID)

        assert fake_repo.get_reason(novel_id, "fp-no-reason") is None

    async def test_dismiss_multiple_findings_returns_all(
        self,
        service: DismissedFindingService,
        novel_id: UUID,
    ) -> None:
        """Dismissing multiple findings returns all fingerprints in the list."""
        for fp in ("fp-a", "fp-b", "fp-c"):
            await service.dismiss_finding(
                novel_id=novel_id,
                request=DismissFindingRequest(fingerprint=fp),
                user_id=_USER_ID,
            )

        result = await service.dismiss_finding(
            novel_id=novel_id,
            request=DismissFindingRequest(fingerprint="fp-d"),
            user_id=_USER_ID,
        )

        assert set(result.fingerprints) == {"fp-a", "fp-b", "fp-c", "fp-d"}


# ---------------------------------------------------------------------------
# Tests: list_dismissed
# ---------------------------------------------------------------------------


class TestListDismissed:
    """Test DismissedFindingService.list_dismissed."""

    async def test_list_dismissed_returns_empty_when_none(
        self,
        service: DismissedFindingService,
        novel_id: UUID,
    ) -> None:
        """List returns empty fingerprints for a novel with no dismissals."""
        result = await service.list_dismissed(novel_id=novel_id, user_id=_USER_ID)

        assert result.fingerprints == []

    async def test_list_dismissed_returns_all_for_novel(
        self,
        service: DismissedFindingService,
        novel_id: UUID,
    ) -> None:
        """List returns all dismissed fingerprints for the given novel."""
        for fp in ("fp-1", "fp-2"):
            await service.dismiss_finding(
                novel_id=novel_id,
                request=DismissFindingRequest(fingerprint=fp),
                user_id=_USER_ID,
            )

        result = await service.list_dismissed(novel_id=novel_id, user_id=_USER_ID)

        assert set(result.fingerprints) == {"fp-1", "fp-2"}

    async def test_list_dismissed_isolates_by_novel(
        self,
        service: DismissedFindingService,
    ) -> None:
        """List only returns fingerprints for the specified novel."""
        novel_a = uuid4()
        novel_b = uuid4()

        await service.dismiss_finding(
            novel_id=novel_a,
            request=DismissFindingRequest(fingerprint="fp-a"),
            user_id=_USER_ID,
        )
        await service.dismiss_finding(
            novel_id=novel_b,
            request=DismissFindingRequest(fingerprint="fp-b"),
            user_id=_USER_ID,
        )

        result_a = await service.list_dismissed(novel_id=novel_a, user_id=_USER_ID)
        result_b = await service.list_dismissed(novel_id=novel_b, user_id=_USER_ID)

        assert result_a.fingerprints == ["fp-a"]
        assert result_b.fingerprints == ["fp-b"]


# ---------------------------------------------------------------------------
# Tests: undismiss_finding
# ---------------------------------------------------------------------------


class TestUndismissFinding:
    """Test DismissedFindingService.undismiss_finding."""

    async def test_undismiss_removes_fingerprint_from_list(
        self,
        service: DismissedFindingService,
        novel_id: UUID,
    ) -> None:
        """Un-dismissing removes the fingerprint from the returned list."""
        await service.dismiss_finding(
            novel_id=novel_id,
            request=DismissFindingRequest(fingerprint="fp-1"),
            user_id=_USER_ID,
        )
        await service.dismiss_finding(
            novel_id=novel_id,
            request=DismissFindingRequest(fingerprint="fp-2"),
            user_id=_USER_ID,
        )

        result = await service.undismiss_finding(
            novel_id=novel_id,
            fingerprint="fp-1",
            user_id=_USER_ID,
        )

        assert "fp-1" not in result.fingerprints
        assert "fp-2" in result.fingerprints

    async def test_undismiss_nonexistent_returns_empty_list(
        self,
        service: DismissedFindingService,
        novel_id: UUID,
    ) -> None:
        """Un-dismissing a non-existent fingerprint returns an empty list."""
        result = await service.undismiss_finding(
            novel_id=novel_id,
            fingerprint="never-dismissed",
            user_id=_USER_ID,
        )

        assert result.fingerprints == []

    async def test_undismiss_then_redismiss_appears_again(
        self,
        service: DismissedFindingService,
        novel_id: UUID,
    ) -> None:
        """A finding can be dismissed again after being un-dismissed."""
        fp = "fp-resurrect"

        await service.dismiss_finding(
            novel_id=novel_id,
            request=DismissFindingRequest(fingerprint=fp),
            user_id=_USER_ID,
        )
        await service.undismiss_finding(novel_id=novel_id, fingerprint=fp, user_id=_USER_ID)
        result = await service.dismiss_finding(
            novel_id=novel_id,
            request=DismissFindingRequest(fingerprint=fp),
            user_id=_USER_ID,
        )

        assert fp in result.fingerprints
