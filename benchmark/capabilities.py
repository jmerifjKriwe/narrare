"""Public import surface of the capability registry.

``benchmark.capabilities_registry`` owns the entry schema, the type
aliases, and the literal 26-entry table + ``UNAVAILABLE_SURFACES``. This
split exists because the ``output_schema`` additions pushed the combined
file to 416 lines, over the RULE-04 hard limit of 400; the table cannot
be separated from the dataclasses it instantiates at import time without
a circular import, so the schema travels with the data. This facade keeps
the public surface stable — ``benchmark.capabilities`` remains the import
name for every existing importer (tests, ``benchmark.drivers``) — and
hosts the ``capability()`` lookup with its ``UnknownCapabilityError``.
"""

from __future__ import annotations

from benchmark.capabilities_registry import (
    CAPABILITIES,
    UNAVAILABLE_SURFACES,
    CapabilitySpec,
    Direction,
    EndpointSpec,
    InvocationShape,
    SseFlavor,
    UnavailableSurface,
)

__all__ = [
    "CAPABILITIES",
    "UNAVAILABLE_SURFACES",
    "CapabilitySpec",
    "Direction",
    "EndpointSpec",
    "InvocationShape",
    "SseFlavor",
    "UnavailableSurface",
    "UnknownCapabilityError",
    "capability",
]


class UnknownCapabilityError(LookupError):
    """No registry entry exists for a capability id."""


def capability(cap_id: str) -> CapabilitySpec:
    """Look up one registry entry; unknown ids raise a precise error."""
    for spec in CAPABILITIES:
        if spec.cap_id == cap_id:
            return spec
    raise UnknownCapabilityError(
        f"unknown capability id {cap_id!r} (registry holds {len(CAPABILITIES)} entries)"
    )
