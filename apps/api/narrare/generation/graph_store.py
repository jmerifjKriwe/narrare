"""PostgresGraphStateStore — implements GraphStateStore Protocol.

Stores WritingGraph checkpoints as JSONB rows in the ``graph_runs`` table.
``run_id`` is the unique lookup key; ``chapter_id`` is an optional FK.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PostgresGraphStateStore:
    """PostgreSQL-backed GraphStateStore.

    Serializes WritingState to/from JSONB for checkpointing.
    Uses ``run_id`` as the unique key (not the DB primary key).

    Usage::

        store = PostgresGraphStateStore(session)
        await store.save("run-uuid", state)
        state = await store.load("run-uuid")
        await store.delete("run-uuid")
    """

    def __init__(self, session: AsyncSession) -> None:
        """Inject the async DB session.

        Args:
            session: SQLAlchemy async session scoped to the request.
        """
        self._session = session

    async def save(
        self,
        run_id: str,
        state: object,
        *,
        chapter_id: str | None = None,
    ) -> None:
        """Upsert checkpoint data for a graph run.

        Args:
            run_id: Unique identifier for this graph run.
            state: The WritingState (or any serializable object) to persist.
            chapter_id: Optional chapter UUID to link this run to a chapter.
        """
        from sqlalchemy import select

        from narrare.generation.models import GraphRun

        result = await self._session.execute(select(GraphRun).where(GraphRun.run_id == run_id))
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.checkpoint_data = _serialize_state(state)
            existing.updated_at = datetime.now(UTC)
        else:
            kwargs: dict[str, Any] = {
                "run_id": run_id,
                "checkpoint_data": _serialize_state(state),
            }
            if chapter_id is not None:
                kwargs["chapter_id"] = uuid.UUID(chapter_id)
            model = GraphRun(**kwargs)
            self._session.add(model)

    async def load(self, run_id: str) -> object | None:
        """Load the latest checkpoint for a graph run.

        Args:
            run_id: The graph run identifier.

        Returns:
            A WritingState instance if found, or None.
        """
        from sqlalchemy import select

        from narrare.generation.models import GraphRun
        from narrare_core.agents.writing_graph_types import WritingState

        result = await self._session.execute(
            select(GraphRun)
            .where(GraphRun.run_id == run_id)
            .order_by(GraphRun.updated_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _deserialize_state(row.checkpoint_data, WritingState)

    async def delete(self, run_id: str) -> None:
        """Delete all checkpoints for a graph run.

        Args:
            run_id: The graph run to clean up.
        """
        from sqlalchemy import delete as sa_delete

        from narrare.generation.models import GraphRun

        await self._session.execute(sa_delete(GraphRun).where(GraphRun.run_id == run_id))


def _serialize_state(state: object) -> dict[str, Any]:
    """Convert a dataclass (e.g. WritingState) to a JSON-safe dict.

    Falls back to returning the object as-is if it is already a dict,
    or wrapping it in a ``{"data": ...}`` container as a last resort.
    """
    from dataclasses import asdict

    if isinstance(state, dict):
        return dict(state)  # type: ignore[return-value]  # reason: pgvector/SQLAlchemy dict→dict[str, Any] narrowing not inferrable
    if hasattr(state, "__dataclass_fields__"):
        return dict(asdict(state))  # type: ignore[return-value]  # reason: dataclass asdict() returns dict[str, Any], not inferable through dict()
    return {"data": str(state)}


def _deserialize_state(
    data: dict[str, Any],
    state_cls: type[Any],
) -> object | None:
    """Convert a JSON dict back into a dataclass (e.g. WritingState).

    Only fields that exist on the target dataclass are passed through,
    ignoring any extra keys that may have been added or removed.
    """
    if not data:
        return None
    if not hasattr(state_cls, "__dataclass_fields__"):
        return None
    try:
        fields: dict[str, Any] = state_cls.__dataclass_fields__  # pyright: ignore[reportAttributeAccessIssue]
        valid_fields = {f.name for f in fields.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return state_cls(**filtered)
    except TypeError, ValueError:
        return None
