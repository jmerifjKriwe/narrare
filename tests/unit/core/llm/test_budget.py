"""Budget guard slot — Protocol, slot round-trip, no-op and raise semantics.

ADR-094: unlike the usage-event sink seam (ADR-093 D1 — never raise), this
seam MAY raise: ``BudgetExceededError`` deliberately stops a run *before*
spend occurs. The tests pin the controlled inversion's exact boundaries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from narrare_core.llm.budget import (
    check_budget,
    get_budget_guard,
    set_budget_guard,
)
from narrare_core.shared.errors import BudgetExceededError, NarrareError

if TYPE_CHECKING:
    from collections.abc import Generator
    from uuid import UUID


class RecordingGuard:
    """Fake BudgetGuard that records every checked user."""

    def __init__(self) -> None:
        self.checked: list[UUID] = []

    def check(self, user_id: UUID) -> None:
        self.checked.append(user_id)


class OverBudgetGuard:
    """Fake BudgetGuard that always blocks — the A-2 raise case."""

    def check(self, user_id: UUID) -> None:
        raise BudgetExceededError(user_id, month_spend_usd=12.5, monthly_budget_usd=10.0)


class ExplodingGuard:
    """Fake BudgetGuard raising an unrelated error — must propagate too."""

    def check(self, user_id: UUID) -> None:
        raise RuntimeError("guard impl bug")


@pytest.fixture(autouse=True)
def _clean_budget_slot() -> Generator[None]:
    """Isolate the module-state slot around every test."""
    set_budget_guard(None)
    yield
    set_budget_guard(None)


def test_budget_guard_slot_set_then_unset_round_trips():
    guard = RecordingGuard()
    set_budget_guard(guard)
    assert get_budget_guard() is guard
    set_budget_guard(None)
    assert get_budget_guard() is None


def test_check_budget_with_unset_guard_is_noop():
    check_budget(uuid4())  # must not raise — tests/CLI pay zero overhead


def test_check_budget_with_none_user_is_noop_even_with_raising_guard():
    set_budget_guard(OverBudgetGuard())
    check_budget(None)  # None user fast-path precedes guard delegation


def test_check_budget_with_guard_set_delegates_with_exact_user():
    guard = RecordingGuard()
    set_budget_guard(guard)
    user = uuid4()
    check_budget(user)
    assert guard.checked == [user]


def test_check_budget_with_guard_and_user_propagates_budget_exceeded_error():
    set_budget_guard(OverBudgetGuard())
    user = uuid4()
    with pytest.raises(BudgetExceededError) as exc_info:
        check_budget(user)
    assert exc_info.value.user_id == user
    assert exc_info.value.month_spend_usd == 12.5
    assert exc_info.value.monthly_budget_usd == 10.0


def test_check_budget_propagates_unrelated_guard_errors_unchanged():
    set_budget_guard(ExplodingGuard())
    with pytest.raises(RuntimeError, match="guard impl bug"):
        check_budget(uuid4())


def test_budget_exceeded_error_follows_shared_error_conventions():
    user = uuid4()
    err = BudgetExceededError(user, month_spend_usd=12.5, monthly_budget_usd=10.0)
    assert isinstance(err, NarrareError)
    assert err.code == "BUDGET_EXCEEDED"
    # Message carries the money math (RULE-11 — honest, visible numbers).
    assert "12.50" in str(err)
    assert "10.00" in str(err)
    assert str(user) in str(err)
    # Base-class repr convention: ClassName('message', code='CODE')
    assert "BudgetExceededError(" in repr(err)
    assert "code='BUDGET_EXCEEDED'" in repr(err)
