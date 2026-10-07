# tests/unit/api/analytics/test_usage_record_repository_month_spend.py
"""Unit tests for ``UsageRecordRepository.month_spend_by_user`` (ADR-094 D5).

Budget-guard hydration query: per-user priced spend at/after a start
timestamp. Companion to ``test_usage_record_repository.py`` (insert /
aggregate / stream wiring); shares its fake-session fleet via
``_repository_fakes``. Pinned here: row mapping onto
``dict[UUID, Decimal]``, the COALESCE int-0 normalization, ALL-users
scoping (no user_id bind), the single open ``created_at >= start`` bound,
and the ``GROUP BY user_id`` + ``COALESCE(SUM(...))`` SQL shape.
Real-DB semantics are proven in
``tests/integration/test_usage_record_aggregation.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from tests.unit.api.analytics._repository_fakes import _AggSession, _make_repo


class TestUsageRecordRepositoryMonthSpend:
    async def test_maps_rows_onto_per_user_decimal_dict(self) -> None:
        """(user_id, SUM) rows → ``dict[UUID, Decimal]`` keyed by user."""
        user_a, user_b = uuid4(), uuid4()
        session = _AggSession([(user_a, Decimal("1.5")), (user_b, Decimal("0.25"))])
        repo = _make_repo(session)

        result = await repo.month_spend_by_user(datetime(2026, 1, 1, tzinfo=UTC))

        assert result == {user_a: Decimal("1.5"), user_b: Decimal("0.25")}

    async def test_int_zero_fallback_is_normalized_to_decimal(self) -> None:
        """COALESCE's int-0 fallback (all-unpriced user) becomes Decimal."""
        user_a = uuid4()
        session = _AggSession([(user_a, 0)])
        repo = _make_repo(session)

        result = await repo.month_spend_by_user(datetime(2026, 1, 1, tzinfo=UTC))

        assert result == {user_a: Decimal("0")}
        assert isinstance(result[user_a], Decimal)

    async def test_no_user_scoping_one_ge_bound_only(self) -> None:
        """Hydration reads ALL users (no user_id bind); single ``created_at >= start``.

        Upper bound is deliberately absent: the window is the open current
        UTC month (spec A-4) — every row at/after the month start counts.
        """
        session = _AggSession([])
        repo = _make_repo(session)
        start = datetime(2026, 3, 1, tzinfo=UTC)

        await repo.month_spend_by_user(start)

        params = session.statements[0].compile().params
        assert not [key for key in params if key.startswith("user_id")]
        whereclause = session.statements[0].whereclause
        # Single where() criterion → the clause list collapses to one
        # BinaryExpression (no .clauses) — normalize before asserting.
        criteria = whereclause.clauses if hasattr(whereclause, "clauses") else [whereclause]
        bounds = [(crit.operator.__name__, crit.right.value) for crit in criteria]
        assert bounds == [("ge", start)]

    async def test_groups_by_user_id_over_coalesced_cost_sum(self) -> None:
        """GROUP BY user_id; the cost column is COALESCE(SUM(cost_usd), 0)."""
        session = _AggSession([])
        repo = _make_repo(session)

        await repo.month_spend_by_user(datetime(2026, 1, 1, tzinfo=UTC))

        grouped = session.statements[0]._group_by_clauses
        assert [clause.name for clause in grouped] == ["user_id"]
        sql = str(session.statements[0].compile(compile_kwargs={"literal_binds": True}))
        assert "coalesce(sum(usage_records.cost_usd), 0)" in sql
