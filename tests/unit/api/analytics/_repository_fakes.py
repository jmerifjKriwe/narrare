# tests/unit/api/analytics/_repository_fakes.py
"""Shared fake sessions for the ``UsageRecordRepository`` test modules.

Split out of ``test_usage_record_repository.py`` (RULE-04): the aggregate,
streaming, and budget-hydration query tests all ride the same fake-session
fleet. The shared ``FakeDbSession`` covers scalar results only; the
aggregate query reads whole rows via ``result.all()`` — the same reason the
KB repository tests carry local fakes (test_relationship_repository.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from narrare.analytics.repository import UsageRecordRepository

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession
    from tests.fakes.fake_db_session import FakeDbSession

    from narrare.analytics.models import UsageRecordRow


class _RowsResult:
    """Simulates a SQLAlchemy ``Result`` exposing ``all()`` (row tuples)."""

    def __init__(self, rows: Sequence[tuple[Any, ...]]) -> None:
        self._rows = list(rows)

    def all(self) -> list[tuple[Any, ...]]:
        return list(self._rows)


class _AggSession:
    """Minimal ``AsyncSession`` fake: preset aggregate rows + bookkeeping."""

    def __init__(self, rows: Sequence[tuple[Any, ...]]) -> None:
        self._rows = list(rows)
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> _RowsResult:
        self.statements.append(stmt)
        return _RowsResult(self._rows)


class _ScalarsResult:
    """Async-iterable scalar result — what ``stream_scalars()`` returns."""

    def __init__(self, rows: Sequence[UsageRecordRow]) -> None:
        self._iterator = iter(rows)

    def __aiter__(self) -> _ScalarsResult:
        return self

    async def __anext__(self) -> UsageRecordRow:
        try:
            return next(self._iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _StreamSession:
    """Minimal ``AsyncSession`` fake for the streaming query (``stream``).

    Companion to ``_AggSession``: the stream path iterates scalars lazily
    instead of materializing ``result.all()``.
    """

    def __init__(self, rows: Sequence[UsageRecordRow]) -> None:
        self._rows = list(rows)
        self.statements: list[Any] = []

    async def stream_scalars(self, stmt: Any) -> _ScalarsResult:
        self.statements.append(stmt)
        return _ScalarsResult(self._rows)


def _make_repo(session: FakeDbSession | _AggSession) -> UsageRecordRepository:
    """Wrap a fake session in a repository.

    ``cast`` (not ``# type: ignore[arg-type]``) is the RULE-23-sanctioned
    seam for passing a fake where an ``AsyncSession`` is declared.
    """
    return UsageRecordRepository(cast("AsyncSession", session))
