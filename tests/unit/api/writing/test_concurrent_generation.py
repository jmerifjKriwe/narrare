"""Regression tests for TOCTOU race in concurrent generation creation.

Finding: ``fnd_sig-feat-library-000e72e7f6-06b7_9562565477``

The ``validate_*`` / ``start_*`` methods previously used separate
``get_active_for_chapter`` (SELECT) and ``create`` (INSERT) calls.
Two concurrent requests for the same chapter could both read no active
row and both INSERT — violating the intended concurrency guard.

Fix: ``create_if_no_active`` uses ``SELECT ... FOR UPDATE`` to make
the check-then-insert atomic.  A partial unique index provides
database-level defence-in-depth.

These tests verify:
1. ``create_if_no_active`` raises ConflictError when an active row exists
2. ``create_if_no_active`` returns a UUID when no active row exists
3. Concurrent coroutines for the same chapter result in exactly one success
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.writing.models import GenerationRequest
from narrare.writing.repository import GenerationRepository
from narrare_core.shared.errors import ConflictError


def _make_mock_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock(spec=["scalar_one_or_none"])
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    session.flush = AsyncMock()
    session.add = MagicMock(spec=lambda *a, **kw: None)
    session.refresh = AsyncMock()
    return session


class TestCreateIfNoActive:
    async def test_raises_conflict_when_active_exists(self) -> None:
        session = _make_mock_session()
        active = MagicMock(spec=GenerationRequest)
        session.execute.return_value.scalar_one_or_none.return_value = active

        repo: GenerationRepository = GenerationRepository(session=session)

        with pytest.raises(ConflictError, match="already active"):
            await repo.create_if_no_active(
                chapter_id=uuid.uuid4(),
                novel_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                mode="full_draft",
            )

    async def test_creates_when_no_active(self) -> None:
        session = _make_mock_session()
        session.execute.return_value.scalar_one_or_none.return_value = None

        created_id = uuid.uuid4()

        async def fake_flush_and_refresh(entity: object) -> None:
            entity.id = created_id  # type: ignore[attr-defined]

        repo: GenerationRepository = GenerationRepository(session=session)
        repo._flush_and_refresh = AsyncMock(side_effect=fake_flush_and_refresh)

        result = await repo.create_if_no_active(
            chapter_id=uuid.uuid4(),
            novel_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            mode="extend",
        )

        assert result == created_id
        session.add.assert_called_once()

    async def test_uses_for_update_in_query(self) -> None:
        session = _make_mock_session()
        session.execute.return_value.scalar_one_or_none.return_value = None

        async def fake_flush_and_refresh(entity: object) -> None:
            entity.id = uuid.uuid4()  # type: ignore[attr-defined]

        repo: GenerationRepository = GenerationRepository(session=session)
        repo._flush_and_refresh = AsyncMock(side_effect=fake_flush_and_refresh)

        await repo.create_if_no_active(
            chapter_id=uuid.uuid4(),
            novel_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            mode="rewrite",
        )

        call_args = session.execute.call_args
        stmt = call_args[0][0]
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        sql_str = str(compiled).lower()
        assert "for update" in sql_str


class TestConcurrentGenerationRace:
    async def test_concurrent_calls_only_one_succeeds(self) -> None:
        """Simulate TOCTOU race: two coroutines, same chapter_id.

        First call locks the row (returns None from FOR UPDATE), creates.
        Second call sees the active row and raises ConflictError.
        """
        call_count = 0
        chapter_id = uuid.uuid4()

        session = AsyncMock(spec=AsyncSession)

        async def mock_execute(stmt: object) -> MagicMock:
            nonlocal call_count
            call_count += 1

            result = MagicMock(spec=["scalar_one_or_none"])

            if call_count == 1:
                result.scalar_one_or_none.return_value = None
            else:
                active = MagicMock(spec=GenerationRequest)
                result.scalar_one_or_none.return_value = active

            return result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.flush = AsyncMock()
        session.add = MagicMock(spec=lambda *a, **kw: None)

        async def fake_flush_and_refresh(entity: object) -> None:
            entity.id = uuid.uuid4()  # type: ignore[attr-defined]

        repo: GenerationRepository = GenerationRepository(session=session)
        repo._flush_and_refresh = AsyncMock(side_effect=fake_flush_and_refresh)

        results = await asyncio.gather(
            repo.create_if_no_active(
                chapter_id=chapter_id,
                novel_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                mode="full_draft",
            ),
            repo.create_if_no_active(
                chapter_id=chapter_id,
                novel_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                mode="full_draft",
            ),
            return_exceptions=True,
        )

        successes = [r for r in results if isinstance(r, uuid.UUID)]
        conflicts = [r for r in results if isinstance(r, ConflictError)]

        assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
        assert len(conflicts) == 1, f"Expected exactly 1 conflict, got {len(conflicts)}"
