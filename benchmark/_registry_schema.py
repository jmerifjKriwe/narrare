"""Entry schema of the capability registry — type aliases + dataclasses.

RULE-04 split (plan Task 13 fix, ADR-085 P6): the literal entry tables
instantiate ``CapabilitySpec``/``EndpointSpec`` at import time, so the
schema must be importable WITHOUT pulling the tables — a table module
importing this one, and the registry importing the tables, stays
acyclic. Data only, no logic: the assembly, ``DRIVERS_PENDING``, and
``UNAVAILABLE_SURFACES`` remain in ``benchmark.capabilities_registry``;
the public lookup surface remains ``benchmark.capabilities``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Direction = Literal["in", "out", "check"]
InvocationShape = Literal["rest", "sse", "poll"]
SseFlavor = Literal["A", "B"]


@dataclass(frozen=True)
class EndpointSpec:
    """One method-pinned endpoint (path template relative to ``/api/v1``)."""

    method: str
    path: str


@dataclass(frozen=True)
class CapabilitySpec:
    """One inventoried capability: identity, shape, endpoints, output, driver."""

    cap_id: str
    direction: Direction
    shape: InvocationShape
    sse_flavor: SseFlavor | None
    driver_name: str
    output_schema: str
    endpoints: tuple[EndpointSpec, ...]
    unavailable_reason: str | None = None
    llm_backed: bool | None = None
    requires: tuple[str, ...] = ()


@dataclass(frozen=True)
class UnavailableSurface:
    """An inventoried capability whose routes 404 at runtime (unmounted)."""

    label: str
    direction: Direction
    endpoints: tuple[EndpointSpec, ...]
    reason: str
