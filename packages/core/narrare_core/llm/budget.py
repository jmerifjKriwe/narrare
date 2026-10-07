"""Budget guard slot — the pre-call spend gate seam (ADR-094).

Core-pure module-state slot in the exact ADR-093 decision-2 service-locator
shape (same pattern as the usage-event sink in ``usage_events.py``): the API
registers its DB-backed ``BudgetGuard`` once at app startup (lifespan);
``ModelRegistry.get_model()`` calls :func:`check_budget` before any provider
work. Unset guard or missing user attribution (``usage_user_id`` is None)
⇒ no-op — tests, CLI, and Core-only usage pay zero overhead and can never
false-positive a block.

Deliberately NOT a registry — a single slot (ADR-094 decision 2, outside
ADR-092 decision 6's fourth-registry trigger).

Why this seam may raise (the one controlled inversion of ADR-093 D1's
never-raise philosophy): a budget *block* stops a run **before** any spend
occurs. The inversion is bounded to this seam and one exception
(``BudgetExceededError``); the sink seam's never-raise contract is untouched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID


class BudgetGuard(Protocol):
    """Pre-call budget check (ADR-094 decision 2).

    The API-side implementation (running month total vs. cached budget
    config) lives in the API layer — Core only owns the contract and the
    slot. ``check`` returns when the call may proceed and raises
    :class:`~narrare_core.shared.errors.BudgetExceededError` when the
    user's month spend must be stopped (block mode at/above budget).
    """

    def check(self, user_id: UUID) -> None: ...


_guard: BudgetGuard | None = None


def set_budget_guard(guard: BudgetGuard | None) -> None:
    """Register (or clear with ``None``) the guard. Clearing disables gating."""
    global _guard
    _guard = guard


def get_budget_guard() -> BudgetGuard | None:
    """Return the registered guard, or ``None`` when no guard is armed."""
    return _guard


def check_budget(user_id: UUID | None) -> None:
    """Gate entry point — no-op unless a guard is armed AND *user_id* is set.

    Exceptions from the guard propagate unchanged: this is ADR-094's
    controlled inversion of ADR-093 D1, confined to this seam (do NOT wrap
    or swallow here — the gate must stop the run before spend occurs).
    """
    if user_id is None or _guard is None:
        return
    _guard.check(user_id)
