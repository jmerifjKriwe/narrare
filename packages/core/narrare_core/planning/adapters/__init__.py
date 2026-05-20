"""Structure adapters — registry and convenience imports.

Importing this module triggers auto-registration of all built-in adapters
(three_act, five_act, heros_journey, save_the_cat, seven_point).
"""

from __future__ import annotations

from narrare_core.planning.adapters import (
    five_act as _five_act,
)
from narrare_core.planning.adapters import (
    heros_journey as _heros_journey,
)
from narrare_core.planning.adapters import (
    save_the_cat as _save_the_cat,
)
from narrare_core.planning.adapters import (
    seven_point as _seven_point,
)
from narrare_core.planning.adapters import (
    three_act as _three_act,
)
from narrare_core.planning.adapters.base import (
    BeatDef,
    StageDef,
    StructureAdapter,
    StructureAdapterRegistry,
)

# Module-level registry singleton.
registry = StructureAdapterRegistry()

# Register all built-in adapters.
_five_act.register(registry)
_heros_journey.register(registry)
_save_the_cat.register(registry)
_seven_point.register(registry)
_three_act.register(registry)

__all__ = [
    "BeatDef",
    "StageDef",
    "StructureAdapter",
    "StructureAdapterRegistry",
    "registry",
]
