"""Budget invalidation slot (ADR-093 D2 pattern — A5 plugs in here).

RULE-04 split from ``test_budget_settings_api.py``: the slot contract
itself (registration, no-op default, no swallowing), independent of the
schema/service suites.
"""

from __future__ import annotations

import uuid

import pytest

from narrare.analytics.budget_invalidation import (
    invalidate_budget_config,
    set_budget_config_invalidator,
)


class TestBudgetInvalidationSlot:
    def test_invalidate_without_registration_is_noop(self) -> None:
        """No guard armed (unit tests, CLI, startup) ⇒ no-op, never raises."""
        set_budget_config_invalidator(None)
        invalidate_budget_config(uuid.uuid4())

    def test_registered_invalidator_receives_user_id(self) -> None:
        calls: list[uuid.UUID] = []
        set_budget_config_invalidator(calls.append)
        try:
            uid = uuid.uuid4()
            invalidate_budget_config(uid)
            assert calls == [uid]
        finally:
            set_budget_config_invalidator(None)

    def test_clearing_slot_restores_noop(self) -> None:
        calls: list[uuid.UUID] = []
        set_budget_config_invalidator(calls.append)
        set_budget_config_invalidator(None)
        invalidate_budget_config(uuid.uuid4())
        assert calls == []

    def test_invalidator_exception_propagates(self) -> None:
        """Mirror the core budget slot: no swallowing (RULE-11)."""

        def _boom(user_id: uuid.UUID) -> None:
            raise RuntimeError("cache drop failed")

        set_budget_config_invalidator(_boom)
        try:
            with pytest.raises(RuntimeError, match="cache drop failed"):
                invalidate_budget_config(uuid.uuid4())
        finally:
            set_budget_config_invalidator(None)
