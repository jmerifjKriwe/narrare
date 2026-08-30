"""Capability driver mapping — the cap_id -> driver class registry.

``benchmark.capabilities`` holds the 26-entry inventory table; THIS
module owns which driver CLASS serves each entry (plan Task 7). Entries
start mapped to :class:`PlaceholderDriver`, whose ``invoke`` raises
``NotImplementedError``; plan Tasks 8-10 replace entries direction by
direction (Task 8 wired the whole ``in`` direction, Task 9 the whole
``out`` direction), so an un-replaced capability fails loudly and
honestly at invocation time, never silently no-ops.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from benchmark.capabilities import CAPABILITIES
from benchmark.drivers.in_direction import IN_DIRECTION_DRIVERS
from benchmark.drivers.out_direction import OUT_DIRECTION_DRIVERS

if TYPE_CHECKING:
    from benchmark.drivers.base import CapabilityContext, CapabilityDriver, CapabilityResult

__all__ = [
    "DRIVERS",
    "IN_DIRECTION_DRIVERS",
    "OUT_DIRECTION_DRIVERS",
    "DriverNotRegisteredError",
    "PlaceholderDriver",
    "driver_for",
]


class DriverNotRegisteredError(LookupError):
    """No driver class is mapped for a capability id."""


class PlaceholderDriver:
    """Stand-in for capabilities whose drivers land in plan Tasks 8-10."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        raise NotImplementedError(
            "capability drivers are implemented in plan Tasks 8-10; "
            "this registry entry is still the placeholder"
        )


DRIVERS: Final[dict[str, type[CapabilityDriver]]] = {
    **{spec.cap_id: PlaceholderDriver for spec in CAPABILITIES},
    **IN_DIRECTION_DRIVERS,
    **OUT_DIRECTION_DRIVERS,
}
"""cap_id -> driver class; Task 10 replaces the remaining placeholders."""


def driver_for(cap_id: str) -> type[CapabilityDriver]:
    """Resolve the driver class for ``cap_id``; unknown ids raise."""
    driver = DRIVERS.get(cap_id)
    if driver is None:
        raise DriverNotRegisteredError(
            f"no driver registered for {cap_id!r} (registry holds {len(CAPABILITIES)} entries)"
        )
    return driver
