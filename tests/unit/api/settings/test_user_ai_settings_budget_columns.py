"""Unit tests for ``UserAiSettings`` budget columns (STATS-002, ADR-094).

Binding spec A-5: ``monthly_budget_usd NUMERIC(10,2) NULL`` (NULL = no
budget) and ``budget_mode TEXT NOT NULL DEFAULT 'warn'`` restricted to
``('warn', 'block')`` by a named CHECK — house precedent
``ck_notes_note_type`` (model ``__table_args__`` + migration 0041).

These are table-metadata assertions (no DB): the DB-level behaviour —
server_default backfill, CHECK enforcement, round-trip — is pinned by
``tests/integration/test_migration_0044_round_trip.py`` (mirrors the
0043 pattern).
"""

from __future__ import annotations

from decimal import Decimal
from typing import get_args, get_origin, get_type_hints

from sqlalchemy import CheckConstraint, Numeric, Table, Text
from sqlalchemy.orm import Mapped

from narrare.settings.models import UserAiSettings

_BUDGET_MODE_CHECK_NAME = "ck_user_ai_settings_budget_mode"


def _declared_type(field: str) -> object:
    """Resolve a mapped attribute's declared Python type (unwrap Mapped)."""
    hint = get_type_hints(UserAiSettings)[field]
    if get_origin(hint) is Mapped:
        (inner,) = get_args(hint)
        hint = inner
    return hint


class TestMonthlyBudgetUsdColumn:
    """A-5: monthly_budget_usd NUMERIC(10,2) NULL — NULL = no budget."""

    def test_monthly_budget_usd_is_numeric_10_2(self) -> None:
        col = UserAiSettings.__table__.columns["monthly_budget_usd"]
        assert isinstance(col.type, Numeric)
        assert col.type.precision == 10
        assert col.type.scale == 2

    def test_monthly_budget_usd_is_nullable(self) -> None:
        col = UserAiSettings.__table__.columns["monthly_budget_usd"]
        assert col.nullable is True, "NULL = no budget (gate no-op)"

    def test_monthly_budget_usd_has_no_server_default(self) -> None:
        col = UserAiSettings.__table__.columns["monthly_budget_usd"]
        assert col.server_default is None, "existing rows must stay NULL (no budget)"

    def test_monthly_budget_usd_is_optional_decimal(self) -> None:
        assert _declared_type("monthly_budget_usd") == Decimal | None


class TestBudgetModeColumn:
    """A-5: budget_mode TEXT NOT NULL DEFAULT 'warn'."""

    def test_budget_mode_is_required_text(self) -> None:
        col = UserAiSettings.__table__.columns["budget_mode"]
        assert isinstance(col.type, Text)
        assert col.nullable is False

    def test_budget_mode_defaults_to_warn_on_model_and_server(self) -> None:
        col = UserAiSettings.__table__.columns["budget_mode"]
        assert col.default is not None and col.default.arg == "warn"
        assert col.server_default is not None and col.server_default.arg == "warn"

    def test_budget_mode_is_declared_str(self) -> None:
        assert _declared_type("budget_mode") is str


class TestBudgetModeCheckConstraint:
    """CHECK in {'warn','block'} — model mirrors migration 0044 (RULE-14)."""

    def test_check_constraint_present_with_house_name(self) -> None:
        table = UserAiSettings.__table__
        assert isinstance(table, Table)  # SQLAlchemy types __table__ as FromClause
        checks = [c for c in table.constraints if c.name == _BUDGET_MODE_CHECK_NAME]
        assert len(checks) == 1, f"expected exactly one {_BUDGET_MODE_CHECK_NAME}"

    def test_check_constraint_pins_warn_and_block(self) -> None:
        table = UserAiSettings.__table__
        assert isinstance(table, Table)  # SQLAlchemy types __table__ as FromClause
        (check,) = (
            c
            for c in table.constraints
            if isinstance(c, CheckConstraint) and c.name == _BUDGET_MODE_CHECK_NAME
        )
        sqltext = str(check.sqltext)
        assert "budget_mode" in sqltext
        assert "'warn'" in sqltext
        assert "'block'" in sqltext
