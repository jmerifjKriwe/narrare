"""Capability driver mapping — the cap_id -> driver class registry.

``benchmark.capabilities`` holds the 26-entry inventory table; THIS
module owns which driver CLASS serves each entry (plan Task 7). Plan
Tasks 8-10 implemented the drivers direction by direction (Task 8 the
whole ``in`` direction, Task 9 the whole ``out`` direction, Task 10 the
whole ``check`` direction) — the registry is COMPLETE: every entry maps
to a real driver class (completion pin in ``test_capabilities.py``;
the ``PlaceholderDriver`` stand-in was removed with Task 10). An id
missing from the map (a future registry addition without a driver)
surfaces as a ``KeyError``/``DriverNotRegisteredError`` — loud, never a
silent no-op.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from benchmark.capabilities import CAPABILITIES
from benchmark.drivers.check_direction import CHECK_DIRECTION_DRIVERS
from benchmark.drivers.in_direction import IN_DIRECTION_DRIVERS
from benchmark.drivers.out_direction import OUT_DIRECTION_DRIVERS

if TYPE_CHECKING:
    from benchmark.drivers.base import CapabilityDriver

__all__ = [
    "CHECK_DIRECTION_DRIVERS",
    "DRIVERS",
    "IN_DIRECTION_DRIVERS",
    "OUT_DIRECTION_DRIVERS",
    "DriverNotRegisteredError",
    "driver_for",
]


class DriverNotRegisteredError(LookupError):
    """No driver class is mapped for a capability id."""


DRIVERS: Final[dict[str, type[CapabilityDriver]]] = {
    **IN_DIRECTION_DRIVERS,
    **OUT_DIRECTION_DRIVERS,
    **CHECK_DIRECTION_DRIVERS,
}
"""cap_id → driver class — ALL 26 registry entries (Task 10 completion)."""


def driver_for(cap_id: str) -> type[CapabilityDriver]:
    """Resolve the driver class for ``cap_id``; unknown ids raise."""
    driver = DRIVERS.get(cap_id)
    if driver is None:
        raise DriverNotRegisteredError(
            f"no driver registered for {cap_id!r} (registry holds {len(CAPABILITIES)} entries)"
        )
    return driver
