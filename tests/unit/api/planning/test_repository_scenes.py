"""Unit tests for the real scene plan repository (PLAN-001 T3).

The real ``ScenePlanRepository`` runs against ``FakeDbSession`` (pattern:
``tests/unit/api/analytics/test_usage_record_repository.py``) to pin query
wiring (position ordering, chapters join, novel scope bind) and the
``bulk_replace`` diff semantics (delete-absent / insert-new / update-existing /
renumber 1..N in payload order, one flush + refresh).

The ``FakeScenePlanRepository`` fidelity half lives in
``test_fake_scene_plan_repository.py`` (pattern: ``test_planning_repository.py``)
— the T4 aggregate service tests depend on that fake being faithful (RULE-23).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy.sql.elements import UnaryExpression

from narrare.planning.contracts import ScenePlanRepositoryProtocol
from narrare.planning.repository_scenes import ScenePlanRepository
from tests.fakes.fake_db_session import FakeDbSession, FakeResult
from tests.fakes.fake_scene_repo import FakeScenePlanRepository
from tests.unit.api.planning._scene_repo_test_helpers import _scene

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.planning.models import ScenePlan

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repo(session: FakeDbSession) -> ScenePlanRepository:
    return ScenePlanRepository(cast("AsyncSession", session))


async def _bulk_replace(
    existing: list[ScenePlan],
    rows: list[ScenePlan],
    chapter_id: uuid.UUID | None = None,
) -> tuple[FakeDbSession, list[ScenePlan]]:
    """Run real-repo bulk_replace with ``existing`` as the queued DB rows."""
    session = FakeDbSession([FakeResult(scalars=existing)])
    result = await _repo(session).bulk_replace(chapter_id or uuid.uuid4(), rows)
    return session, result


def _order_columns(stmt: Any) -> list[tuple[str, str]]:
    """(table, column) of each ORDER BY clause — ordering-wiring pin.

    Implicit-ASC clauses are stored as bare columns; only explicit
    ``asc()``/``desc()`` produce ``UnaryExpression`` wrappers.
    """
    columns = []
    for clause in stmt._order_by_clauses:
        column = clause.element if isinstance(clause, UnaryExpression) else clause
        columns.append((column.table.name, column.name))
    return columns


def _order_directions(stmt: Any) -> list[str]:
    """Operator name (asc_op/desc_op) of each ORDER BY clause."""
    directions: list[str] = []
    for clause in stmt._order_by_clauses:
        if isinstance(clause, UnaryExpression) and clause.modifier is not None:
            directions.append(clause.modifier.__name__)
        else:
            directions.append("asc_op")
    return directions


# ---------------------------------------------------------------------------
# Real repository — query wiring (FakeDbSession)
# ---------------------------------------------------------------------------


class TestListByChapterWiring:
    async def test_returns_rows_preserving_db_order(self) -> None:
        rows = [_scene(), _scene(), _scene()]
        session = FakeDbSession([FakeResult(scalars=rows)])

        result = await _repo(session).list_by_chapter(uuid.uuid4())

        assert result == rows

    async def test_binds_chapter_id_exclusively(self) -> None:
        chapter_id = uuid.uuid4()
        session = FakeDbSession([FakeResult(scalars=[])])

        await _repo(session).list_by_chapter(chapter_id)

        params = session.statements[0].compile().params
        assert list(params.values()) == [chapter_id]

    async def test_orders_by_scene_position_ascending(self) -> None:
        session = FakeDbSession([FakeResult(scalars=[])])

        await _repo(session).list_by_chapter(uuid.uuid4())

        stmt = session.statements[0]
        assert _order_columns(stmt) == [("scene_plans", "position")]
        assert _order_directions(stmt) == ["asc_op"]


class TestListByNovelWiring:
    async def test_joins_chapters_and_orders_by_chapter_then_scene(self) -> None:
        session = FakeDbSession([FakeResult(scalars=[])])

        await _repo(session).list_by_novel(uuid.uuid4())

        stmt = session.statements[0]
        assert "JOIN chapters" in str(stmt)
        assert _order_columns(stmt) == [("chapters", "position"), ("scene_plans", "position")]
        assert _order_directions(stmt) == ["asc_op", "asc_op"]

    async def test_scopes_by_novel_id_exclusively(self) -> None:
        novel_id = uuid.uuid4()
        session = FakeDbSession([FakeResult(scalars=[])])

        await _repo(session).list_by_novel(novel_id)

        params = session.statements[0].compile().params
        assert list(params.values()) == [novel_id]


class TestGet:
    async def test_get_returns_scene_when_found(self) -> None:
        scene = _scene()
        session = FakeDbSession([FakeResult(value=scene)])

        result = await _repo(session).get(scene.id)

        assert result is scene

    async def test_get_returns_none_when_missing(self) -> None:
        session = FakeDbSession()

        result = await _repo(session).get(uuid.uuid4())

        assert result is None


# ---------------------------------------------------------------------------
# Real repository — bulk_replace diff semantics
# ---------------------------------------------------------------------------


class TestBulkReplaceDiff:
    async def test_deletes_rows_absent_from_payload(self) -> None:
        cid = uuid.uuid4()
        kept = _scene(chapter_id=cid, position=1)
        dropped = _scene(chapter_id=cid, position=2)
        replacement = _scene(id=kept.id, chapter_id=cid, position=1)

        session, _ = await _bulk_replace([kept, dropped], [replacement], chapter_id=cid)

        assert session.deleted == [dropped]

    async def test_foreign_chapter_id_row_takes_insert_path_pk_collision(self) -> None:
        # Real-repo equivalent of the fake's foreign-id IntegrityError: the id
        # is absent from this chapter's rows → treated as INSERT → at a real
        # DB this INSERT hits scene_plans_pkey (held by the other chapter).
        cid = uuid.uuid4()
        foreign = _scene(position=1)  # id stored under a DIFFERENT chapter

        session, _ = await _bulk_replace([], [foreign], chapter_id=cid)

        assert session.added == [foreign]

    async def test_inserts_new_rows_renumbered_in_payload_order(self) -> None:
        cid = uuid.uuid4()
        existing = _scene(chapter_id=cid, position=1)
        replacement = _scene(id=existing.id, chapter_id=cid, title="Updated")
        fresh = _scene(chapter_id=cid)

        session, result = await _bulk_replace([existing], [replacement, fresh], chapter_id=cid)

        assert session.added == [fresh]
        assert fresh.position == 2
        assert fresh.chapter_id == cid
        assert [row.id for row in result] == [existing.id, fresh.id]

    async def test_updates_existing_row_fields_from_payload(self) -> None:
        cid = uuid.uuid4()
        existing = _scene(chapter_id=cid, position=1, title="Old", status="planned")
        detached = _scene(
            id=existing.id,
            chapter_id=cid,
            title="New",
            status="complete",
            purpose="Why it matters",
            beats=["b1"],
            present_characters=[{"name": "Ana", "goal": "warn the guard"}],
        )

        _, result = await _bulk_replace([existing], [detached], chapter_id=cid)

        assert result[0] is existing  # persisted instance returned, not detached
        assert existing.title == "New"
        assert existing.status == "complete"
        assert existing.purpose == "Why it matters"
        assert existing.beats == ["b1"]
        assert existing.present_characters == [{"name": "Ana", "goal": "warn the guard"}]

    async def test_renumbers_positions_in_payload_order(self) -> None:
        cid = uuid.uuid4()
        first = _scene(chapter_id=cid, position=1)
        second = _scene(chapter_id=cid, position=2)
        rows = [
            _scene(id=second.id, chapter_id=cid),
            _scene(id=first.id, chapter_id=cid),
        ]

        _, result = await _bulk_replace([first, second], rows, chapter_id=cid)

        assert [row.id for row in result] == [second.id, first.id]
        assert second.position == 1
        assert first.position == 2

    async def test_forces_chapter_id_and_renumbers_persisted_row(self) -> None:
        cid = uuid.uuid4()
        existing = _scene(chapter_id=cid, position=7)
        detached = _scene(id=existing.id, chapter_id=cid, position=42)

        _, result = await _bulk_replace([existing], [detached], chapter_id=cid)

        assert existing.position == 1
        assert existing.chapter_id == cid
        assert result[0] is existing

    async def test_flushes_once_and_refreshes_result_rows(self) -> None:
        cid = uuid.uuid4()
        existing = _scene(chapter_id=cid, position=1)
        fresh = _scene(chapter_id=cid, position=2)

        session, result = await _bulk_replace([existing], [existing, fresh], chapter_id=cid)

        assert session.flush_count == 1
        assert session.refreshed == result

    async def test_empty_payload_deletes_everything(self) -> None:
        cid = uuid.uuid4()
        first = _scene(chapter_id=cid, position=1)
        second = _scene(chapter_id=cid, position=2)

        session, result = await _bulk_replace([first, second], [], chapter_id=cid)

        assert session.deleted == [first, second]
        assert result == []
        assert session.flush_count == 1


# ---------------------------------------------------------------------------
# Protocol conformance (RULE-03)
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    def test_real_repository_satisfies_protocol(self) -> None:
        assert isinstance(_repo(FakeDbSession()), ScenePlanRepositoryProtocol)

    def test_fake_satisfies_protocol(self) -> None:
        assert isinstance(FakeScenePlanRepository(), ScenePlanRepositoryProtocol)
