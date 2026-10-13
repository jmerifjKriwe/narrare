"""Analysis-surface catalog entries (grown in the next task)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.e2e.mocks.catalog import RouteSpec

SPECS: tuple[RouteSpec, ...] = ()


def validate() -> None:
    """Spec §10 ratchet — populated with the entries."""
