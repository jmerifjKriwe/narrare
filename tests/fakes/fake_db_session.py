"""Reusable fake ``AsyncSession`` for repository unit tests.

Repository classes (``BaseRepository`` subclasses) only touch a small
subset of ``sqlalchemy.ext.asyncio.AsyncSession``: ``execute``, ``add``,
``delete``, ``flush``, ``refresh`` and ``rollback``. This fake implements
exactly that surface so repository query wiring can be unit-tested without
a real database (the same approach as the inline ``_UpdateSession`` /
``_IntegrityThenNoneSession`` fakes in ``tests/unit/api/settings``).

Usage::

    session = FakeDbSession()
    session.queue(FakeResult(value=novel))          # 1st execute() -> novel
    session.queue(FakeResult(scalars=[n1, n2]))     # 2nd execute() -> [n1, n2]
    repo = NovelRepository(cast("AsyncSession", session))
    result = await repo.get(novel_id)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence


class _Scalars:
    """Mimics ``result.scalars()`` — iterable + ``.all()``."""

    def __init__(self, items: Sequence[Any]) -> None:
        self._items: list[Any] = list(items)

    def all(self) -> list[Any]:
        """Return all scalar values as a list."""
        return list(self._items)

    def __iter__(self) -> Any:
        return iter(self._items)


class FakeResult:
    """Fake query result supporting common SQLAlchemy result accessors.

    Args:
        value: Value returned by ``scalar_one_or_none`` / ``scalar`` / ``one``.
        scalars: Sequence returned by ``scalars().all()``.
    """

    def __init__(
        self,
        *,
        value: Any = None,
        scalars: Sequence[Any] | None = None,
    ) -> None:
        self._value = value
        self._scalars: list[Any] = list(scalars) if scalars is not None else []

    def scalar_one_or_none(self) -> Any:
        """Return the wrapped scalar value (or ``None``)."""
        return self._value

    def scalar(self) -> Any:
        """Return the wrapped scalar value."""
        return self._value

    def one(self) -> Any:
        """Return the wrapped row value."""
        return self._value

    def scalars(self) -> _Scalars:
        """Return a ``_Scalars`` view of the configured scalar list."""
        return _Scalars(self._scalars)


class FakeDbSession:
    """Fake async DB session for repository unit tests.

    Queue results via :meth:`queue` (or the ``results`` constructor arg);
    each ``execute()`` call pops the next queued result. When the queue is
    exhausted, ``execute()`` returns an empty :class:`FakeResult`.

    ``add``/``delete``/``flush``/``refresh`` calls are recorded for assertions.
    """

    def __init__(self, results: Sequence[Any] | None = None) -> None:
        self._results: list[Any] = list(results or [])
        self._idx: int = 0
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.flush_count: int = 0
        self.refreshed: list[Any] = []

    def queue(self, *results: Any) -> FakeDbSession:
        """Append results to the end of the execute() queue."""
        self._results.extend(results)
        return self

    def add(self, entity: Any) -> None:
        """Record an entity added to the session."""
        self.added.append(entity)

    async def delete(self, entity: Any) -> None:
        """Record an entity deleted from the session."""
        self.deleted.append(entity)

    async def flush(self) -> None:
        """Increment the flush counter."""
        self.flush_count += 1

    async def refresh(self, entity: Any) -> None:
        """Record a refreshed entity."""
        self.refreshed.append(entity)

    async def rollback(self) -> None:
        """No-op rollback."""

    async def execute(self, stmt: Any) -> FakeResult:
        """Return the next queued result (or an empty one if exhausted)."""
        if self._idx < len(self._results):
            queued = self._results[self._idx]
            self._idx += 1
            return queued if isinstance(queued, FakeResult) else FakeResult(value=queued)
        return FakeResult()
