"""Public import surface of the capability registry.

``benchmark.capabilities_registry`` assembles the literal 27-entry
table + ``UNAVAILABLE_SURFACES`` from the split entry modules
(``_registry_entries_in`` / ``_registry_entries_out``); the entry
schema and the type aliases live in ``benchmark._registry_schema``.
This facade keeps the public surface stable — ``benchmark.capabilities``
remains the import name for every existing importer (tests,
``benchmark.drivers``) — and hosts the ``capability()`` lookup with its
``UnknownCapabilityError``.
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
