"""Budget config cache invalidation slot — write-through seam (ADR-094).

Module-state slot in the ADR-093 decision-2 service-locator shape (same
pattern as ``narrare_core.llm.budget``): the settings service calls
:func:`invalidate_budget_config` after every successful budget-config
write (``monthly_budget_usd`` / ``budget_mode`` via ``PATCH /ai``), and
the DB-backed ``BudgetGuard`` implementation (Task A5,
``narrare.analytics.budget_guard``) registers its cache-drop callback
once at startup via :func:`set_budget_config_invalidator`.

Unset slot ⇒ no-op: without an armed guard there is no cache to stale,
so settings writes, tests, and CLI pay zero overhead. This keeps the
A5 guard pluggable without touching the settings files again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID


class BudgetConfigInvalidator(Protocol):
    """Drops a user's cached budget config from the guard.

    The guard (Task A5) registers its in-memory cache eviction here.
    Synchronous by design: a config-cache drop is a dict removal, not
    I/O. The parameter is position-only — this is a callback seam,
    invoked positionally (plain functions and ``list.append``-style
    builtins both conform). Exceptions propagate unchanged — swallowing
    here could leave a stale cache that silently mis-enforces the
    budget (RULE-11).
    """

    def __call__(self, user_id: UUID, /) -> None: ...


_invalidator: BudgetConfigInvalidator | None = None


def set_budget_config_invalidator(fn: BudgetConfigInvalidator | None) -> None:
    """Register (or clear with ``None``) the invalidation callback."""
    global _invalidator
    _invalidator = fn


def invalidate_budget_config(user_id: UUID) -> None:
    """Write-through invalidation after a budget-config write.

    No-op while no invalidator is registered; otherwise delegates with
    the owning ``user_id``. Exceptions propagate (see Protocol docstring).
    """
    if _invalidator is None:
        return
    _invalidator(user_id)
