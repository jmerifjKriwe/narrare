"""CAP-IN-10 registry-consistency tests (plan Task 13, ADR-085 P6).

The entity-resolution capability enters the registry one task BEFORE its
driver (plan Task 14 lands ``ResolutionDriver``) — these tests pin the
entry's honesty contract: identity/direction per the ``01-in.md``
section, ``llm_backed`` truthfully recorded (the deterministic detection
core is what the metrics score, but the REVIEW band may call the
adjudicator — spec §8), the CAP-IN-01 ingest precondition, and
METHOD-PINNED endpoint parity with the LIVE app route table (mirrors
``tests/unit/api/kb/test_route_table.py``: the OpenAPI paths of
``create_app(test_mode=True)`` — mounted routes, not merely decorated
ones; the unmounted KB-009 merge router is the drift class this guards
against). The transitional driver gap is pinned to exactly CAP-IN-10 so
it cannot silently grow.
"""

from __future__ import annotations

from functools import lru_cache

from benchmark.capabilities import UnknownCapabilityError, capability
from benchmark.capabilities_registry import DRIVERS_PENDING, CapabilitySpec


@lru_cache(maxsize=1)
def _live_paths() -> dict[str, dict[str, object]]:
    """Mounted OpenAPI paths of the full app (no lifespan / DB needed)."""
    from narrare._app.main import create_app

    return create_app(test_mode=True).openapi()["paths"]


def _cap_in_10() -> CapabilitySpec:
    return capability("CAP-IN-10")


# ---------------------------------------------------------------------------
# Registry presence + identity
# ---------------------------------------------------------------------------


def test_cap_in_10_is_registered_in_direction_rest() -> None:
    spec = _cap_in_10()

    assert spec.cap_id == "CAP-IN-10"
    assert spec.direction == "in"
    assert spec.shape == "rest"
    assert spec.sse_flavor is None
    assert spec.unavailable_reason is None


def test_cap_in_10_records_llm_backed_true() -> None:
    """Honest declaration (spec §8): detection metrics score the
    deterministic core, but the uncertain band may call the adjudicator."""
    assert _cap_in_10().llm_backed is True


def test_cap_in_10_declares_the_ingest_precondition() -> None:
    assert _cap_in_10().requires == ("CAP-IN-01",)


# ---------------------------------------------------------------------------
# Endpoint parity with the LIVE route table (mounted, not merely decorated)
# ---------------------------------------------------------------------------


def test_cap_in_10_endpoints_are_mounted_with_pinned_methods() -> None:
    live = _live_paths()

    for endpoint in _cap_in_10().endpoints:
        mounted = f"/api/v1{endpoint.path}"
        assert mounted in live, f"CAP-IN-10 endpoint not mounted: {mounted}"
        assert endpoint.method in (m.upper() for m in live[mounted]), (
            f"{endpoint.method} not pinned on {mounted}"
        )


def test_registry_covers_exactly_the_live_resolution_surface() -> None:
    """No drift in either direction: every registry endpoint is mounted,
    every mounted /kb/resolution path is registered."""
    live = _live_paths()

    mounted = {path for path in live if "/kb/resolution/" in path}
    registered = {f"/api/v1{e.path}" for e in _cap_in_10().endpoints}

    assert mounted == registered


# ---------------------------------------------------------------------------
# Transitional driver gap — exactly CAP-IN-10 until plan Task 14
# ---------------------------------------------------------------------------


def test_cap_in_10_is_the_only_entry_waiting_for_its_driver() -> None:
    assert frozenset({"CAP-IN-10"}) == DRIVERS_PENDING


def test_cap_in_10_driver_resolution_stays_loud() -> None:
    """driver_for keeps raising for the pending id — never a silent no-op."""
    from benchmark.drivers import DriverNotRegisteredError, driver_for

    try:
        driver_for("CAP-IN-10")
    except DriverNotRegisteredError as exc:
        assert "CAP-IN-10" in str(exc)
    else:
        raise AssertionError("CAP-IN-10 resolved a driver before Task 14")


def test_preexisting_ids_stay_resolvable() -> None:
    """The pending set must not grow a shadow over already-driven entries."""
    assert "CAP-IN-01" not in DRIVERS_PENDING
    assert capability("CAP-IN-01").cap_id == "CAP-IN-01"


def test_unknown_capability_lookup_still_raises_precisely() -> None:
    try:
        capability("CAP-IN-11")
    except UnknownCapabilityError as exc:
        assert "CAP-IN-11" in str(exc)
    else:
        raise AssertionError("unknown id resolved")
