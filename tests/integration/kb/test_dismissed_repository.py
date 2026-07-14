"""Integration tests for DismissedFindingRepository — real PostgreSQL DB.

Tests the full dismiss → list → undismiss lifecycle, upsert idempotency,
and cross-novel isolation using a transaction-wrapped session.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from narrare.auth.models import User
from narrare.kb.dismissed_repository import DismissedFindingRepository
from narrare.novels.models import Novel

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


async def _create_novel(session: AsyncSession) -> UUID:
    """Insert a minimal Novel (with a User) to satisfy FK constraints."""
    from datetime import UTC, datetime

    user = User(
        id=uuid4(),
        email=f"test-{uuid4().hex[:12]}@example.com",
        hashed_password="not-a-real-hash",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    await session.flush()

    novel = Novel(
        id=uuid4(),
        user_id=user.id,
        title="Test Novel",
    )
    session.add(novel)
    await session.flush()
    return novel.id


@pytest.fixture
async def repo(db_session: AsyncSession) -> DismissedFindingRepository:
    return DismissedFindingRepository(db_session)


@pytest.fixture
async def novel_id(db_session: AsyncSession) -> UUID:
    """Create a novel and return its ID."""
    return await _create_novel(db_session)


@pytest.fixture
async def other_novel_id(db_session: AsyncSession) -> UUID:
    """Create a second novel for isolation tests."""
    return await _create_novel(db_session)


# ---------------------------------------------------------------------------
# Tests: dismiss + list
# ---------------------------------------------------------------------------


class TestDismissAndList:
    """Test DismissedFindingRepository.dismiss and list_dismissed."""

    async def test_dismiss_then_list_returns_fingerprint(
        self,
        repo: DismissedFindingRepository,
        novel_id: UUID,
    ) -> None:
        """A dismissed fingerprint appears in list_dismissed."""
        await repo.dismiss(novel_id, "fp-1")

        result = await repo.list_dismissed(novel_id)

        assert result == ["fp-1"]

    async def test_list_dismissed_empty_when_none(
        self,
        repo: DismissedFindingRepository,
        novel_id: UUID,
    ) -> None:
        """list_dismissed returns empty list for a novel with no dismissals."""
        result = await repo.list_dismissed(novel_id)

        assert result == []

    async def test_dismiss_multiple_returns_all(
        self,
        repo: DismissedFindingRepository,
        novel_id: UUID,
    ) -> None:
        """Multiple dismissed fingerprints all appear in list_dismissed."""
        await repo.dismiss(novel_id, "fp-a")
        await repo.dismiss(novel_id, "fp-b")
        await repo.dismiss(novel_id, "fp-c")

        result = await repo.list_dismissed(novel_id)

        assert set(result) == {"fp-a", "fp-b", "fp-c"}

    async def test_dismiss_is_idempotent_upsert(
        self,
        repo: DismissedFindingRepository,
        novel_id: UUID,
    ) -> None:
        """Dismissing the same fingerprint twice does not create a duplicate."""
        await repo.dismiss(novel_id, "fp-dup", reason="first")
        await repo.dismiss(novel_id, "fp-dup", reason="second")

        result = await repo.list_dismissed(novel_id)

        assert result.count("fp-dup") == 1


# ---------------------------------------------------------------------------
# Tests: undismiss
# ---------------------------------------------------------------------------


class TestUndismiss:
    """Test DismissedFindingRepository.undismiss."""

    async def test_undismiss_removes_fingerprint(
        self,
        repo: DismissedFindingRepository,
        novel_id: UUID,
    ) -> None:
        """Undismiss removes the fingerprint from the store."""
        await repo.dismiss(novel_id, "fp-1")
        await repo.dismiss(novel_id, "fp-2")

        deleted = await repo.undismiss(novel_id, "fp-1")

        assert deleted is True
        remaining = await repo.list_dismissed(novel_id)
        assert remaining == ["fp-2"]

    async def test_undismiss_nonexistent_returns_false(
        self,
        repo: DismissedFindingRepository,
        novel_id: UUID,
    ) -> None:
        """Undismiss of a non-existent fingerprint returns False."""
        deleted = await repo.undismiss(novel_id, "never-existed")

        assert deleted is False

    async def test_undismiss_all_then_list_empty(
        self,
        repo: DismissedFindingRepository,
        novel_id: UUID,
    ) -> None:
        """Undismissing all fingerprints leaves an empty list."""
        await repo.dismiss(novel_id, "fp-1")
        await repo.undismiss(novel_id, "fp-1")

        result = await repo.list_dismissed(novel_id)

        assert result == []


# ---------------------------------------------------------------------------
# Tests: cross-novel isolation
# ---------------------------------------------------------------------------


class TestCrossNovelIsolation:
    """Test that dismissals are isolated per novel."""

    async def test_dismiss_in_one_novel_does_not_appear_in_other(
        self,
        repo: DismissedFindingRepository,
        novel_id: UUID,
        other_novel_id: UUID,
    ) -> None:
        """A fingerprint dismissed in novel A does not appear in novel B."""
        await repo.dismiss(novel_id, "fp-shared")

        result_a = await repo.list_dismissed(novel_id)
        result_b = await repo.list_dismissed(other_novel_id)

        assert result_a == ["fp-shared"]
        assert result_b == []

    async def test_same_fingerprint_in_different_novels(
        self,
        repo: DismissedFindingRepository,
        novel_id: UUID,
        other_novel_id: UUID,
    ) -> None:
        """The same fingerprint can be dismissed independently in two novels."""
        await repo.dismiss(novel_id, "fp-same")
        await repo.dismiss(other_novel_id, "fp-same")

        assert await repo.list_dismissed(novel_id) == ["fp-same"]
        assert await repo.list_dismissed(other_novel_id) == ["fp-same"]

        # Undismiss in novel A only
        await repo.undismiss(novel_id, "fp-same")

        assert await repo.list_dismissed(novel_id) == []
        assert await repo.list_dismissed(other_novel_id) == ["fp-same"]


# ---------------------------------------------------------------------------
# Tests: full lifecycle
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """Test the complete dismiss → list → undismiss → list lifecycle."""

    async def test_dismiss_list_undismiss_redismiss_lifecycle(
        self,
        repo: DismissedFindingRepository,
        novel_id: UUID,
    ) -> None:
        """Full lifecycle: dismiss, verify, undismiss, verify, re-dismiss."""
        # 1. Dismiss
        await repo.dismiss(novel_id, "fp-life", reason="reviewed")
        assert await repo.list_dismissed(novel_id) == ["fp-life"]

        # 2. Undismiss
        assert await repo.undismiss(novel_id, "fp-life") is True
        assert await repo.list_dismissed(novel_id) == []

        # 3. Re-dismiss (upsert should still work)
        await repo.dismiss(novel_id, "fp-life", reason="changed mind")
        assert await repo.list_dismissed(novel_id) == ["fp-life"]


# ---------------------------------------------------------------------------
# Tests: fingerprint format (matches frontend issueKey)
# ---------------------------------------------------------------------------


class TestFingerprintFormat:
    """Test that real-world fingerprints (description::entities) work."""

    async def test_fingerprint_with_colons_and_commas(
        self,
        repo: DismissedFindingRepository,
        novel_id: UUID,
    ) -> None:
        """Fingerprints with :: and commas (frontend issueKey format) persist."""
        fingerprint = "Ages conflict between characters::Alice Müller,Bob Smith"

        await repo.dismiss(novel_id, fingerprint)

        result = await repo.list_dismissed(novel_id)
        assert fingerprint in result
